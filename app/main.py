from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import ltrc, images, sheets
from app.utils.logging import setup_logging

logger = setup_logging()

app = FastAPI(
    title="LTRC Manager API",
    description="Backend API service for managing LTRC results",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ltrc.router, prefix="/ltrc", tags=["LTRC Processing"])
app.include_router(images.router, prefix="/ltrc", tags=["Image Generation"])
app.include_router(sheets.router, prefix="/ltrc", tags=["Google Sheets Integration"])

@app.on_event("startup")
async def startup_event():
    logger.info("LTRC Manager API starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("LTRC Manager API shutting down...")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error", "details": str(exc)}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTP error", "message": exc.detail}
    )

@app.get("/")
async def root():
    return {"message": "LTRC Manager API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "LTRC Manager API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
