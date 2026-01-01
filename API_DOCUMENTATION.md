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

##### Generate or Retrieve Tournament Image

```
POST /ltrc/images/{event_id}
```

Generate a tournament result image if it doesn't exist, or retrieve the existing image. This endpoint handles both image generation and acquisition in a single POST request.

**Request Body:** None required

**Response:**
Binary image data (PNG format) with appropriate content-type header (`image/png`).

**Status Codes:**
- 200: Success (image generated or retrieved)
- 404: Event not found
- 500: Image generation failed

**Notes:**
- If the image for the specified event already exists, it will be returned directly
- If the image doesn't exist, it will be generated on-demand and then returned
- The response contains the actual image data, not file paths or URLs
- Images are cached after generation to improve performance for subsequent requests
- Image generation uses the event_date and other stored tournament data for customization

#### Google Sheets Integration

##### Update Google Sheets

```
POST /ltrc/sheets/update
```

Update Google Sheets with tournament data.

**Request Body:**

```json
{
  "event_id": "LTRC_S1E1",
  "update_placements": true,
  "update_playerdata": true
}
```

**Response:**

```json
{
  "success": true,
  "updated_cells": 45,
  "timestamp": "2025-01-31T14:35:00Z",
  "message": "Sheet updated successfully"
}
```

**Status Codes:**
- 200: Success
- 400: Invalid request
- 500: Sheets update failed

##### Check Sheets Status

```
GET /ltrc/sheets/status
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
- 200: Success


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

1. **Lock Cell**: Uses cell Z1 as a lock indicator
2. **Instance ID**: Each instance generates a unique ID
3. **Timeout**: Locks expire after 5 minutes of inactivity
4. **Cleanup**: Locks are automatically released on instance shutdown

### Lock States

- **Unlocked**: No instance is currently processing
- **Locked**: Another instance is processing
- **Expired**: Lock exists but is older than timeout

### Status API

The `/ltrc/status` endpoint provides information about current locks and active instances.

## Error Handling

### Common Errors

#### Google Sheets Errors
- **401 Unauthorized**: Invalid or missing credentials
- **403 Forbidden**: Missing permissions for the sheet
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
