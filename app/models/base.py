"""
Base Pydantic models for the LTRC Manager API.

This module contains common models and base classes used throughout the API.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator


class ErrorResponse(BaseModel):
    """Base error response model"""
    error: str = Field(..., description="Error description")
    code: str = Field(..., description="Error code")
    details: Optional[dict] = Field(None, description="Additional error details")


class ProcessingStatus(BaseModel):
    """Processing status response model"""
    status: str = Field(..., description="Current processing status")
    sheets_locked: bool = Field(..., description="Whether Google Sheets is locked")
    locked_by: Optional[str] = Field(None, description="Instance ID that locked the sheets")
    last_processed: Optional[datetime] = Field(None, description="Timestamp of last processing")
    active_instances: int = Field(..., description="Number of active instances")
    supported_formats: List[str] = Field(..., description="Supported tournament formats")


class SheetsStatus(BaseModel):
    """Google Sheets status response model"""
    connected: bool = Field(..., description="Whether Google Sheets connection is active")
    sheet_name: str = Field(..., description="Name of the Google Sheet")
    locked: bool = Field(..., description="Whether sheets are locked")
    locked_by: Optional[str] = Field(None, description="Instance ID that locked the sheets")
    last_update: Optional[datetime] = Field(None, description="Timestamp of last update")
    error: Optional[str] = Field(None, description="Error message if any")
