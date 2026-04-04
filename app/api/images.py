from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional, Dict, Any, List
from datetime import datetime
import io
import os
import json
import logging

from app.models.image import ImageGenerationRequest, ImageGenerationResponse, PlayerResult, ImageGenerationStatus
from app.services.image_generator import ImageGenerator
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/images", tags=["Image Generation"])
image_generator = None

def load_config():
    """Load configuration from config.json"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'config.json')
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load configuration: {str(e)}")

def get_image_generator(format_type: str = 'FFA'):
    """Get the image generator instance for a specific format"""
    config = load_config()
    return ImageGenerator(format_type, config)

@router.get("/generate/{event_id}", response_class=StreamingResponse, summary="Generate tournament result image")
async def generate_image(
    event_id: str
):
    """
    Generate or retrieve tournament result image from saved results.
    Requires existing results file in database directory.
    
    Steps:
    1. Check if results exist for event_id
    2. Load saved tournament results
    3. Generate/retrieve image using ImageGenerator
    4. Return existing image or newly generated image
    
    Returns 404 if results not found
    """
    try:
        # Check if results exist with season folder structure
        season = event_id.split('E')[0]
        json_path = os.path.join("database", season, f"{event_id}.json")
        if not os.path.exists(json_path):
            raise HTTPException(status_code=404, detail=f"Results not found for event {event_id}")
        
        # Load results data
        with open(json_path, 'r') as f:
            results_data = json.load(f)
        
        # Safely extract required fields with defaults
        format_type = results_data.get("mode")
        event_date = results_data.get("event_date", "")  # Default to empty string
        players = results_data.get("results", [])

        # Validate required fields exist
        if not format_type:
            raise HTTPException(status_code=500, detail="Missing tournament mode in results")
        if not players:
            raise HTTPException(status_code=500, detail="No player results found")
        
        # Create image generator with the correct format type from results
        image_gen = get_image_generator(format_type)
        
        # Generate image using loaded data
        img = image_gen.generate_or_retrieve(
            results=[{
                "name": player["name"],
                "score": player["score"],
                "mmr_change": player["mmr_change"],
                "new_mmr": player["new_mmr"],
                "completion": player["completion"],
                "mii_data": player.get("mii_data", "")
            } for player in players],
            event_id=event_id,
            event_date=event_date
        )
        
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_bytes = img_buffer.getvalue()
        
        return StreamingResponse(
            img_buffer,
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={event_id}.png",
                "X-Image-Format": "PNG",
                "X-Image-Size": str(img_buffer.getbuffer().nbytes)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating/retrieving image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate/retrieve image: {str(e)}")
