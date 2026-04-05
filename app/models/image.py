"""
Image generation models for the LTRC Manager API.

This module contains models specific to image generation and retrieval.
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

class PlayerResult(BaseModel):
    """Player result data for image generation"""
    name: str = Field(..., description="Player name")
    score: int = Field(..., description="Player score")
    mmr_change: int = Field(..., description="MMR change for this tournament")
    new_mmr: int = Field(..., description="New MMR after this tournament")
    mii_data: Optional[str] = Field(None, description="Base64-encoded Mii data")

class ImageGenerationRequest(BaseModel):
    """Request model for image generation"""
    format_type: str = Field(..., description="Tournament format (FFA, 2vs2, 4vs4, 5v5, 6v6)")
    results: List[PlayerResult] = Field(..., description="List of player results")
    event_id: Optional[str] = Field(None, description="Event ID for automatic subtitle generation (format: LTRC_SxEy)")
    event_date: Optional[str] = Field(None, description="Event date for subtitle format 'Event #y DD-MM-YYYY'")


class SavedImageRequest(BaseModel):
    """Generate an image from a previously processed event."""
    event_id: str = Field(..., description="Processed event identifier")
    subtitle: Optional[str] = Field(None, description="Optional subtitle override")
    title: Optional[str] = Field(None, description="Optional title override")


class ImageGenerationResponse(BaseModel):
    """Response model for image generation"""
    success: bool = Field(..., description="Whether the image generation was successful")
    message: str = Field(..., description="Status message")
    image_data: Optional[str] = Field(None, description="Base64-encoded image data")
    image_url: Optional[str] = Field(None, description="URL to the generated image")

class ImageGenerationStatus(BaseModel):
    """Status of image generation process"""
    task_id: str = Field(..., description="Unique identifier for the generation task")
    status: str = Field(..., description="Current status (pending, processing, completed, failed)")
    progress: int = Field(0, description="Progress percentage (0-100)")
    message: str = Field("", description="Current status message")
    created_at: datetime = Field(default_factory=datetime.now, description="Task creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Task completion timestamp")
    image_url: Optional[str] = Field(None, description="URL to the generated image")
    error_message: Optional[str] = Field(None, description="Error message if task failed")
