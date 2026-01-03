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

def get_image_generator():
    """Get the global image generator instance"""
    global image_generator
    if image_generator is None:
        config = load_config()
        image_generator = ImageGenerator('FFA', config)
    return image_generator

@router.post("/generate", response_class=StreamingResponse, summary="Generate tournament result image")
async def generate_image(
    request: ImageGenerationRequest,
    image_gen: ImageGenerator = Depends(get_image_generator)
):
    """
    Generate or retrieve a tournament result image with player information, MMR changes, and automatic formatting.
    First tries to retrieve an existing image, otherwise generates and saves a new one.
    
    This endpoint creates a professional tournament result image with:
    - Player names and scores
    - MMR changes with color coding (green for positive, red for negative)
    - Rank progression indicators
    - Placement completion status (1/3, 2/3, 3/3)
    - Mii images for players (if available)
    - Professional podium layout for top 3 positions
    - Multi-format support (FFA, 2vs2, 4vs4, 5v5, 6v6)
    - Automatic subtitle generation with event number and date
    - Persistent storage in results_images folder organized by season
    """
    try:
        logger.info(f"Generating/retrieving image for format: {request.format_type}, results: {len(request.results)} players, event: {request.event_id}")
        
        if request.format_type not in image_gen.format_config['formats']:
            raise HTTPException(status_code=400, detail=f"Invalid format type: {request.format_type}")
        
        if not request.results:
            raise HTTPException(status_code=400, detail="Results list cannot be empty")
        
        # Use the new generate_or_retrieve method that handles storage and retrieval
        img = image_gen.generate_or_retrieve(
            results=[{
                "name": player.name,
                "score": player.score,
                "mmr_change": player.mmr_change,
                "new_mmr": player.new_mmr,
                "completion": player.completion,
                "mii_data": player.mii_data
            } for player in request.results],
            event_id=request.event_id,
            event_date=request.event_date
        )
        
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_bytes = img_buffer.getvalue()
        
        return StreamingResponse(
            io.BytesIO(img_bytes),
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename=tournament_results_{request.format_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                "X-Image-Format": "PNG",
                "X-Image-Size": str(len(img_bytes))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating/retrieving image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate/retrieve image: {str(e)}")

@router.get("/health", summary="Check image generation service health")
async def image_generation_health(image_gen: ImageGenerator = Depends(get_image_generator)):
    """
    Check the health of the image generation service.
    
    Returns the status of the image generation service and its configuration.
    """
    try:
        return {
            "status": "healthy",
            "service": "image_generation",
            "formats_supported": len(image_gen.format_config['formats']),
            "configuration_loaded": True,
            "message": "Image generation service is ready"
        }
    except Exception as e:
        logger.error(f"Error checking image generation health: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
