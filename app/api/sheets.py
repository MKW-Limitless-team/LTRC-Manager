from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from app.models.sheets import SheetsUpdateRequest, SheetsUpdateResponse
from app.auth.dependencies import require_authorized_user
from app.services.sheets_manager import SheetsManager
from app.services.ltrc_processor import LTRCProcessor
from app.utils.logging import get_logger
from app.api.ltrc import _persist_tournament_response, tournament_storage

router = APIRouter()
logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_sheets_manager() -> SheetsManager:
    return SheetsManager()


@lru_cache(maxsize=1)
def get_ltrc_processor() -> LTRCProcessor:
    return LTRCProcessor()

class SheetsUpdateWithResultsRequest(BaseModel):
    """Request model for sheets update with tournament results"""
    event_id: str = Field(..., description="Unique event identifier")
    results: List[Dict[str, Any]] = Field(..., description="Tournament results to update")

@router.post("/update", response_model=SheetsUpdateResponse)
async def update_google_sheets(
    request: SheetsUpdateRequest,
    user=Depends(require_authorized_user),
):
    """
    Update Google Sheets with tournament data. Only one update can be processed at a time.
    If another update is in progress, returns HTTP 423 (Locked).
    
    Args:
        request: SheetsUpdateRequest containing event_id and results
        
    Returns:
        SheetsUpdateResponse: Update results
    """
    try:
        logger.info(f"Processing sheets update request for event: {request.event_id}")
        
        sheets_manager = get_sheets_manager()

        if sheets_manager.is_locked():
            raise HTTPException(
                status_code=423,
                detail="Google Sheets is currently busy with another update. Please try again later."
            )
        
        result = sheets_manager.update_sheets(
            event_id=request.event_id,
            results=request.results
        )

        if request.tournament is not None:
            staged_entry = tournament_storage.get(request.event_id)
            request_payload = staged_entry.get("request", {}) if staged_entry else {}
            tournament_storage[request.event_id] = {
                "request": request_payload,
                "response": request.tournament.model_dump(),
            }

            _persist_tournament_response(request.tournament, request_payload=request_payload)

            if request.persist_image:
                from app.api.images import _render_saved_image

                _render_saved_image(
                    request.event_id,
                    subtitle=request.subtitle,
                    title=request.title,
                    persist=True,
                )

            get_ltrc_processor().record_event_history(
                event_id=request.event_id,
                results=request.results,
            )
        
        logger.info(f"Google Sheets updated successfully for event: {request.event_id}")
        return result
        
    except HTTPException as e:
        if e.status_code == 423:
            logger.warning(f"Sheets are busy for event: {request.event_id if hasattr(request, 'event_id') else 'unknown'}")
        raise
    except Exception as e:
        logger.error(f"Error updating Google Sheets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating sheets: {str(e)}")

@router.get("/status")
async def get_sheets_status(user=Depends(require_authorized_user)):
    """
    Check Google Sheets connection and lock status.
    
    Returns:
        Dict: Sheets status information
    """
    try:
        logger.info("Retrieving Google Sheets status")
        
        status = get_sheets_manager().get_sheets_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting sheets status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting sheets status: {str(e)}")
