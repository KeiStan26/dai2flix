"""FastAPI application entrypoint for Daini-group Netflix-style VOD.

Configures:
- Database initialization on startup (WAL mode and tables creation)
- Strict CORS policies for frontend development and production Apache2 proxy
- Defensive global exception handlers preventing internal stack trace disclosure
- Modular routers (/api/health, /api/v1/feed)
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app import __version__
from app.config import get_settings
from app.database import init_db
from app.routers import feed, health

# Configure root logger
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daini_vod_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown procedures."""
    logger.info("Starting Daini-group VOD API (v%s)...", __version__)
    try:
        init_db()
        logger.info("Database schema initialized and verified.")
    except Exception as e:
        logger.critical("Failed to initialize database during startup: %s", e, exc_info=True)
    yield
    logger.info("Shutting down Daini-group VOD API.")


app = FastAPI(
    title="Daini Group Netflix-style VOD API",
    description="Backend API for high-impact Netflix-style VOD application dedicated to Daini-group video assets.",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ------------------------------------------------------------------------------
# Security & CORS Middleware
# ------------------------------------------------------------------------------
allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Apply standard defense-in-depth HTTP security headers."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ------------------------------------------------------------------------------
# Global Defensive Exception Handler
# ------------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and prevent leaking stack traces or internal secrets."""
    logger.error("Unhandled exception processing request '%s %s': %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please contact administrator if problem persists."},
    )


# ------------------------------------------------------------------------------
# Routers Registration
# ------------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(feed.router)


@app.get("/", tags=["root"], summary="API Root / Welcome")
def root():
    """Welcome endpoint providing service metadata."""
    return {
        "service": "Daini Group Netflix-style VOD API",
        "version": __version__,
        "health": "/api/health",
        "feed": "/api/v1/feed",
        "docs": "/docs",
    }
