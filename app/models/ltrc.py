"""
LTRC Processing models for the LTRC Manager API.

This module contains models specific to tournament processing and MMR calculations.
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class PlayerData(BaseModel):
    """Player data model"""
    name: str = Field(..., description="Player's display name", min_length=1, max_length=50)
    score: int = Field(..., description="Player's score in the tournament")
    mii_data: str = Field(..., description="Base64-encoded Mii image data")


class TournamentOptions(BaseModel):
    """Tournament options model"""
    three_two_track: bool = Field(False, alias="32track", description="Enable 32-track mode")
    two_hundred_cc: bool = Field(False, alias="200cc", description="Enable 200cc mode")
    ott: bool = Field(False, description="Enable OTT mode")


class TournamentRequest(BaseModel):
    """Tournament processing request model"""
    event_id: str = Field(..., description="Unique event identifier")
    mode: str = Field(..., description="Tournament format", 
                     pattern="^(FFA|2vs2|3vs3|4vs4|5vs5|6vs6)$")
    players: List[PlayerData] = Field(..., description="List of players")
    options: TournamentOptions = Field(default_factory=TournamentOptions, 
                                     description="Tournament options")
    event_date: str = Field(..., description="Date when the event was held (DD-MM-YYYY format)",
                          pattern=r"^\d{1,2}-\d{1,2}-\d{4}$")


class WorkflowProcessRequest(BaseModel):
    """Workflow processing request that reads players from Google Sheets."""
    event_id: str = Field(..., description="Unique event identifier")
    mode: str = Field(..., description="Tournament format", pattern="^(FFA|2vs2|3vs3|4vs4|5vs5|6vs6)$")
    options: TournamentOptions = Field(default_factory=TournamentOptions, description="Tournament options")
    event_date: str = Field(
        ...,
        description="Date when the event was held (DD-MM-YYYY format)",
        pattern=r"^\d{1,2}-\d{1,2}-\d{4}$",
    )

class TournamentResult(BaseModel):
    """Tournament result model"""
    name: str = Field(..., description="Player's name")
    ranking: int = Field(..., description="Player or team ranking")
    score: int = Field(..., description="Player's score")
    old_mmr: int = Field(..., description="Player's MMR before the tournament")
    new_mmr: int = Field(..., description="Player's MMR after the tournament")
    mmr_change: int = Field(..., description="MMR change (can be negative)")
    mii_data: str = Field(..., description="Base64-encoded Mii image data")


class TournamentResponse(BaseModel):
    """Tournament processing response model"""
    event_id: str = Field(..., description="Unique event identifier")
    mode: str = Field(..., description="Tournament format")
    processed_at: datetime = Field(..., description="Timestamp when processing was completed")
    results: List[TournamentResult] = Field(..., description="List of tournament results")
    options: TournamentOptions = Field(..., description="Tournament options used")
    event_date: str = Field(..., description="Event date in DD-MM-YYYY format")



class SheetsUpdateRequest(BaseModel):
    """Google Sheets update request model"""
    event_id: str = Field(..., description="Unique event identifier")
    update_placements: bool = Field(True, description="Whether to update placements sheet")
    update_playerdata: bool = Field(True, description="Whether to update player data sheet")


class SheetsUpdateResponse(BaseModel):
    """Google Sheets update response model"""
    success: bool = Field(..., description="Whether the update was successful")
    updated_cells: int = Field(..., description="Number of cells updated")
    timestamp: datetime = Field(..., description="Timestamp of the update")
    message: str = Field(..., description="Update message")
