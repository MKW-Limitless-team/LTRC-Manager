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
from google.oauth2.service_account import Credentials
from app.utils.logging import get_logger

# Get logger
logger = get_logger(__name__)


class SheetsManager:
    """
    Service class for managing Google Sheets operations.
    Designed to keep Google Sheets reads and writes in one place.
    """
    
    def __init__(self):
        """Initialise the sheets manager."""
        logger.info("Initialising sheets manager")
        
        # Sheets configuration
        self.sheet_name = "LTRC"
        self.connected = False

        # Initialise the connection.
        self._initialise_connection()
    
    def _initialise_connection(self):
        """Initialise the Google Sheets connection using gspread."""
        try:
            logger.info("Initialising Google Sheets connection")
            
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
            logger.info("Google Sheets connection initialised successfully")
            
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

    def is_locked(self) -> bool:
        """Compatibility hook for the API. Sheets updates are currently unlocked."""
        return False
    
    
    def _update_placements_sheet(self, event_id: str, results: List[Dict[str, Any]]) -> int:
        """Placement state is app-owned now, so placement sheet writes are skipped."""
        logger.info(f"Skipping placements sheet update for event: {event_id}")
        return 0
    
    def _update_playerdata_sheet(self, event_id: str, results: List[Dict[str, Any]]) -> int:
        """Update the player data sheet with tournament results."""
        try:
            logger.info(f"Updating player data sheet for event: {event_id}")
            
            updated_cells = 0
            
            # Write each player's new MMR back to the sheet.
            for result in results:
                if not result.get("is_rated", True):
                    continue

                player_name = result["name"]
                new_mmr = result["new_mmr"]
                
                # Find the player in the player data sheet.
                cell = self.Playerdata.find(player_name, case_sensitive=False)
                if cell:
                    row = cell.row
                    
                    # Update the MMR column.
                    self.Playerdata.update_cell(row, 4, new_mmr)
                    updated_cells += 1
            
            logger.info(f"Updated {updated_cells} cells in player data sheet")
            return updated_cells
            
        except Exception as e:
            logger.error(f"Error updating player data sheet: {str(e)}")
            raise
    
    def get_sheets_status(self) -> Dict[str, Any]:
        """Check Google Sheets connection status."""
        try:
            logger.info("Checking Google Sheets status")
            
            # Check connection status
            connected = self.connected
            
            status = {
                "connected": connected,
                "sheet_name": self.sheet_name,
                "locked": False,
                "locked_by": None,
                "last_update": None,
                "error": None
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error checking sheets status: {str(e)}")
            return {
                "connected": False,
                "sheet_name": self.sheet_name,
                "locked": False,
                "locked_by": None,
                "last_update": None,
                "error": str(e)
            }
