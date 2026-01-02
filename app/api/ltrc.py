from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Dict, Any

from app.models.ltrc import (
    TournamentRequest, TournamentResponse, TournamentResultsResponse,
    SheetsUpdateRequest, SheetsUpdateResponse
)
from app.services.ltrc_processor import LTRCProcessor
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

tournament_storage: Dict[str, Dict[str, Any]] = {}
ltrc_processor = LTRCProcessor()

@router.post("/process", response_model=TournamentResponse)
async def process_tournament(request: TournamentRequest):
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
        
        result = ltrc_processor.process_tournament(
            mode=request.mode,
            players=players_data,
            options=options_data,
            event_date=request.event_date,
            event_id=request.event_id
        )
        
        response = TournamentResponse(
            event_id=request.event_id,
            mode=result["mode"],
            processed_at=result["processed_at"],
            results=result["results"],
            image_generated=result.get("image_generated", False),
            image_url=result.get("image_url", None),
            event_date=result.get("event_date", request.event_date)
        )
        
        tournament_storage[request.event_id] = {
            "request": request.dict(),
            "response": response.dict()
        }
        
        logger.info(f"Tournament processed successfully: {request.event_id}")
        return response
        
    except ValueError as e:
        logger.error(f"Validation error processing tournament: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing tournament: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing tournament: {str(e)}")
@router.get("/results/{event_id}", response_model=TournamentResultsResponse)
async def get_tournament_results(event_id: str):
    """
    Retrieve processed tournament results by ID.
    
    Args:
        event_id: Unique event identifier
        
    Returns:
        TournamentResultsResponse: Tournament results
    """
    try:
        logger.info(f"Retrieving results for event: {event_id}")
        
        if event_id not in tournament_storage:
            logger.warning(f"Event not found: {event_id}")
            raise HTTPException(status_code=404, detail="Event not found")
        
        response_data = tournament_storage[event_id]["response"]
        return TournamentResultsResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving tournament results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving results: {str(e)}")

@router.get("/status")
async def get_processing_status():
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
            "supported_formats": ["FFA", "2vs2", "3vs3", "4vs4", "5vs5", "6vs6"]
        }
        
    except Exception as e:
        logger.error(f"Error getting processing status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")
