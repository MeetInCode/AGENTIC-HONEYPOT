"""
Agentic Honeypot — Main Entry Point
A single-endpoint AI honeypot that detects scam messages,
engages scammers with believable personas, extracts intelligence,
and sends results to the GUVI evaluation endpoint.
"""

import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
# Force reload

# Load environment variables FIRST
load_dotenv()

from config.settings import get_settings
from api.honeypot import router as honeypot_router

# ─── Logging ──────────────────────────────────────────────────────

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("=" * 60)
    logger.info("🍯 Agentic Honeypot starting up")
    logger.info(f"   Endpoint: POST /honeypot/message")
    logger.info(f"   Callback: {settings.guvi_callback_url}")
    logger.info(f"   Inactivity timeout: {settings.inactivity_timeout_seconds}s")
    logger.info(f"   NVIDIA models: nemotron, deepseek-v3, minimax-m2")
    logger.info(f"   Groq models: llama-4-scout, gpt-oss-120b")
    logger.info("=" * 60)
    yield
    logger.info("🍯 Agentic Honeypot shutting down")


# ─── App ──────────────────────────────────────────────────────────

app = FastAPI(
    title="Agentic Honeypot API",
    description=(
        "AI-powered honeypot that detects scam messages, engages scammers "
        "with believable personas, and extracts intelligence. "
        "Single endpoint: POST /honeypot/message"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)[:200]},
    )


# Health endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "agentic-honeypot",
        "version": "2.0.0",
    }


# Mount honeypot router (no prefix — endpoint is /honeypot/message)
app.include_router(honeypot_router)


# ─── Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", settings.port))
    workers = int(os.environ.get("WORKERS", 4))
    
    # Production: Use multiple workers for better concurrency
    # Development: Single worker with reload
    if settings.debug:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            reload=True,
            log_level=settings.log_level.lower(),
        )
    else:
        # Production mode: multiple workers for concurrent request handling
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            workers=workers,
            log_level=settings.log_level.lower(),
            access_log=True,
        )
