from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import io
import json
import os

from app.models.image import SavedImageRequest
from app.services.ltrc_processor import LTRCProcessor
from app.services.image_generator import ImageGenerator
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/images", tags=["Image Generation"])

def load_config():
    """Load configuration from config.json"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'config.json')
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load configuration: {str(e)}")

def get_image_generator(format_type: str = 'FFA'):
    """Get the image generator instance for a specific format"""
    config = load_config()
    return ImageGenerator(format_type, config)


def get_ltrc_processor() -> LTRCProcessor:
    return LTRCProcessor()


def _load_saved_tournament(event_id: str) -> Dict[str, Any]:
    season = event_id.split('E')[0]
    json_path = os.path.join("database", season, f"{event_id}.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail=f"Results not found for event {event_id}")

    with open(json_path, 'r') as f:
        return json.load(f)


def _load_tournament_for_render(event_id: str) -> Dict[str, Any]:
    try:
        return _load_saved_tournament(event_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise

    from app.api.ltrc import tournament_storage

    staged_entry = tournament_storage.get(event_id)
    if staged_entry and staged_entry.get("response"):
        return staged_entry["response"]

    raise HTTPException(status_code=404, detail=f"Results not found for event {event_id}")


def _build_title(mode: str, options: Dict[str, Any] | None) -> str:
    options = options or {}
    title_parts = []
    if options.get("32track"):
        title_parts.append("32 Track")
    if options.get("200cc"):
        title_parts.append("200cc")
    if options.get("ott"):
        title_parts.append("OTT")
    title_parts.append(f"{mode} Results")
    return " ".join(title_parts)


def _normalise_player_name(player_name: str) -> str:
    return player_name.strip().lower()


def _get_ascendant_holders(mmr_snapshot: Dict[str, int]) -> set[str]:
    if not mmr_snapshot:
        return set()

    highest_mmr = max(mmr_snapshot.values())
    if highest_mmr <= 8000:
        return set()

    return {
        player_name
        for player_name, mmr in mmr_snapshot.items()
        if mmr == highest_mmr
    }


def _annotate_overall_ascendant_flags(players: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    processor = get_ltrc_processor()
    current_snapshot = processor.get_player_mmr_snapshot()
    old_snapshot = dict(current_snapshot)
    new_snapshot = dict(current_snapshot)

    annotated_players = [dict(player) for player in players]
    for player in annotated_players:
        if not player.get("is_rated", True):
            continue

        normalised_name = _normalise_player_name(player["name"])
        old_mmr = player.get("old_mmr", -1)
        if isinstance(old_mmr, int) and old_mmr >= 0:
            old_snapshot[normalised_name] = old_mmr

        new_snapshot[normalised_name] = player["new_mmr"]

    old_ascendant_holders = _get_ascendant_holders(old_snapshot)
    new_ascendant_holders = _get_ascendant_holders(new_snapshot)

    for player in annotated_players:
        normalised_name = _normalise_player_name(player["name"])
        player["is_top_mmr"] = normalised_name in new_ascendant_holders
        player["old_is_top_mmr"] = normalised_name in old_ascendant_holders

    return annotated_players


def _render_saved_image(
    event_id: str,
    subtitle: str | None = None,
    title: str | None = None,
    persist: bool = False,
):
    results_data = _load_tournament_for_render(event_id)

    format_type = results_data.get("mode")
    event_date = results_data.get("event_date", "")
    players = results_data.get("results", [])

    if not format_type:
        raise HTTPException(status_code=500, detail="Missing tournament mode in results")
    if not players:
        raise HTTPException(status_code=500, detail="No player results found")

    image_gen = get_image_generator(format_type)
    title_text = title or _build_title(format_type, results_data.get("options"))
    render_fn = image_gen.generate_or_retrieve if persist else image_gen.generate
    image = render_fn(
        results=_annotate_overall_ascendant_flags([
            {
                "name": player["name"],
                "score": player["score"],
                "old_mmr": player.get("old_mmr", -1),
                "mmr_change": player["mmr_change"],
                "new_mmr": player["new_mmr"],
                "is_rated": player.get("is_rated", True),
                "mii_data": player.get("mii_data", ""),
            }
            for player in players
        ]),
        event_id=event_id,
        event_date=event_date,
        title_text=title_text,
        subtitle_text=subtitle,
    )

    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer

@router.get("/generate/{event_id}", response_class=StreamingResponse, summary="Generate tournament result image")
async def generate_image(
    event_id: str,
):
    """
    Generate or retrieve tournament result image from saved results.
    Requires existing results file in database directory.
    
    Steps:
    1. Check if results exist for event_id
    2. Load saved tournament results
    3. Generate/retrieve image using ImageGenerator
    4. Return existing image or newly generated image
    
    Returns 404 if results not found
    """
    try:
        img_buffer = _render_saved_image(event_id)
        
        return StreamingResponse(
            img_buffer,
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={event_id}.png",
                "X-Image-Format": "PNG",
                "X-Image-Size": str(img_buffer.getbuffer().nbytes),
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating/retrieving image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate/retrieve image: {str(e)}")


@router.post("/generate", response_class=StreamingResponse, summary="Generate tournament result image with custom subtitle")
async def generate_image_with_custom_text(
    request: SavedImageRequest,
):
    try:
        img_buffer = _render_saved_image(
            request.event_id,
            subtitle=request.subtitle,
            title=request.title,
            persist=request.persist,
        )
        return StreamingResponse(
            img_buffer,
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={request.event_id}.png",
                "X-Image-Format": "PNG",
                "X-Image-Size": str(img_buffer.getbuffer().nbytes),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating image with custom text: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(e)}")
