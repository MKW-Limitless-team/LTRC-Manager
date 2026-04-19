"""
Google Sheets integration models for the LTRC Manager API.

This module contains models specific to Google Sheets operations.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SheetsUpdateResult(BaseModel):
    """Individual tournament result for sheets update"""
    name: str = Field(..., description="Player's name (must match Google Sheets)")
    score: int = Field(..., description="Player's tournament score")
    new_mmr: int = Field(..., description="Player's MMR after the tournament")
    mmr_change: int = Field(..., description="MMR change (positive or negative)")
    is_rated: bool = Field(True, description="Whether this MMR should be written back to Playerdata")


class SheetsUpdateRequest(BaseModel):
    """Google Sheets update request model"""
    event_id: str = Field(..., description="Unique event identifier")
    results: List[SheetsUpdateResult] = Field(..., description="List of tournament results to update")


class SheetsUpdateResponse(BaseModel):
    """Google Sheets update response model"""
    success: bool = Field(..., description="Whether the update was successful")
    updated_cells: int = Field(..., description="Number of cells updated")
    timestamp: datetime = Field(..., description="Timestamp of the update")
    message: str = Field(..., description="Update message")


class SheetsStatusResponse(BaseModel):
    """Google Sheets status response model"""
    connected: bool = Field(..., description="Whether Google Sheets connection is active")
    sheet_name: str = Field(..., description="Name of the Google Sheet")
    locked: bool = Field(..., description="Whether sheets are locked")
    locked_by: Optional[str] = Field(None, description="Instance ID that locked the sheets")
    last_update: Optional[datetime] = Field(None, description="Timestamp of last update")
    error: Optional[str] = Field(None, description="Error message if any")
