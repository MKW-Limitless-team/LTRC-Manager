"""
LTRC Processing service.

This module contains the business logic for tournament processing and MMR calculations.
Based on the original MMR.py implementation.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np
import sys
import os
import json
import gspread
from gspread.utils import ValueRenderOption
from google.oauth2.service_account import Credentials
from app.utils.logging import get_logger

# Get logger
logger = get_logger(__name__)


class LTRCProcessor:
    """
    Service class for processing LTRC tournaments and calculating MMR changes.
    
    This class handles the core business logic for tournament processing,
    including MMR calculations, player placement tracking, and Google Sheets updates.
    Based on the original MMR.py implementation.
    """
    
    def __init__(self):
        """Initialize the LTRC processor."""
        logger.info("Initializing LTRC processor")
        
        # MMR Ranges and thresholds (from MMR.py lines 10-27)
        self.MMR_THRESHOLDS = {
            10: 500, 20: 1000, 30: 1500, 
            40: 2000, 50: 2250, 60: 2500, 
            70: 3000, 80: 3250, 90: 3500, 
            100: 4000, 110: 4250, 120: 4500, 
            130: 5250, 140: 5500, 
            150: 6250, 160: 6500, 
            170: 7250, 180: 7500
        }
        
        # Format configurations with correct player limits (from MMR.py lines 32-43)
        self.FORMAT_CONFIGS = {
            "FFA": {"team_size": 1, "podium_count": 3, "max_players": 12},
            "2vs2": {"team_size": 2, "podium_count": 3, "max_players": 12},
            "3vs3": {"team_size": 3, "podium_count": 3, "max_players": 12},
            "4vs4": {"team_size": 4, "podium_count": 3, "max_players": 12},
            "5vs5": {"team_size": 5, "podium_count": 2, "max_players": 10},  # 2 teams of 5
            "6vs6": {"team_size": 6, "podium_count": 2, "max_players": 12}   # 2 teams of 6
        }
        
        # Google Sheets connection and data
        self._initialize_sheets_connection()
        self.playerdata_cache = None
        self.placements_cache = None
    
    def _initialize_sheets_connection(self):
        """Initialize Google Sheets connection using gspread."""
        try:
            logger.info("Initializing Google Sheets connection for LTRC processor")
            
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
            self.Playerdata = sheet.get_worksheet(4)
            self.Placements = sheet.get_worksheet(6)
            
            logger.info("Google Sheets connection initialized successfully for LTRC processor")
            
        except Exception as e:
            logger.error(f"Error initializing Google Sheets connection: {str(e)}")
            raise
    
    def _read_sheets_data(self):
        """Read all necessary data from Google Sheets once and cache it."""
        try:
            logger.info("Reading player data from Google Sheets")
            
            # Read Playerdata sheet (list of lists)
            self.playerdata_cache = self.Playerdata.get_all_values()
            
            # Read Placements sheet (list of lists, skipping header rows)
            self.placements_cache = self.Placements.get_all_values()[4:]  # Skip header rows
            
            logger.info(f"Read {len(self.playerdata_cache)} players from Playerdata sheet")
            logger.info(f"Read {len(self.placements_cache)} players from Placements sheet")
            
        except Exception as e:
            logger.error(f"Error reading sheets data: {str(e)}")
            raise
    
    def _get_player_mmr_from_sheets(self, player_name: str) -> int:
        """Get player's current MMR from Playerdata sheet."""
        if self.playerdata_cache is None:
            self._read_sheets_data()
        
        # Find player in Playerdata sheet (column A = index 0)
        for row in self.playerdata_cache:
            if row and len(row) > 0 and row[0].lower() == player_name.lower():
                # MMR is in column D (index 3)
                if len(row) > 3 and row[3] and row[3] != "???":
                    return int(row[3])
                else:
                    # Player exists but has no MMR (unplaced)
                    return None
        
        # Player not found in sheets
        raise ValueError(f"Player '{player_name}' not found in Playerdata sheet")
    
    def _get_player_placement_data_from_sheets(self, player_name: str) -> Dict[str, Any]:
        """Get player's placement data from Placements sheet."""
        if self.placements_cache is None:
            self._read_sheets_data()
        
        # Find player in Placements sheet (column A = index 0)
        for row_idx, row in enumerate(self.placements_cache, start=5):  # Start at row 5 (after headers)
            if row and len(row) > 0 and row[0].lower() == player_name.lower():
                return {
                    'row': row_idx,
                    'completion': row[1] if len(row) > 1 else None,
                    'point1': row[3] if len(row) > 3 and row[3] else None,
                    'point2': row[4] if len(row) > 4 and row[4] else None,
                    'point3': row[5] if len(row) > 5 and row[5] else None,
                    'mmr_accum': row[7] if len(row) > 7 and row[7] else "0"
                }
        
        return None
    
    def process_tournament(self, event_id: str, mode: str, players: List[Dict[str, Any]], 
                          options: Dict[str, Any], event_date: str) -> Dict[str, Any]:
        """
        Process a tournament and calculate MMR changes.
        Based on the original MMR.py LTRC_routine method.
        Reads player data from Google Sheets instead of API request.
        
        Args:
            event_id: Unique event identifier
            mode: Tournament format (FFA, 2vs2, 3vs3, 4vs4, 5vs5, 6vs6)
            players: List of player data with name, score, old_mmr, mii_data
            options: Tournament options (32track, 200cc, ott)
            event_date: Date when the event was held
            
        Returns:
            Dict containing processing results
        """
        try:
            logger.info(f"Processing {mode} tournament with {len(players)} players")
            
            # Validate format
            if mode not in self.FORMAT_CONFIGS:
                raise ValueError(f"Unsupported tournament format: {mode}")
            
            # Get format configuration
            format_config = self.FORMAT_CONFIGS[mode]
            team_size = format_config["team_size"]
            max_players = format_config["max_players"]
            
            # Validate player count based on format (from MMR.py lines 32-43)
            if len(players) > max_players:
                raise ValueError(f"Player count ({len(players)}) exceeds maximum for {mode} format ({max_players})")
            
            # Validate team size divisibility for team formats
            if mode != "FFA" and len(players) % team_size != 0:
                raise ValueError(f"Player count must be divisible by team size ({team_size}) for {mode}")
            
            # Validate score limits (from MMR.py lines 58-65)
            for player in players:
                score = player["score"]
                # Check 32track option directly - no default fallback
                if "32track" in options and options["32track"]:
                    # 32-track: max 480 points (180 * 2.67)
                    if score > 480:
                        raise ValueError(f"Score {score} exceeds maximum for 32-track mode (480)")
                else:
                    # Normal events: max 180 points
                    if score > 180:
                        raise ValueError(f"Score {score} exceeds maximum for normal events (180)")
            
            # Read player data from Google Sheets and enrich player dictionaries
            for player in players:
                # Add score to player dict for easier access (already there, but being explicit)
                score = player["score"]
                
                # Get MMR data from sheets for each player (NO DEFAULTS - error if missing)
                try:
                    player_mmr = self._get_player_mmr_from_sheets(player["name"])
                    if player_mmr is None:
                        # Player exists but is unplaced (MMR = ???)
                        player["old_mmr"] = "???"
                        player["lr_value"] = None  # Will be calculated in placement logic
                    else:
                        player["old_mmr"] = player_mmr
                        player["lr_value"] = player_mmr  # For placed players, lr_value = old_mmr
                except ValueError as e:
                    # Player not found in sheets - this is an error, no default
                    raise ValueError(f"Player '{player['name']}' not found in Playerdata sheet. Cannot process tournament without player data.")
            
            # Calculate placements for unplaced players (from MMR.py calculate_placement)
            is_placed, completion = self._calculate_placement(players, options)
            
            # Extract data for ranking calculation and add to player dictionaries
            scores = [player["score"] for player in players]
            lr_list = [player["lr_value"] for player in players]
            
            # Find rankings (from MMR.py find_ranking method)
            rankings = self._find_rankings(scores, mode)
            
            # Add rankings to player dictionaries
            for i, player in enumerate(players):
                player["ranking"] = rankings[i]
                player["is_placed"] = is_placed[i]
                player["completion"] = completion[i]
            
            # Find K-values (from MMR.py find_k_values method)
            k_values = self._get_k_values(rankings, mode)
            
            # Add K-values to player dictionaries
            for i, player in enumerate(players):
                player["k_value"] = k_values[i]
            
            # Calculate new MMR values (from MMR.py calc_new_MMR method)
            mmr_changes, new_mmrs = self._calculate_mmr_changes(
                lr_list, k_values, rankings, mode, options
            )
            
            # Add MMR changes and new MMRs to player dictionaries
            for i, player in enumerate(players):
                player["mmr_change"] = mmr_changes[i]
                player["new_mmr"] = new_mmrs[i]
            
            # Generate results - now all data is in player dictionaries
            results = self._generate_results(players)
            
            # Create response
            response = {
                "event_id": event_id,
                "mode": mode,
                "processed_at": datetime.now(),
                "results": results,
                "event_date": event_date
            }
            
            logger.info(f"Tournament processed successfully: {response['event_id']}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing tournament: {str(e)}")
            raise
    
    def _calculate_placement(self, players: List[Dict[str, Any]], 
                           options: Dict[str, Any]) -> tuple:
        """Calculate placements for unplaced players using enhanced player dictionaries"""
        is_placed = []
        completion = []
        
        for player in players:
            player_name = player["name"]
            score = player["score"]
            old_mmr = player["old_mmr"]
            
            if old_mmr == "???" or old_mmr == "" or old_mmr is None:
                # Unplaced player - need to check placement progress from sheets
                is_placed.append(False)
                
                # Get placement data from sheets
                placement_data = self._get_player_placement_data_from_sheets(player_name)
                
                if placement_data is None:
                    # New player - first race
                    completion.append("1/3")
                    points = [score]
                else:
                    # Existing unplaced player - check completion status
                    completion_status = placement_data['completion']
                    points = []
                    
                    if not completion_status:
                        # First placement race
                        completion.append("1/3")
                        points = [score]
                    elif completion_status == "1/3":
                        # Second placement race
                        completion.append("2/3")
                        points = [score]
                        if placement_data['point1']:
                            points.append(float(placement_data['point1']))
                    elif completion_status == "2/3":
                        # Third placement race - this will place the player
                        completion.append("3/3")
                        is_placed.append(True)  # Player will be placed after this race
                        points = [score]
                        if placement_data['point1']:
                            points.append(float(placement_data['point1']))
                        if placement_data['point2']:
                            points.append(float(placement_data['point2']))
                    else:
                        # Invalid completion status
                        raise ValueError(f"Invalid completion status for {player_name}: {completion_status}")
                
                # Calculate assumed MMR based on score (from MMR.py)
                if "32track" in options and options["32track"]:
                    points = [p / 2.67 for p in points]
                
                # Calculate average points for MMR assumption
                average = np.average(points)
                
                # Calculate the MMR of the racer based on the average
                assumed_mmr = 40 * average + 500
                
                # Handle previous season MMR averaging for 2/3 completion players (from MMR.py lines 150-160)
                if placement_data and placement_data['completion'] == "2/3":
                    # Get previous season MMR from Playerdata sheet (column K = index 10)
                    previous_season_mmr = self.Playerdata.cell(placement_data['row'], 11).value
                    if previous_season_mmr and previous_season_mmr != "???":
                        previous_season_mmr = int(previous_season_mmr)
                        assumed_mmr = (assumed_mmr + previous_season_mmr) / 2
                    
                
                # Add previously gained MMR to the new MMR (from MMR.py lines 165-168)
                if placement_data and placement_data['mmr_accum']:
                    mmr_accum = int(placement_data['mmr_accum']) if placement_data['mmr_accum'] else 0
                    assumed_mmr += mmr_accum
                
                # Store the calculated lr_value in the player dict
                player["lr_value"] = assumed_mmr
            else:
                # Placed player - lr_value is the same as old_mmr
                is_placed.append(True)
                completion.append("")
                player["lr_value"] = int(old_mmr)
        
        return is_placed, completion
    
    def _find_rankings(self, scores: List[int], mode: str) -> List[int]:
        """Find rankings based on scores (from MMR.py find_ranking method)"""
        rankings = [1]
        
        # Get team scores depending on the mode (from MMR.py lines 185-200)
        if mode == "FFA":
            team_scores = scores
        elif mode == "2vs2":
            team_scores = [sum(scores[i:i+2]) for i in range(0, len(scores), 2)]
        elif mode == "3vs3":
            team_scores = [sum(scores[i:i+3]) for i in range(0, len(scores), 3)]
        elif mode == "4vs4":
            team_scores = [sum(scores[i:i+4]) for i in range(0, len(scores), 4)]
        elif mode == "5vs5":
            team_scores = [sum(scores[i:i+5]) for i in range(0, len(scores), 5)]
        elif mode == "6vs6":
            team_scores = [sum(scores[i:i+6]) for i in range(0, len(scores), 6)]
        
        # Find the rankings of the racers/teams (from MMR.py lines 185-200)
        for i in range(1, len(team_scores)):
            if team_scores[i] == team_scores[i-1]:
                rankings.append(rankings[i-1])
            else:
                rankings.append(i+1)
        
        # Make the list the right size again (from MMR.py lines 185-200)
        if mode == "FFA":
            rankings = rankings
        elif mode == "2vs2":
            rankings = [rankings[i//2] for i in range(len(rankings)*2)]
        elif mode == "3vs3":
            rankings = [rankings[i//3] for i in range(len(rankings)*3)]
        elif mode == "4vs4":
            rankings = [rankings[i//4] for i in range(len(rankings)*4)]
        elif mode == "5vs5":
            rankings = [rankings[i//5] for i in range(len(rankings)*5)]
        elif mode == "6vs6":
            rankings = [rankings[i//6] for i in range(len(rankings)*6)]
        
        return rankings
    
    def _get_k_values(self, rankings: List[int], mode: str) -> List[int]:
        """Get K values based on rankings and tournament mode using the correct formula."""
        # Get format configuration to determine team size and max players
        format_config = self.FORMAT_CONFIGS[mode]
        team_size = format_config["team_size"]
        max_players = format_config["max_players"]
        
        # Calculate maximum number of teams/players (depending on format)
        if mode == "FFA":
            # For FFA, it's individual players
            max_teams = max_players
        else:
            # For team formats, it's number of teams
            max_teams = max_players // team_size
        
        # Maximum loss value (from original hardcoded values, using FFA max as baseline)
        max_loss = 20
        
        # Calculate K values using the formula: K = min(round((ranking - 1) / (num_players/team_size - 1)), max_loss)
        k_values = []
        for ranking in rankings:
            # Calculate the ratio: (ranking - 1) / (max_teams - 1)
            if max_teams > 1:
                ratio = (ranking - 1) / (max_teams - 1)
            else:
                ratio = 0  # Avoid division by zero
            
            # Apply the formula and round to nearest integer
            k_value = min(round(ratio), max_loss)
            k_values.append(k_value)
        
        return k_values
    
    def _calculate_mmr_changes(self, lr_list: List[int], k_values: List[int], 
                             rankings: List[int], mode: str, options: Dict[str, Any]) -> tuple:
        """Calculate MMR changes for all players (from MMR.py calc_new_MMR method)"""
        # Constants from MMR.py lines 220-260
        C = 100  # This would come from the spreadsheet
        p_mu = 5800
        
        # Calculate the average MMR of the room (from MMR.py lines 220-260)
        average_room_MMR = np.average(lr_list)
        
        # Calculate MMR changes (from MMR.py lines 220-260)
        delta_MMRs = []
        for i in range(len(lr_list)):
            # The equation for the change in MMR (from MMR.py lines 220-260)
            delta_MMR = C/12 + C/(1+11**(-(average_room_MMR-lr_list[i])/p_mu)) - k_values[i]
            delta_MMRs.append(delta_MMR)
        
        # Average MMR gain for the teams (from MMR.py lines 220-260)
        team_size = self.FORMAT_CONFIGS[mode]["team_size"]
        if team_size > 1:
            delta_MMRs = [sum(delta_MMRs[i:i+team_size])/team_size for i in range(0, len(delta_MMRs), team_size)]
            delta_MMRs = [delta_MMRs[i//team_size] for i in range(len(delta_MMRs)*team_size)]
        
        # Modify MMR if 32 track mode is enabled (from MMR.py lines 220-260)
        # Check 32track option directly - no default fallback
        if "32track" in options and options["32track"]:
            delta_MMRs = [delta_MMR * 2.67 if delta_MMR > 0 else delta_MMR * 0.67 for delta_MMR in delta_MMRs]
        
        # Modify MMR if 200cc mode is enabled - halve losses only (from MMR.py lines 220-260)
        # Check 200cc option directly - no default fallback
        if "200cc" in options and options["200cc"]:
            delta_MMRs = [delta_MMR if delta_MMR > 0 else delta_MMR * 0.5 for delta_MMR in delta_MMRs]
        
        # Round the MMR changes to the nearest integer (from MMR.py lines 220-260)
        delta_MMRs = [int(round(delta_MMR)) for delta_MMR in delta_MMRs]
        
        # Calculate new MMR values (from MMR.py lines 220-260)
        new_mmrs = [lr_list[i] + delta_MMRs[i] for i in range(len(lr_list))]
        new_mmrs = [int(round(mmr)) for mmr in new_mmrs]
        
        return delta_MMRs, new_mmrs
    
    def _generate_results(self, players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate tournament results for all players (from MMR.py get_results)"""
        results = []

        for player in players:
            if player["old_mmr"] == "???":
                old_mmr = -1
            else:
                old_mmr = player["old_mmr"]

            result = {
                "name": player["name"],
                "ranking": player["ranking"],
                "score": player["score"],
                "old_mmr": old_mmr,
                "new_mmr": player["new_mmr"],
                "mmr_change": player["mmr_change"],
                "completion": player["completion"] if not player["is_placed"] else "",
                "mii_data": player["mii_data"] if "mii_data" in player else ""
            }

            results.append(result)
    
        return results
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        import time
        timestamp = int(time.time())
        return f"LTRC_S1E{timestamp}"
    
    def update_google_sheets(self, event_id: str, update_placements: bool = True, 
                           update_playerdata: bool = True) -> Dict[str, Any]:
        """
        Update Google Sheets with tournament data.
        This method delegates to the SheetsManager service for actual Google Sheets operations.
        
        Args:
            event_id: Unique event identifier
            update_placements: Whether to update placements sheet
            update_playerdata: Whether to update player data sheet
            
        Returns:
            Dict containing update results
        """
        try:
            logger.info(f"Updating Google Sheets for event: {event_id}")
            
            # Import SheetsManager to handle actual Google Sheets operations
            from app.services.sheets_manager import SheetsManager
            
            # Initialize sheets manager
            sheets_manager = SheetsManager()
            
            # Use the sheets manager to perform the actual update
            result = sheets_manager.update_sheets(
                event_id=event_id,
                results=[],  # Results would be passed from the main processing
                update_placements=update_placements,
                update_playerdata=update_playerdata
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating Google Sheets: {str(e)}")
            raise
    
    def check_sheets_status(self) -> Dict[str, Any]:
        """Check Google Sheets connection and lock status."""
        try:
            logger.info("Checking Google Sheets status")
            
            # Import SheetsManager to handle actual Google Sheets operations
            from app.services.sheets_manager import SheetsManager
            
            # Initialize sheets manager
            sheets_manager = SheetsManager()
            
            # Use the sheets manager to check status
            status = sheets_manager.get_sheets_status()
            
            return status
            
        except Exception as e:
            logger.error(f"Error checking sheets status: {str(e)}")
            raise
