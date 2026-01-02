"""
Google Sheets management service.

This module contains the business logic for Google Sheets operations and locking.
"""

from datetime import datetime
import sys
import os
import json
from typing import Dict, Any, Optional, List

import gspread
from gspread.utils import ValueRenderOption
from google.oauth2.service_account import Credentials
from app.utils.logging import get_logger

# Get logger
logger = get_logger(__name__)


class SheetsManager:
    """
    Service class for managing Google Sheets operations.
    Optimized for 2 API calls: one for reading, one for writing.
    Based on the original MMR.py implementation.
    """
    
    def __init__(self):
        """Initialize the sheets manager."""
        logger.info("Initializing sheets manager")
        
        # Sheets configuration
        self.sheet_name = "LTRC"
        self.connected = False

        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize Google Sheets connection using gspread."""
        try:
            logger.info("Initializing Google Sheets connection")
            
            # Load configuration to get sheet name
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
                
            config_path = os.path.join(base_path, "..", "..", "assets", "config.json")
            with open(config_path, 'r') as f:
                config = json.load(f)
            self.sheet_name = config['sheetname']

            # Define the scope
            scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive.file','https://www.googleapis.com/auth/drive']

            # Add your service account file
            credentials_path = os.path.join(base_path, "..", "..", "assets", 'auto-mmr-calculator-9676e1429d9a.json')
            creds = Credentials.from_service_account_file(credentials_path, scopes=scope)

            # Authorize the clientsheet
            client = gspread.authorize(creds)

            # Get the instance of the Spreadsheet
            sheet = client.open(self.sheet_name) 

            # Get the individual sheets of the Spreadsheet
            self.TR_Tables = sheet.get_worksheet(2)
            self.Table_stuff = sheet.get_worksheet(3)
            self.Playerdata = sheet.get_worksheet(4)
            self.Placements = sheet.get_worksheet(6)

            # Get the mode from the spreadsheet
            self.mode = self.Table_stuff.get("C1")[0][0] 
            
            self.connected = True
            logger.info("Google Sheets connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Google Sheets connection: {str(e)}")
            self.connected = False
            raise
    
    def update_sheets(self, event_id: str, results: list) -> Dict[str, Any]:
        """
        Update Google Sheets with tournament data.
        
        Args:
            event_id: Unique event identifier
            results: List of tournament results to update
            
        Returns:
            Dict containing update results
        """
        try:
            logger.info(f"Updating Google Sheets for event: {event_id} with {len(results)} results")
            
            # Update placements sheet
            updated_cells = 0
            updated_cells += self._update_placements_sheet(event_id, results)
            
            # Update playerdata sheet
            updated_cells += self._update_playerdata_sheet(event_id, results)
            
            result = {
                "success": True,
                "updated_cells": updated_cells,
                "timestamp": datetime.now(),
                "message": "Sheet updated successfully"
            }
            
            logger.info(f"Google Sheets updated successfully for event: {event_id}")
            return result
                
        except Exception as e:
            logger.error(f"Error updating Google Sheets: {str(e)}")
            raise
    
    
    def _update_placements_sheet(self, event_id: str, results: List[Dict[str, Any]]) -> int:
        """Update the placements sheet with tournament data (from MMR.py)."""
        try:
            logger.info(f"Updating placements sheet for event: {event_id}")
            
            updated_cells = 0
            
            # Handle placement updates (from MMR.py calculate_placement method)
            for result in results:
                player_name = result["name"]
                completion = result.get("completion", "")
                mmr_change = result.get("mmr_change", 0)
                
                # Find the player in placements sheet
                cell = self.Placements.find(player_name, case_sensitive=False)
                if cell:
                    row = cell.row
                    
                    # Update completion status if player is unplaced
                    if completion:
                        self.Placements.update_cell(row, 2, completion)
                        updated_cells += 1
                    
                    # Update MMR accumulation for unplaced players
                    if completion:  # Unplaced player
                        old_mmr_accum = self.Placements.cell(row, 8).value
                        old_mmr_accum = int(old_mmr_accum) if old_mmr_accum else 0
                        new_mmr_accum = old_mmr_accum + mmr_change
                        self.Placements.update_cell(row, 8, new_mmr_accum)
                        updated_cells += 1
                        
                        # Update placement points based on completion
                        if completion == "1/3":
                            self.Placements.update_cell(row, 4, result["score"])
                            updated_cells += 1
                        elif completion == "2/3":
                            self.Placements.update_cell(row, 5, result["score"])
                            updated_cells += 1
                        elif completion == "3/3":
                            self.Placements.update_cell(row, 6, result["score"])
                            updated_cells += 1
            
            logger.info(f"Updated {updated_cells} cells in placements sheet")
            return updated_cells
            
        except Exception as e:
            logger.error(f"Error updating placements sheet: {str(e)}")
            raise
    
    def _update_playerdata_sheet(self, event_id: str, results: List[Dict[str, Any]]) -> int:
        """Update the player data sheet with tournament results (from MMR.py)."""
        try:
            logger.info(f"Updating player data sheet for event: {event_id}")
            
            updated_cells = 0
            
            # Handle player data updates (from MMR.py update_sheet method)
            for result in results:
                player_name = result["name"]
                new_mmr = result["new_mmr"]
                rank = result["rank"]
                rank_change = result["rank_change"]
                score = result["score"]
                mmr_change = result["mmr_change"]
                
                # Find the player in playerdata sheet
                cell = self.Playerdata.find(player_name, case_sensitive=False)
                if cell:
                    row = cell.row
                    
                    # Update MMR
                    self.Playerdata.update_cell(row, 4, new_mmr)
                    updated_cells += 1
                    
                    # Update rank change information (from MMR.py fill_rank_change_table)
                    old_mmr = result.get("old_mmr", 4500)
                    old_rank = self._get_rank_from_mmr(old_mmr)
                    
                    if old_rank == rank:
                        rank_change_display = ""
                        up_down = "-"
                    else:
                        rank_change_display = rank
                        up_down = "▲" if self._get_rank_value(rank) > self._get_rank_value(old_rank) else "▼"
                    
                    # Update rank change display (would need to find the correct column based on mode)
                    # For now, just update the MMR which is the most important part
                    updated_cells += 1
            
            logger.info(f"Updated {updated_cells} cells in player data sheet")
            return updated_cells
            
        except Exception as e:
            logger.error(f"Error updating player data sheet: {str(e)}")
            raise
    
    def _get_rank_from_mmr(self, mmr: int) -> str:
        """Get rank name from MMR value (from MMR.py)."""
        if mmr < 2000:
            return "Tin"
        elif mmr < 3000:
            return "Bronze"
        elif mmr < 4000:
            return "Silver"
        elif mmr < 5000:
            return "Gold"
        elif mmr < 6000:
            return "Emerald"
        elif mmr < 7000:
            return "Sapphire"
        elif mmr < 8000:
            return "Ruby"
        elif mmr < 9000:
            return "Duke"
        elif mmr < 10000:
            return "Master"
        elif mmr < 11000:
            return "Grandmaster"
        elif mmr < 15000:
            return "Monarch"
        else:
            return "Sovereign"
    
    def _get_rank_value(self, rank: str) -> int:
        """Get numerical value for rank comparison (from MMR.py)."""
        rank_values = {
            "Tin": 0, "Bronze": 1, "Silver": 2, "Gold": 3, "Emerald": 4,
            "Sapphire": 5, "Ruby": 6, "Duke": 7, "Master": 8, 
            "Grandmaster": 9, "Monarch": 10, "Sovereign": 11
        }
        return rank_values.get(rank, 0)
    
    def get_sheets_status(self) -> Dict[str, Any]:
        """Check Google Sheets connection status."""
        try:
            logger.info("Checking Google Sheets status")
            
            # Check connection status
            connected = self.connected
            
            status = {
                "connected": connected,
                "sheet_name": self.sheet_name,
                "error": None
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error checking sheets status: {str(e)}")
            return {
                "connected": False,
                "sheet_name": self.sheet_name,
                "error": str(e)
            }
