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

@router.get("/formats", summary="Get supported image formats")
async def get_supported_formats(image_gen: ImageGenerator = Depends(get_image_generator)):
    """
    Get a list of supported tournament formats for image generation.
    
    Returns the available formats and their configuration details.
    """
    try:
        formats = list(image_gen.format_config['formats'].keys())
        return {
            "supported_formats": formats,
            "message": f"Found {len(formats)} supported formats",
            "formats": {
                fmt: {
                    "podium_count": image_gen.format_config['formats'][fmt]['podium_count'],
                    "team_size": image_gen.format_config['formats'][fmt]['team_size'],
                    "description": f"{image_gen.format_config['formats'][fmt]['team_size']}v{image_gen.format_config['formats'][fmt]['team_size']} or FFA"
                } for fmt in formats
            }
        }
    except Exception as e:
        logger.error(f"Error getting supported formats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get supported formats: {str(e)}")

@router.get("/config", summary="Get current image generation configuration")
async def get_image_config(image_gen: ImageGenerator = Depends(get_image_generator)):
    """
    Get the current image generation configuration.
    
    Returns the configuration used for image generation including colors, fonts, and layout settings.
    """
    try:
        return {
            "width": image_gen.width,
            "height": image_gen.height,
            "font_file": image_gen.font_file,
            "background_color": image_gen.colors.get('background_color', '#000000'),
            "colors": image_gen.colors,
            "formats": list(image_gen.format_config['formats'].keys()),
            "message": "Current image generation configuration"
        }
    except Exception as e:
        logger.error(f"Error getting image config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get image config: {str(e)}")

@router.post("/test", response_class=StreamingResponse, summary="Test image generation with sample data")
async def test_image_generation(image_gen: ImageGenerator = Depends(get_image_generator)):
    """
    Generate a test image with sample data to verify the image generation functionality.
    
    This endpoint creates a sample tournament result image with dummy data for testing purposes.
    """
    try:
        sample_results = [
            {
                "name": "Player 1",
                "score": 160,
                "mmr_change": 50,
                "new_mmr": 2050,
                "completion": "3/3",
                "mii_data": "AAYiHgBCAGwAYQB6AGkAYwBvIh4AAEFAiRgSycIKnXVMAG5BIb0oojyMSEgUSbhucIoAiiUFAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            },
            {
                "name": "Player 2",
                "score": 140,
                "mmr_change": -20,
                "new_mmr": 1980,
                "completion": "3/3",
                "mii_data": "AAYiHgBCAGwAYQB6AGkAYwBvIh4AAEFAiRgSycIKnXVMAG5BIb0oojyMSEgUSbhucIoAiiUFAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            },
            {
                "name": "Player 3",
                "score": 120,
                "mmr_change": 30,
                "new_mmr": 2030,
                "completion": "3/3",
                "mii_data": "AAYiHgBCAGwAYQB6AGkAYwBvIh4AAEFAiRgSycIKnXVMAG5BIb0oojyMSEgUSbhucIoAiiUFAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            },
            {
                "name": "Player 4",
                "score": 100,
                "mmr_change": -10,
                "new_mmr": 1990,
                "completion": "3/3",
                "mii_data": "AAYiHgBCAGwAYQB6AGkAYwBvIh4AAEFAiRgSycIKnXVMAG5BIb0oojyMSEgUSbhucIoAiiUFAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            }
        ]
        
        img = image_gen.generate(
            results=sample_results
        )
        
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        img_bytes = img_buffer.getvalue()
        
        return StreamingResponse(
            io.BytesIO(img_bytes),
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename=test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                "X-Image-Format": "PNG",
                "X-Image-Size": str(len(img_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating test image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate test image: {str(e)}")

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
