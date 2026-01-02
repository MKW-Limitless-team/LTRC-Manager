# LTRC Manager API Documentation

## Overview

The LTRC Manager is a backend API service for managing Mario Kart tournament results. The API provides RESTful endpoints for calculating MMR changes, updating Google Sheets, and generating professional tournament result images. This is a pure backend service designed to be consumed by external frontend applications.

## Table of Contents

1. [API Reference](#api-reference)
2. [Data Formats](#data-formats)
3. [Multi-Instance Handling](#multi-instance-handling)
4. [Error Handling](#error-handling)
5. [Examples](#examples)
6. [Deployment](#deployment)

## API Reference

### Base URL

```
http://localhost:8000
```

### Authentication

Currently no authentication is required. For production use, consider adding API key authentication.

### Endpoints

#### LTRC Processing

##### Process Tournament Results

```
POST /ltrc/process
```

Process tournament results and calculate MMR changes.

**Request Body:**

```json
{
  "mode": "FFA",
  "players": [
    {
      "name": "Player1",
      "score": 1500,
      "mii_data": "base64_encoded_mii_image"
    },
    {
      "name": "Player2",
      "score": 1200,
      "mii_data": "base64_encoded_mii_image"
    }
  ],
  "options": {
    "32track": false,
    "200cc": false,
    "ott": false
  },
  "event_date": "2025-01-31"
}
```

**Response:**

```json
{
  "event_id": "LTRC_S1E1",
  "mode": "FFA",
  "processed_at": "2025-01-31T14:30:22Z",
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
      "mii_data": "base64_encoded_mii_image"
    }
  ],
  "image_generated": true,
  "image_url": "/ltrc/images/LTRC_S1E1.png"
}
```

**Status Codes:**
- 200: Success
- 400: Invalid request data
- 500: Internal server error

##### Get Tournament Results

```
GET /ltrc/results/{event_id}
```

Retrieve processed tournament results by ID.

**Response:**

```json
{
  "event_id": "LTRC_S1E1",
  "mode": "FFA",
  "processed_at": "2025-01-31T14:30:22Z",
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
      "mii_data": "base64_encoded_mii_image"
    }
  ],
  "image_generated": true,
  "image_url": "/ltrc/images/LTRC_S1E1.png"
}
```

**Status Codes:**
- 200: Success
- 404: Event not found

##### Get Processing Status

```
GET /ltrc/status
```

Get current processing status and system information.

**Response:**

```json
{
  "status": "ready",
  "sheets_locked": false,
  "locked_by": null,
  "last_processed": "2025-01-31T14:30:22Z",
  "active_instances": 1,
  "supported_formats": ["FFA", "2vs2", "3vs3", "4vs4", "5vs5", "6vs6"]
}
```

**Status Codes:**
- 200: Success

#### Image Generation

##### Generate Tournament Image

```
POST /images/generate
```

Generate a professional tournament result image with player information, MMR changes, and automatic formatting.

**Request Body:**

```json
{
  "format_type": "FFA",
  "results": [
    {
      "name": "Player 1",
      "score": 1000,
      "mmr_change": 50,
      "new_mmr": 2050,
      "completion": "3/3",
      "mii_data": "base64_encoded_mii_data"
    }
  ],
  "event_id": "LTRC_S1E15",
  "event_date": "25-12-2025"
}
```

**Response:**
Binary image data (PNG format) with appropriate content-type header (`image/png`).

**Status Codes:**
- 200: Success (image generated)
- 400: Invalid request (invalid format type or empty results)
- 500: Image generation failed

**Features:**
- Player names and scores
- MMR changes with color coding (green for positive, red for negative)
- Rank progression indicators
- Placement completion status (1/3, 2/3, 3/3)
- Mii images for players (if available)
- Professional podium layout for top 3 positions
- Multi-format support (FFA, 2vs2, 4vs4, 5v5, 6v6)
- Automatic subtitle generation with event number and date

##### Get Supported Image Formats

```
GET /images/formats
```

Get a list of supported tournament formats for image generation.

**Response:**

```json
{
  "supported_formats": ["FFA", "2vs2", "4vs4", "5v5", "6v6"],
  "message": "Found 5 supported formats",
  "formats": {
    "FFA": {
      "podium_count": 3,
      "team_size": 1,
      "description": "1v1 or FFA"
    }
  }
}
```

**Status Codes:**
- 200: Success

##### Get Image Generation Configuration

```
GET /images/config
```

Get the current image generation configuration.

**Response:**

```json
{
  "width": 1200,
  "height": 800,
  "font_file": "Knewave-Regular.ttf",
  "background_color": "#000000",
  "colors": {
    "positions": {
      "1": "#FFD700",
      "2": "#C0C0C0",
      "3": "#CD7F32",
      "default": "#FFFFFF"
    },
    "mmr_up": "#00FF00",
    "mmr_down": "#FF0000",
    "gold": "#FFD700"
  },
  "formats": ["FFA", "2vs2", "4vs4", "5v5", "6v6"],
  "message": "Current image generation configuration"
}
```

**Status Codes:**
- 200: Success

##### Test Image Generation

```
POST /images/test
```

Generate a test image with sample data to verify the image generation functionality.

**Response:** Binary PNG image data with sample tournament results

**Status Codes:**
- 200: Success (test image generated)

##### Check Image Generation Health

```
GET /images/health
```

Check the health of the image generation service.

**Response:**

```json
{
  "status": "healthy",
  "service": "image_generation",
  "formats_supported": 5,
  "configuration_loaded": true,
  "message": "Image generation service is ready"
}
```

**Status Codes:**
- 200: Success


#### Google Sheets Integration

##### Update Google Sheets

```
POST /sheets/update
```

Update Google Sheets with tournament data. Only one update can be processed at a time - if another update is in progress, returns a busy error.

**Request Body:**

```json
{
  "event_id": "LTRC_S1E123",
  "results": [
    {
      "name": "Player1",
      "score": 1500,
      "new_mmr": 4650,
      "mmr_change": 150
    },
    {
      "name": "Player2",
      "score": 1200,
      "new_mmr": 4150,
      "mmr_change": -50
    }
  ]
}
```

**Response:**

```json
{
  "success": true,
  "updated_cells": 12,
  "timestamp": "2025-01-31T15:30:00",
  "message": "Sheet updated successfully"
}
```

**Status Codes:**
- 200: Success
- 400: Invalid request (missing event_id or results)
- 423: Sheet is busy (another update in progress)
- 500: Sheets update failed

**Notes:**
- `name`: Player's name (must match Google Sheets)
- `score`: Player's tournament score
- `new_mmr`: Player's MMR after the tournament
- `mmr_change`: MMR change (positive or negative)

##### Check Sheets Status

```
GET /sheets/status
```

Check Google Sheets connection and lock status.

**Response:**

```json
{
  "connected": true,
  "sheet_name": "LTRC",
  "locked": false,
  "locked_by": null,
  "last_update": "2025-01-31T14:35:00Z",
  "error": null
}
```

**Status Codes:**


## Data Formats

### Player Data

```json
{
  "name": "PlayerName",
  "score": 1500,
  "mii_data": "base64_encoded_image_data"
}
```

**Fields:**
- `name` (string): Player's display name
- `score` (integer): Player's score in the tournament
- `mii_data` (string): Base64-encoded Mii image data

### Tournament Options

```json
{
  "32track": false,
  "200cc": false,
  "ott": false
}
```

**Fields:**
- `32track` (boolean): Enable 32-track mode (MMR gains multiplied by 2.67, losses by 0.67)
- `200cc` (boolean): Enable 200cc mode (losses halved)
- `ott` (boolean): Enable OTT mode (special rules)

### Event Information

```json
{
  "event_date": "31-01-2025"
}
```

**Fields:**
- `event_date` (string): Date when the event was held (DD-MM-YYYY format)

### Tournament Result

```json
{
  "name": "PlayerName",
  "score": 1500,
  "old_mmr": 4500,
  "new_mmr": 4650,
  "mmr_change": 150,
  "rank": "Gold",
  "rank_change": "up",
  "completion": "3/3",
  "mii_data": "base64_encoded_image_data"
}
```

**Fields:**
- `name` (string): Player's name
- `score` (integer): Player's score
- `old_mmr` (integer): Player's MMR before the tournament
- `new_mmr` (integer): Player's MMR after the tournament
- `mmr_change` (integer): MMR change (can be negative)
- `rank` (string): Player's rank (Tin, Bronze, Silver, Gold, Emerald, Sapphire, Ruby, Duke, Master, Grandmaster, Monarch, Sovereign)
- `rank_change` (string): Rank change direction ("up", "down", "neutral", "right")
- `completion` (string): Placement completion status ("1/3", "2/3", "3/3", or empty for placed players)
- `mii_data` (string): Base64-encoded Mii image data

## Multi-Instance Handling

### Google Sheets Locking

The application implements a distributed locking mechanism to prevent concurrent access to Google Sheets:

1. **Single Update at a Time**: Only one sheets update can be processed simultaneously
2. **Busy Error**: If an update is requested while another is in progress, returns HTTP 423 (Locked)
3. **Automatic Cleanup**: Locks are released when updates complete or fail

### Lock States

- **Available**: No update is currently in progress
- **Busy**: Another update is currently being processed
- **Error**: Previous update failed and lock needs cleanup

### Status API

The `/sheets/status` endpoint provides information about current locks and active instances.

## Error Handling

### Common Errors

#### Google Sheets Errors
- **401 Unauthorized**: Invalid or missing credentials
- **403 Forbidden**: Missing permissions for the sheet
- **423 Locked**: Sheet is busy (another update in progress)
- **429 Too Many Requests**: Rate limiting exceeded
- **500 Internal Server Error**: Google Sheets API error

#### Processing Errors
- **400 Bad Request**: Invalid tournament data
- **422 Unprocessable Entity**: Data validation failed
- **500 Internal Server Error**: Processing error

#### Image Generation Errors
- **404 Not Found**: Tournament data not found
- **500 Internal Server Error**: Image generation failed

### Error Response Format

```json
{
  "error": "Error description",
  "code": "ERROR_CODE",
  "details": {
    "field": "Additional error details"
  }
}
```

## Examples

### Basic Tournament Processing

```python
import requests
import json

# Tournament data
data = {
    "mode": "FFA",
    "players": [
        {"name": "Player1", "score": 1500, "mii_data": ""},
        {"name": "Player2", "score": 1200, "mii_data": ""},
        {"name": "Player3", "score": 900, "mii_data": ""}
    ],
    "options": {
        "32track": False,
        "200cc": False,
        "ott": False
    },
    "event_date": "31-01-2025"
}

# Process tournament
response = requests.post("http://localhost:8000/ltrc/process", json=data)
result = response.json()

print(f"Event ID: {result['event_id']}")
print(f"Image URL: {result['image_url']}")
```

### Image Generation Only

```python
# Generate or retrieve image for existing tournament
# No request body needed - the endpoint uses stored tournament data including event_date

# Make POST request to the image endpoint with event_id in URL
response = requests.post("http://localhost:8000/ltrc/images/LTRC_S1E1")

# The response contains the actual image data (binary PNG)
if response.status_code == 200:
    # Save the image to a file
    with open("tournament_image.png", "wb") as f:
        f.write(response.content)
    print("Image saved successfully")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### Sheets Update with Results

```python
# Update Google Sheets with tournament results
sheets_data = {
    "event_id": "LTRC_S1E123",
    "results": [
        {
            "name": "Player1",
            "score": 1500,
            "new_mmr": 4650,
            "mmr_change": 150
        },
        {
            "name": "Player2",
            "score": 1200,
            "new_mmr": 4150,
            "mmr_change": -50
        }
    ]
}

response = requests.post("http://localhost:8000/sheets/update", json=sheets_data)

if response.status_code == 200:
    print("Sheets updated successfully")
elif response.status_code == 423:
    print("Sheets are busy - another update in progress")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### Status Monitoring

```python
# Check system status
response = requests.get("http://localhost:8000/ltrc/status")
status = response.json()

if status['sheets_locked']:
    print(f"Sheet locked by: {status['locked_by']}")
else:
    print("Sheet is available for processing")
```

## Deployment

### Prerequisites

- Python 3.8 or higher
- Google Sheets API credentials file (`auto-mmr-calculator-9676e1429d9a.json`)
- Access to Google Sheets document

### Installation

Install required packages:

```bash
pip install -r requirements.txt
```

Required packages:
- fastapi
- uvicorn[standard]
- pydantic
- pydantic-settings
- pillow
- requests
- gspread
- google-auth
- numpy

### Running the Application

```bash
# Run with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Environment Variables

- `LTRC_HOST`: API host (default: 0.0.0.0)
- `LTRC_PORT`: API port (default: 8000)
- `LTRC_DEBUG`: Enable debug mode (default: False)

### Production Deployment

For production use, consider:
- Using a production WSGI server (e.g., Gunicorn)
- Setting up reverse proxy (e.g., Nginx)
- Adding authentication and rate limiting
- Configuring proper logging
- Setting up monitoring and health checks

## Project Structure

```
LTRC-Manager/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── models/              # Pydantic models
│   │   ├── base.py
│   │   ├── ltrc.py
│   │   ├── image.py
│   │   └── sheets.py
│   ├── services/            # Business logic
│   │   ├── ltrc_processor.py
│   │   ├── image_generator.py
│   │   └── sheets_manager.py
│   ├── api/                 # API route definitions
│   │   ├── ltrc.py
│   │   ├── images.py
│   │   └── sheets.py
│   └── utils/               # Utility functions
├── model.py                 # Original LTRC model
├── MMR.py                   # MMR calculation engine
├── imagegen.py              # Image generation
├── config.json              # Application configuration
└── requirements.txt         # Python dependencies
```

### Adding New Features

1. **Create Pydantic Models**: Define request/response schemas
2. **Implement Services**: Add business logic to services
3. **Create API Routes**: Add endpoints to API modules
4. **Update Documentation**: Add examples and descriptions

### Testing

The application includes comprehensive error handling and status monitoring. For production use:

1. Monitor the `/ltrc/status` endpoint
2. Implement retry logic for failed requests
3. Handle rate limiting appropriately
4. Monitor Google Sheets API quotas

## Support

For issues and support:
- Check the application logs
- Verify Google Sheets permissions
- Ensure all required files are present
- Monitor the status endpoint for system health

## License

This project is licensed under the MIT License.
