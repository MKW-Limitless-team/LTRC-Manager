from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth, images, ltrc, sheets
from app.core.config import Settings, get_settings
from app.utils.logging import setup_logging

logger = setup_logging()

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title="LTRC Manager API",
        description="Backend API service for managing LTRC results",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie=settings.session_cookie_name,
        max_age=settings.session_max_age_seconds,
        same_site="lax",
        https_only=settings.is_production,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
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
            content={"error": "Validation error", "details": str(exc)},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request, exc):
        logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": "HTTP error", "message": exc.detail},
        )

    @app.get("/")
    async def root():
        return {"message": "LTRC Manager API is running", "version": "1.0.0"}

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "LTRC Manager API"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
