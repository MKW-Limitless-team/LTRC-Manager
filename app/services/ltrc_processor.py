"""
LTRC Processing service.

This module contains the business logic for tournament processing and MMR calculations.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np
import sys
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from app.utils.logging import get_logger

# Get logger
logger = get_logger(__name__)


class LTRCProcessor:
    """
    Service class for processing LTRC tournaments and calculating MMR changes.
    
    This class handles the core business logic for tournament processing,
    including MMR calculations, placement handling, and Google Sheets updates.
    """

    MAX_LOSS_BY_MODE = {
        "FFA": 220,
        "2vs2": 200,
        "3vs3": 180,
        "4vs4": 160,
        "5vs5": 140,
        "6vs6": 140,
    }
    
    def __init__(self):
        """Initialise the LTRC processor."""
        logger.info("Initialising LTRC processor")
        
        self.point_distribution = [15,13,11,9,8,7,6,5,4,3,2,1]
        self.base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        self.event_history_path = os.path.join(self.base_dir, "database", "player_event_history.json")

        # Format configuration with the correct player limits.
        self.FORMAT_CONFIGS = {
            "FFA": {"team_size": 1, "podium_count": 3, "max_players": 12},
            "2vs2": {"team_size": 2, "podium_count": 3, "max_players": 12},
            "3vs3": {"team_size": 3, "podium_count": 3, "max_players": 12},
            "4vs4": {"team_size": 4, "podium_count": 3, "max_players": 12},
            "5vs5": {"team_size": 5, "podium_count": 2, "max_players": 10},
            "6vs6": {"team_size": 6, "podium_count": 2, "max_players": 12}
        }
        
        # Google Sheets connection and data
        self._initialise_sheets_connection()
        self.playerdata_cache = None
    
    def _initialise_sheets_connection(self):
        """Initialise the Google Sheets connection using gspread."""
        try:
            logger.info("Initialising Google Sheets connection for LTRC processor")
            
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
            self.Playerdata = sheet.get_worksheet(4)
            
            logger.info("Google Sheets connection initialised successfully for LTRC processor")
            
        except Exception as e:
            logger.error(f"Error initializing Google Sheets connection: {str(e)}")
            raise
    
    def _read_sheets_data(self):
        """Read all necessary data from Google Sheets once and cache it."""
        try:
            logger.info("Reading player data from Google Sheets")
            
            # Read Playerdata sheet (list of lists)
            self.playerdata_cache = self.Playerdata.get_all_values()

            logger.info(f"Read {len(self.playerdata_cache)} players from Playerdata sheet")
            
        except Exception as e:
            logger.error(f"Error reading sheets data: {str(e)}")
            raise

    def get_player_names(self) -> List[str]:
        """Return the known player names from the LTRC sheet."""
        if self.playerdata_cache is None:
            self._read_sheets_data()

        names = []
        seen = set()
        ignored_headers = {"player", "players", "name", "names"}
        for row in self.playerdata_cache:
            if row and len(row) > 0 and row[0]:
                candidate = row[0].strip()
                normalised_candidate = candidate.lower()
                if (
                    candidate
                    and normalised_candidate not in ignored_headers
                    and normalised_candidate not in seen
                ):
                    names.append(candidate)
                    seen.add(normalised_candidate)

        return names

    def _ensure_players_exist(self, players: List[Dict[str, Any]]) -> None:
        """Add unknown players to Playerdata with placeholder MMR before processing."""
        if self.playerdata_cache is None:
            self._read_sheets_data()

        known_names = {
            row[0].strip().lower()
            for row in self.playerdata_cache
            if row and len(row) > 0 and row[0]
        }

        new_rows = []
        for player in players:
            normalised_name = player["name"].strip().lower()
            if normalised_name not in known_names:
                new_rows.append([player["name"], "", "", "???"])
                known_names.add(normalised_name)

        if new_rows:
            logger.info("Adding %s new player(s) to Playerdata", len(new_rows))
            self.Playerdata.append_rows(new_rows, value_input_option="RAW")
            self.playerdata_cache.extend(new_rows)

    def _get_table_range_for_mode(self, mode: str) -> str:
        ranges = {
            "FFA": "B3:C14",
            "2vs2": "B23:C39",
            "3vs3": "B48:C62",
            "4vs4": "B71:C84",
            "5vs5": "B92:C104",
            "6vs6": "B92:C104",
        }
        if mode not in ranges:
            raise ValueError(f"Unsupported tournament format: {mode}")
        return ranges[mode]

    def load_players_from_sheet(self, mode: str) -> List[Dict[str, Any]]:
        """Load the current tournament player list and scores from Google Sheets."""
        range_str = self._get_table_range_for_mode(mode)
        rows = self.TR_Tables.get(range_str)

        players = []
        for row in rows:
            if not row or len(row) < 2 or not row[0]:
                continue
            players.append(
                {
                    "name": row[0],
                    "score": int(row[1]),
                    "mii_data": "",
                }
            )

        if not players:
            raise ValueError(f"No players found in the Google Sheet for mode {mode}")

        return players
    
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
    
    def _normalise_player_name(self, player_name: str) -> str:
        """Normalise a player name for stable event-history lookups."""
        return player_name.strip().lower()

    def _load_event_history(self) -> Dict[str, Dict[str, Any]]:
        """Load the app-owned player event history."""
        if not os.path.exists(self.event_history_path):
            return {}

        try:
            with open(self.event_history_path, 'r') as history_file:
                history = json.load(history_file)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Falling back to an empty event history: {str(e)}")
            return {}

        return history if isinstance(history, dict) else {}

    def _save_event_history(self, event_history: Dict[str, Dict[str, Any]]) -> None:
        """Persist the app-owned player event history."""
        os.makedirs(os.path.dirname(self.event_history_path), exist_ok=True)
        with open(self.event_history_path, 'w') as history_file:
            json.dump(event_history, history_file, indent=4, sort_keys=True)

    def _get_player_event_count(self, event_history: Dict[str, Dict[str, Any]], player_name: str) -> int:
        """Return the number of tracked events for a player."""
        history_entry = event_history.get(self._normalise_player_name(player_name), {})
        return int(history_entry.get("events_played", 0))

    def _record_tournament_participation(self, event_history: Dict[str, Dict[str, Any]],
                                       event_id: str, players: List[Dict[str, Any]]) -> None:
        """Track processed events per player and avoid double-counting the same event."""
        for player in players:
            normalised_name = self._normalise_player_name(player["name"])
            entry = event_history.setdefault(normalised_name, {
                "name": player["name"],
                "events_played": 0,
                "event_ids": []
            })

            entry["name"] = player["name"]
            event_ids = entry.setdefault("event_ids", [])

            if event_id not in event_ids:
                event_ids.append(event_id)
                entry["events_played"] = int(entry.get("events_played", 0)) + 1

    def _get_room_minimum_points(self, room_size: int) -> int:
        """
        Get the minimum total points possible for a room size over 12 races.

        For example:
        - 12 players -> 1 point per race -> 12 total
        - 11 players -> 2 points per race -> 24 total
        """
        if room_size < 1 or room_size > len(self.point_distribution):
            raise ValueError(f"Unsupported room size for placement calculation: {room_size}")

        lowest_available_points = self.point_distribution[room_size - 1]
        return lowest_available_points * 12

    def _calculate_initial_placement_mmr(self, score: int, room_size: int, options: Dict[str, Any]) -> int:
        """Map a player's first-event score linearly into the 1000-3000 MMR range."""
        score = float(score)
        max_score = 180

        if options.get("32track"):
            score /= 8 / 3
            max_score = 480 / (8 / 3)

        min_score = self._get_room_minimum_points(room_size)

        if max_score <= min_score:
            raise ValueError(f"Invalid placement score range for room size {room_size}")

        score = min(max(score, min_score), max_score)
        ratio = (score - min_score) / (max_score - min_score)
        placement_mmr = 1000 + ratio * 2000
        return int(round(placement_mmr))
    
    def process_tournament(self, event_id: str, mode: str, players: List[Dict[str, Any]], 
                          options: Dict[str, Any], event_date: str) -> Dict[str, Any]:
        """
        Process a tournament and calculate MMR changes.
        Reads player data from Google Sheets rather than the API request.
        
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
            
            # Validate player count based on the selected format.
            if len(players) > max_players:
                raise ValueError(f"Player count ({len(players)}) exceeds maximum for {mode} format ({max_players})")
            
            # Validate team size divisibility for team formats
            if mode != "FFA" and len(players) % team_size != 0:
                raise ValueError(f"Player count must be divisible by team size ({team_size}) for {mode}")
            
            # Validate score limits.
            for player in players:
                score = player["score"]
                # Check the 32track option directly.
                if "32track" in options and options["32track"]:
                    # 32-track events use a maximum of 480 points.
                    if score > 480:
                        raise ValueError(f"Score {score} exceeds maximum for 32-track mode (480)")
                else:
                    # Standard events use a maximum of 180 points.
                    if score > 180:
                        raise ValueError(f"Score {score} exceeds maximum for normal events (180)")
            
            event_history = self._load_event_history()
            self._ensure_players_exist(players)

            # Read player data from Google Sheets and enrich player dictionaries
            for player in players:
                # Read each player's current MMR from the sheet.
                try:
                    player_mmr = self._get_player_mmr_from_sheets(player["name"])
                    player["tracked_event_count"] = self._get_player_event_count(event_history, player["name"])

                    if player_mmr is None:
                        player["old_mmr"] = "???"
                        player["lr_value"] = self._calculate_initial_placement_mmr(
                            score=player["score"],
                            room_size=len(players),
                            options=options
                        )
                        player["is_placed"] = False
                    else:
                        player["old_mmr"] = player_mmr
                        player["lr_value"] = player_mmr
                        player["is_placed"] = True
                except ValueError as e:
                    raise ValueError(f"Player '{player['name']}' not found in Playerdata sheet. Cannot process tournament without player data.")
            
            # Extract data for ranking calculation and add it to the player dictionaries.
            scores = [player["score"] for player in players]
            lr_list = [player["lr_value"] for player in players]
            
            # Find rankings.
            rankings = self._find_rankings(scores, mode)
            
            # Add rankings to player dictionaries
            for i, player in enumerate(players):
                player["ranking"] = rankings[i]
            
            # Find K-values.
            k_values = self._get_k_values(rankings, mode)
            
            # Add K-values to player dictionaries
            for i, player in enumerate(players):
                player["k_value"] = k_values[i]
            
            # Calculate new MMR values.
            mmr_changes, new_mmrs = self._calculate_mmr_changes(
                players, lr_list, k_values, rankings, mode, options
            )
            
            # Add MMR changes and new MMRs to player dictionaries
            for i, player in enumerate(players):
                player["mmr_change"] = mmr_changes[i]
                player["new_mmr"] = new_mmrs[i]
            
            # Generate results once all derived values have been added.
            results = self._generate_results(players)
            
            # Create response
            response = {
                "event_id": event_id,
                "mode": mode,
                "processed_at": datetime.now(),
                "results": results,
                "event_date": event_date
            }

            self._record_tournament_participation(event_history, event_id, players)
            self._save_event_history(event_history)
            
            logger.info(f"Tournament processed successfully: {response['event_id']}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing tournament: {str(e)}")
            raise
    
    def _find_rankings(self, scores: List[int], mode: str) -> List[int]:
        """Find rankings based on scores."""
        rankings = [1]
        
        # Build team scores for the selected format.
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
        
        # Assign rankings for players or teams.
        for i in range(1, len(team_scores)):
            if team_scores[i] == team_scores[i-1]:
                rankings.append(rankings[i-1])
            else:
                rankings.append(i+1)
        
        # Expand team rankings back to the full player list.
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
        """Get K values based on rankings and tournament mode."""
        format_config = self.FORMAT_CONFIGS[mode]
        team_size = format_config["team_size"]
        team_count = len(rankings) if team_size == 1 else len(rankings) // team_size
        max_loss = self.MAX_LOSS_BY_MODE[mode]

        if team_count <= 1:
            return [0 for _ in rankings]

        k_values = []
        for ranking in rankings:
            ratio = (ranking - 1) / (team_count - 1)
            k_value = int(round(ratio * max_loss))
            k_values.append(k_value)

        return k_values
    
    def _calculate_mmr_changes(self, players: List[Dict[str, Any]], lr_list: List[int],
                             k_values: List[int], rankings: List[int], mode: str,
                             options: Dict[str, Any]) -> tuple:
        """Calculate MMR changes for all players."""
        C = self.MAX_LOSS_BY_MODE[mode]
        p_mu = 5800
        
        # Calculate the average MMR of the room.
        average_room_MMR = np.average(lr_list)
        
        # Calculate raw MMR changes.
        delta_MMRs = []
        for i in range(len(lr_list)):
            delta_MMR = C/12 + C/(1+11**(-(average_room_MMR-lr_list[i])/p_mu)) - k_values[i]
            delta_MMRs.append(delta_MMR)
        
        # Share the same change across team members.
        team_size = self.FORMAT_CONFIGS[mode]["team_size"]
        if team_size > 1:
            delta_MMRs = [sum(delta_MMRs[i:i+team_size])/team_size for i in range(0, len(delta_MMRs), team_size)]
            delta_MMRs = [delta_MMRs[i//team_size] for i in range(len(delta_MMRs)*team_size)]
        
        # Apply format modifiers.
        if "32track" in options and options["32track"]:
            delta_MMRs = [delta_MMR * (8 / 3) if delta_MMR > 0 else delta_MMR * (2 / 3) for delta_MMR in delta_MMRs]
        
        if "200cc" in options and options["200cc"]:
            delta_MMRs = [delta_MMR if delta_MMR > 0 else delta_MMR * 0.5 for delta_MMR in delta_MMRs]

        # Boost gains and losses during each player's first three tracked events.
        boosted_deltas = []
        for i, delta_mmr in enumerate(delta_MMRs):
            tracked_event_count = players[i].get("tracked_event_count", 0)
            if tracked_event_count < 3:
                delta_mmr *= 2.5
            boosted_deltas.append(delta_mmr)
        delta_MMRs = boosted_deltas
        
        # Round the MMR changes to the nearest integer.
        delta_MMRs = [int(round(delta_MMR)) for delta_MMR in delta_MMRs]
        
        # Calculate new MMR values.
        new_mmrs = [lr_list[i] + delta_MMRs[i] for i in range(len(lr_list))]
        new_mmrs = [int(round(mmr)) for mmr in new_mmrs]
        
        return delta_MMRs, new_mmrs
    
    def _generate_results(self, players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate tournament results for all players."""
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
                "mii_data": player["mii_data"] if "mii_data" in player else ""
            }

            results.append(result)
    
        return results
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        import time
        timestamp = int(time.time())
        return f"LTRC_S1E{timestamp}"

    def get_next_event_id(self, season_number: int = 5) -> str:
        """Return the next sequential event ID for the given season."""
        season = f"LTRC_S{season_number}"
        season_dir = os.path.join(self.base_dir, "database", season)

        highest_event = 0
        if os.path.isdir(season_dir):
            for filename in os.listdir(season_dir):
                if not filename.endswith(".json"):
                    continue
                match = filename.removesuffix(".json")
                prefix = f"{season}E"
                if not match.startswith(prefix):
                    continue
                suffix = match[len(prefix):]
                if suffix.isdigit():
                    highest_event = max(highest_event, int(suffix))

        return f"{season}E{highest_event + 1}"
    
    def update_google_sheets(self, event_id: str, update_placements: bool = True, 
                           update_playerdata: bool = True) -> Dict[str, Any]:
        """
        Update Google Sheets with tournament data.
        This method delegates to the SheetsManager service for the Google Sheets update.
        
        Args:
            event_id: Unique event identifier
            update_placements: Whether to update placements sheet
            update_playerdata: Whether to update player data sheet
            
        Returns:
            Dict containing update results
        """
        try:
            logger.info(f"Updating Google Sheets for event: {event_id}")
            
            # Import SheetsManager only when it is needed.
            from app.services.sheets_manager import SheetsManager
            
            # Initialise the sheets manager.
            sheets_manager = SheetsManager()
            
            season = event_id.split('E')[0]
            json_path = os.path.join(self.base_dir, "database", season, f"{event_id}.json")
            with open(json_path, 'r') as json_file:
                saved_results = json.load(json_file)

            result = sheets_manager.update_sheets(
                event_id=event_id,
                results=saved_results.get("results", [])
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating Google Sheets: {str(e)}")
            raise
    
    def check_sheets_status(self) -> Dict[str, Any]:
        """Check Google Sheets connection and lock status."""
        try:
            logger.info("Checking Google Sheets status")
            
            # Import SheetsManager only when it is needed.
            from app.services.sheets_manager import SheetsManager
            
            # Initialise the sheets manager.
            sheets_manager = SheetsManager()
            
            # Use the sheets manager to check status
            status = sheets_manager.get_sheets_status()
            
            return status
            
        except Exception as e:
            logger.error(f"Error checking sheets status: {str(e)}")
            raise
