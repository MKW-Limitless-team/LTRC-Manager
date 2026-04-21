import json
import os
from functools import lru_cache
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Dict, Any, List
from fastapi import Depends
from app.models.ltrc import (
    TournamentRequest, TournamentResponse,
    WorkflowProcessRequest,
)
from app.auth.dependencies import require_authorized_user
from app.services.ltrc_processor import LTRCProcessor
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

tournament_storage: Dict[str, Dict[str, Any]] = {}
LIMIT_BREAKER_MODE = "Limit Breaker"


@lru_cache(maxsize=1)
def get_ltrc_processor() -> LTRCProcessor:
    return LTRCProcessor()


def _get_event_output_dir(event_id: str) -> str:
    if event_id.startswith("LB_"):
        return os.path.join("database", "LB")

    season = event_id.split("E")[0]
    return os.path.join("database", season)


def get_event_json_path(event_id: str) -> str:
    return os.path.join(_get_event_output_dir(event_id), f"{event_id}.json")


def _persist_tournament_response(response: TournamentResponse, request_payload: Dict[str, Any] | None = None) -> None:
    tournament_storage[response.event_id] = {
        "request": request_payload or {},
        "response": response.model_dump(by_alias=True),
    }

    output_dir = _get_event_output_dir(response.event_id)
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"{response.event_id}.json")

    with open(json_path, 'w') as json_file:
        json.dump(json.loads(response.model_dump_json(by_alias=True)), json_file, indent=4)


def _calculate_limit_breaker_results(players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    indexed_players = []
    for index, player in enumerate(players):
        round_scores = player.get("round_scores") or []
        normalised_round_scores = [
            int(score) if isinstance(score, (int, float)) else None
            for score in round_scores
        ]
        rounds_played = sum(1 for score in normalised_round_scores if score is not None)
        total_score = sum(score for score in normalised_round_scores if score is not None)
        last_round_score = next(
            (score for score in reversed(normalised_round_scores) if score is not None),
            0,
        )
        indexed_players.append(
            {
                "original_index": index,
                "name": player["name"],
                "mii_data": player.get("mii_data", ""),
                "seed": player.get("seed"),
                "round_scores": normalised_round_scores,
                "rounds_played": rounds_played,
                "total_score": total_score,
                "last_round_score": last_round_score,
            }
        )

    indexed_players.sort(
        key=lambda player: (
            -player["rounds_played"],
            -player["last_round_score"],
            player["original_index"],
        )
    )

    current_rank = 1
    previous_key: tuple[int, int] | None = None
    for index, player in enumerate(indexed_players):
        current_key = (player["rounds_played"], player["last_round_score"])
        if previous_key is None:
            current_rank = 1
        elif current_key != previous_key:
            current_rank = index + 1
        player["ranking"] = current_rank
        previous_key = current_key

    return [
        {
            "name": player["name"],
            "ranking": player["ranking"],
            "score": player["total_score"],
            "old_mmr": -1,
            "new_mmr": 0,
            "mmr_change": 0,
            "is_rated": False,
            "boosted": False,
            "bonus": 0,
            "mii_data": player["mii_data"],
            "seed": player["seed"],
            "round_scores": player["round_scores"],
            "rounds_played": player["rounds_played"],
            "total_score": player["total_score"],
        }
        for player in indexed_players
    ]


def _process_limit_breaker_tournament(request: TournamentRequest) -> TournamentResponse:
    if len(request.players) == 0:
        raise ValueError("At least one player is required.")

    players_data = []
    for player in request.players:
        round_scores = list(player.round_scores or [])
        players_data.append(
            {
                "name": player.name,
                "mii_data": player.mii_data,
                "seed": player.seed,
                "round_scores": round_scores,
            }
        )

    results = _calculate_limit_breaker_results(players_data)
    response = TournamentResponse(
        event_id=request.event_id,
        mode=request.mode,
        processed_at=datetime.now(),
        results=results,
        options=request.options,
        event_date=request.event_date,
    )
    tournament_storage[request.event_id] = {
        "request": request.model_dump(by_alias=True),
        "response": response.model_dump(by_alias=True),
    }
    return response

@router.post("/process", response_model=TournamentResponse)
async def process_tournament(
    request: TournamentRequest,
    user=Depends(require_authorized_user),
):
    """
    Process tournament results and calculate MMR changes.
    Uses the actual LTRCProcessor service for real MMR calculations.
    
    Args:
        request: Tournament processing request
        
    Returns:
        TournamentResponse: Processing results
    """
    try:
        logger.info(f"Processing tournament: {request.mode} with {len(request.players)} players")
        if request.mode == LIMIT_BREAKER_MODE:
            response = _process_limit_breaker_tournament(request)
            logger.info(f"Tournament processed successfully: {request.event_id}. Results staged in memory")
            return response
        
        players_data = []
        for player in request.players:
            players_data.append({
                "name": player.name,
                "score": player.score,
                "mii_data": player.mii_data
            })
        
        options_data = {
            "32track": request.options.three_two_track,
            "200cc": request.options.two_hundred_cc,
            "ott": request.options.ott
        }
        
        result = get_ltrc_processor().process_tournament(
            mode=request.mode,
            players=players_data,
            options=options_data,
            event_date=request.event_date,
            event_id=request.event_id
        )
        
        # Ensure event_date is set correctly
        event_date_value = result.get("event_date") or request.event_date
        
        response = TournamentResponse(
            event_id=request.event_id,
            mode=result["mode"],
            processed_at=result["processed_at"],
            results=result["results"],
            options=request.options,
            event_date=event_date_value
        )

        tournament_storage[request.event_id] = {
            "request": request.model_dump(by_alias=True),
            "response": response.model_dump(by_alias=True),
        }

        logger.info(f"Tournament processed successfully: {request.event_id}. Results staged in memory")
        return response

    except ValueError as e:
        logger.error(f"Validation error processing tournament: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing tournament: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing tournament: {str(e)}")
@router.post("/workflow/process", response_model=TournamentResponse)
async def process_tournament_from_sheet(
    request: WorkflowProcessRequest,
    user=Depends(require_authorized_user),
):
    try:
        if request.mode == LIMIT_BREAKER_MODE:
            raise ValueError("Limit Breaker must be entered manually and cannot be loaded from Google Sheets.")

        processor = get_ltrc_processor()
        players = processor.load_players_from_sheet(request.mode)
        result = processor.process_tournament(
            mode=request.mode,
            players=players,
            options={
                "32track": request.options.three_two_track,
                "200cc": request.options.two_hundred_cc,
                "ott": request.options.ott,
            },
            event_date=request.event_date,
            event_id=request.event_id,
        )

        response = TournamentResponse(
            event_id=request.event_id,
            mode=result["mode"],
            processed_at=result["processed_at"],
            results=result["results"],
            options=request.options,
            event_date=result.get("event_date") or request.event_date,
        )

        tournament_storage[request.event_id] = {
            "request": request.model_dump(by_alias=True),
            "response": response.model_dump(),
        }
        return response
    except ValueError as e:
        logger.error(f"Validation error processing workflow tournament: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing workflow tournament: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing tournament: {str(e)}")


@router.get("/results/{event_id}", response_model=TournamentResponse)
async def get_tournament_results(
    event_id: str,
    user=Depends(require_authorized_user),
):
    """
    Retrieve processed tournament results by ID.
    
    Args:
        event_id: Unique event identifier
        
    Returns:
        TournamentResponse: Tournament results
    """
    try:
        logger.info(f"Retrieving results for event: {event_id}")
        
        # Check if results exist in database directory with season folder structure
        json_path = get_event_json_path(event_id)
        if not os.path.exists(json_path):
            logger.warning(f"Results not found for event: {event_id}")
            raise HTTPException(status_code=404, detail=f"Results not found for event ID: {event_id}")
        
        # Load from JSON file
        with open(json_path, 'r') as json_file:
            response_data = json.load(json_file)
            return TournamentResponse(**response_data)
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in results file for event {event_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Corrupt results data")
    except Exception as e:
        logger.error(f"Error retrieving tournament results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving results: {str(e)}")

@router.get("/status")
async def get_processing_status(user=Depends(require_authorized_user)):
    """
    Get current processing status and system information.
    
    Returns:
        Dict: Processing status information
    """
    try:
        logger.info("Retrieving processing status")
        
        sheets_locked = False
        locked_by = None
        
        return {
            "status": "ready",
            "sheets_locked": sheets_locked,
            "locked_by": locked_by,
            "last_processed": datetime.now(),
            "active_instances": 1,
            "supported_formats": ["FFA", "FFA KO", "2vs2", "2v2 GP", "3vs3", "4vs4", "5vs5", "6vs6", LIMIT_BREAKER_MODE]
        }
        
    except Exception as e:
        logger.error(f"Error getting processing status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@router.get("/next-event-id")
async def get_next_event_id(
    mode: str = Query("FFA"),
    user=Depends(require_authorized_user),
):
    try:
        if mode == LIMIT_BREAKER_MODE:
            output_dir = os.path.join("database", "LB")
            highest_event = 0
            if os.path.isdir(output_dir):
                for filename in os.listdir(output_dir):
                    if not filename.endswith(".json"):
                        continue
                    match = filename.removesuffix(".json")
                    if not match.startswith("LB_"):
                        continue
                    suffix = match[3:]
                    if suffix.isdigit():
                        highest_event = max(highest_event, int(suffix))
            return {"event_id": f"LB_{highest_event + 1}", "season": None}

        processor = get_ltrc_processor()
        return {"event_id": processor.get_next_event_id(season_number=5), "season": 5}
    except Exception as e:
        logger.error(f"Error getting next event id: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting next event id: {str(e)}")


@router.get("/players")
async def get_player_names(user=Depends(require_authorized_user)):
    try:
        processor = get_ltrc_processor()
        return {"players": processor.get_player_names()}
    except Exception as e:
        logger.error(f"Error getting player names: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting player names: {str(e)}")


@router.post("/results/save", response_model=TournamentResponse)
async def save_tournament_results(
    response: TournamentResponse,
    user=Depends(require_authorized_user),
):
    try:
        staged_entry = tournament_storage.get(response.event_id)
        request_payload = staged_entry.get("request", {}) if staged_entry else {}
        _persist_tournament_response(response, request_payload=request_payload)
        logger.info(f"Tournament results saved for event: {response.event_id}")
        return response
    except Exception as e:
        logger.error(f"Error saving tournament results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving tournament results: {str(e)}")
