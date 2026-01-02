from fastapi import APIRouter, HTTPException, Request
from datetime import datetime
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from app.models.sheets import SheetsUpdateRequest, SheetsUpdateResponse
from app.services.sheets_manager import SheetsManager
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)
sheets_manager = SheetsManager()

class SheetsUpdateWithResultsRequest(BaseModel):
    """Request model for sheets update with tournament results"""
    event_id: str = Field(..., description="Unique event identifier")
    results: List[Dict[str, Any]] = Field(..., description="Tournament results to update")

@router.post("/update", response_model=SheetsUpdateResponse)
async def update_google_sheets(request: SheetsUpdateRequest):
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
        
        if sheets_manager.is_locked():
            raise HTTPException(
                status_code=423,
                detail="Google Sheets is currently busy with another update. Please try again later."
            )
        
        result = sheets_manager.update_sheets(
            event_id=request.event_id,
            results=request.results
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
async def get_sheets_status():
    """
    Check Google Sheets connection and lock status.
    
    Returns:
        Dict: Sheets status information
    """
    try:
        logger.info("Retrieving Google Sheets status")
        
        status = sheets_manager.get_sheets_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting sheets status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting sheets status: {str(e)}")
