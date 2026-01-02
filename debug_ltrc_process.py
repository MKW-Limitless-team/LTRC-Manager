#!/usr/bin/env python3
"""
Simple debug script for LTRC processor
Loads data from example_json.json and processes it directly
Use this with your IDE's debugger (VS Code, PyCharm, etc.)
"""

import sys
import os
import json
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load_test_payload():
    """Load test payload from example_json.json"""
    try:
        with open('example_json.json', 'r') as f:
            payload = json.load(f)
        print(f"Loaded payload from example_json.json")
        print(f"Mode: {payload.get('mode', 'Unknown')}")
        print(f"Players: {len(payload.get('players', []))}")
        print(f"Event Date: {payload.get('event_date', 'Unknown')}")
        return payload
    except FileNotFoundError:
        print("example_json.json not found")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None

def debug_ltrc_processor():
    """Debug the LTRC processor directly"""
    print("LTRC Processor Debug Script")
    print("=" * 50)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load payload
    payload = load_test_payload()
    if not payload:
        return

    try:
        from app.services.ltrc_processor import LTRCProcessor

        # Create processor instance
        processor = LTRCProcessor()

        # Set a breakpoint here in your IDE to start debugging
        # The debugger will stop at this line when you run this script
        print("\nReady for debugging. Set breakpoint in your IDE and start debugging.")
        print("The script will process the tournament data step by step.")

        # Process tournament - set breakpoint here or step through with debugger
    result = processor.process_tournament(
        event_id=payload['event_id'],
        mode=payload['mode'],
        players=payload['players'],
        options=payload['options'],
        event_date=payload['event_date']
    )

        print("\nTournament processed successfully!")
        print(f"Event ID: {result['event_id']}")
        print(f"Results count: {len(result['results'])}")

        # Show results
        print("\nResults:")
        for i, player_result in enumerate(result['results']):
            print(f"  {i+1}. {player_result['name']}: {player_result['score']} pts, MMR {player_result['old_mmr']} -> {player_result['new_mmr']} ({player_result['mmr_change']:+})")

        return result

    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_ltrc_processor()
