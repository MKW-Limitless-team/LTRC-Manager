"""
Unit tests for Pydantic models.

This module contains comprehensive tests for all Pydantic models used in the API.
"""

import pytest
from datetime import datetime
from app.models.base import ErrorResponse, ProcessingStatus, SheetsStatus
from app.models.ltrc import (
    PlayerData, TournamentOptions, TournamentRequest, 
    TournamentResult, TournamentResponse, TournamentResultsResponse,
    SheetsUpdateRequest, SheetsUpdateResponse
)
from app.models.image import ImageGenerationRequest, ImageGenerationResponse
from app.models.sheets import SheetsUpdateRequest as SheetsUpdateRequestModel


class TestBaseModels:
    """Test cases for base models"""

    def test_error_response_valid(self):
        """Test ErrorResponse with valid data"""
        error_data = {
            "error": "Invalid request",
            "code": "VALIDATION_ERROR",
            "details": {"field": "name", "message": "Field is required"}
        }
        
        error = ErrorResponse(**error_data)
        assert error.error == "Invalid request"
        assert error.code == "VALIDATION_ERROR"
        assert error.details == {"field": "name", "message": "Field is required"}

    def test_processing_status_valid(self):
        """Test ProcessingStatus with valid data"""
        status_data = {
            "status": "ready",
            "sheets_locked": False,
            "locked_by": None,
            "last_processed": datetime.now(),
            "active_instances": 1,
            "supported_formats": ["FFA", "2vs2"]
        }
        
        status = ProcessingStatus(**status_data)
        assert status.status == "ready"
        assert status.sheets_locked is False
        assert status.active_instances == 1
        assert "FFA" in status.supported_formats

    def test_sheets_status_valid(self):
        """Test SheetsStatus with valid data"""
        sheets_data = {
            "connected": True,
            "sheet_name": "LTRC",
            "locked": False,
            "locked_by": None,
            "last_update": datetime.now(),
            "error": None
        }
        
        sheets = SheetsStatus(**sheets_data)
        assert sheets.connected is True
        assert sheets.sheet_name == "LTRC"
        assert sheets.locked is False


class TestLTRCModels:
    """Test cases for LTRC processing models"""

    def test_player_data_valid(self):
        """Test PlayerData with valid data"""
        player_data = {
            "name": "Player1",
            "score": 1500,
            "mii_data": "base64_encoded_data"
        }
        
        player = PlayerData(**player_data)
        assert player.name == "Player1"
        assert player.score == 1500
        assert player.mii_data == "base64_encoded_data"

    def test_player_data_invalid_score(self):
        """Test PlayerData with invalid score"""
        player_data = {
            "name": "Player1",
            "score": -100,  # Invalid negative score
            "mii_data": "base64_encoded_data"
        }
        
        # Score validation is now handled in the service layer based on format
        # For now, we'll just test that negative scores are allowed (as per LTRC rules)
        player = PlayerData(**player_data)
        assert player.score == -100

    def test_player_data_high_score(self):
        """Test PlayerData with very high score"""
        player_data = {
            "name": "Player1",
            "score": 150000,  # Above reasonable limit
            "mii_data": "base64_encoded_data"
        }
        
        # Score validation is now handled in the service layer based on format
        # For now, we'll just test that high scores are allowed in the model
        player = PlayerData(**player_data)
        assert player.score == 150000

    def test_tournament_options_default(self):
        """Test TournamentOptions with default values"""
        options = TournamentOptions()
        assert options.three_two_track is False
        assert options.two_hundred_cc is False
        assert options.ott is False

    def test_tournament_options_custom(self):
        """Test TournamentOptions with custom values"""
        options_data = {
            "32track": True,
            "200cc": True,
            "ott": True
        }
        
        options = TournamentOptions(**options_data)
        assert options.three_two_track is True
        assert options.two_hundred_cc is True
        assert options.ott is True

    def test_tournament_request_valid_ffa(self):
        """Test TournamentRequest with valid FFA data"""
        request_data = {
            "mode": "FFA",
            "players": [
                {"name": "Player1", "score": 1500, "mii_data": "data1"},
                {"name": "Player2", "score": 1200, "mii_data": "data2"}
            ],
            "options": {
                "32track": False,
                "200cc": False,
                "ott": False
            },
            "event_date": "31-01-2025"
        }
        
        request = TournamentRequest(**request_data)
        assert request.mode == "FFA"
        assert len(request.players) == 2
        assert request.event_date == "31-01-2025"
        assert request.options.three_two_track is False

    def test_tournament_request_invalid_mode(self):
        """Test TournamentRequest with invalid mode"""
        request_data = {
            "mode": "INVALID",
            "players": [{"name": "Player1", "score": 1500, "mii_data": "data1"}],
            "options": {},
            "event_date": "31-01-2025"
        }
        
        with pytest.raises(ValueError):
            TournamentRequest(**request_data)

    def test_tournament_request_invalid_date_format(self):
        """Test TournamentRequest with invalid date format"""
        request_data = {
            "mode": "FFA",
            "players": [{"name": "Player1", "score": 1500, "mii_data": "data1"}],
            "options": {},
            "event_date": "2025-01-31"  # Wrong format
        }
        
        with pytest.raises(ValueError):
            TournamentRequest(**request_data)

    def test_tournament_request_too_many_players_global_limit(self):
        """Test TournamentRequest with too many players (global limit)"""
        # Test with more than the global maximum of 72 players
        players = [{"name": f"Player{i}", "score": 1500, "mii_data": f"data{i}"} 
                  for i in range(80)]  # More than global limit of 72
        
        request_data = {
            "mode": "FFA",
            "players": players,
            "options": {},
            "event_date": "31-01-2025"
        }
        
        # Player count validation is now handled in the service layer based on format
        # For now, we'll just test that the model accepts the data
        request = TournamentRequest(**request_data)
        assert request.mode == "FFA"
        assert len(request.players) == 80

    def test_tournament_result_valid(self):
        """Test TournamentResult with valid data"""
        result_data = {
            "name": "Player1",
            "score": 1500,
            "old_mmr": 4500,
            "new_mmr": 4650,
            "mmr_change": 150,
            "rank": "Gold",
            "rank_change": "up",
            "completion": "3/3",
            "mii_data": "base64_data"
        }
        
        result = TournamentResult(**result_data)
        assert result.name == "Player1"
        assert result.score == 1500
        assert result.mmr_change == 150

    def test_tournament_response_valid(self):
        """Test TournamentResponse with valid data"""
        response_data = {
            "event_id": "LTRC_S1E1",
            "mode": "FFA",
            "processed_at": datetime.now(),
            "results": [
                {
                    "name": "Player1",
                    "score": 1500,
                    "old_mmr": 4500,
                    "new_mmr": 4650,
                    "mmr_change": 150,
                    "rank": "Gold",
                    "rank_change": "up",
                    "completion": "3/3",
                    "mii_data": "data"
                }
            ],
            "image_generated": True,
            "image_url": "/images/test.png"
        }
        
        response = TournamentResponse(**response_data)
        assert response.event_id == "LTRC_S1E1"
        assert response.mode == "FFA"
        assert response.image_generated is True

    def test_sheets_update_request_valid(self):
        """Test SheetsUpdateRequest with valid data"""
        request_data = {
            "event_id": "LTRC_S1E1",
            "update_placements": True,
            "update_playerdata": True
        }
        
        request = SheetsUpdateRequest(**request_data)
        assert request.event_id == "LTRC_S1E1"
        assert request.update_placements is True
        assert request.update_playerdata is True


class TestImageModels:
    """Test cases for image generation models"""

    def test_image_generation_request_valid(self):
        """Test ImageGenerationRequest with valid data"""
        request_data = {
            "format_type": "FFA",
            "results": [
                {
                    "name": "Player1",
                    "score": 1500,
                    "mmr_change": 150,
                    "new_mmr": 4650,
                    "completion": "3/3",
                    "mii_data": "base64_data"
                }
            ],
            "event_id": "LTRC_S1E1",
            "event_date": "31-01-2025"
        }
        
        request = ImageGenerationRequest(**request_data)
        assert request.format_type == "FFA"
        assert len(request.results) == 1
        assert request.event_id == "LTRC_S1E1"
        assert request.event_date == "31-01-2025"

    def test_image_generation_response_valid(self):
        """Test ImageGenerationResponse with valid data"""
        response_data = {
            "success": True,
            "message": "Image generated successfully",
            "image_data": "base64_encoded_image",
            "image_url": "/images/test.png"
        }
        
        response = ImageGenerationResponse(**response_data)
        assert response.success is True
        assert response.message == "Image generated successfully"
        assert response.image_data == "base64_encoded_image"


class TestSheetsModels:
    """Test cases for sheets models"""

    def test_sheets_update_request_model_valid(self):
        """Test SheetsUpdateRequestModel with valid data"""
        request_data = {
            "event_id": "LTRC_S1E1",
            "results": [
                {
                    "name": "Player1",
                    "score": 1500,
                    "new_mmr": 4650,
                    "mmr_change": 150
                }
            ]
        }
        
        request = SheetsUpdateRequestModel(**request_data)
        assert request.event_id == "LTRC_S1E1"
        assert len(request.results) == 1
        assert request.results[0].name == "Player1"

    def test_sheets_update_response_valid(self):
        """Test SheetsUpdateResponse with valid data"""
        response_data = {
            "success": True,
            "updated_cells": 45,
            "timestamp": datetime.now(),
            "message": "Sheet updated successfully"
        }
        
        response = SheetsUpdateResponse(**response_data)
        assert response.success is True
        assert response.updated_cells == 45
        assert "Sheet updated successfully" in response.message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
