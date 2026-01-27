"""
Agentic Honeypot - Main Application Entry Point

An AI-powered honeypot system for scam detection and intelligence extraction.
"""

import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rich.console import Console
import uvicorn

from api.honeypot import router as honeypot_router
from api.health import router as health_router
from config.settings import get_settings
from services.session_manager import get_session_manager


console = Console()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Handles startup and shutdown events.
    """
    # Startup
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]🍯 AGENTIC HONEYPOT API[/bold cyan]")
    console.print("[dim]AI-Powered Scam Detection & Intelligence Extraction[/dim]")
    console.print("=" * 60)
    
    settings = get_settings()
    console.print(f"\n[bold]Configuration:[/bold]")
    console.print(f"  • Debug Mode: {settings.debug}")
    console.print(f"  • Log Level: {settings.log_level}")
    console.print(f"  • Scam Threshold: {settings.scam_confidence_threshold}")
    console.print(f"  • Max Turns: {settings.max_conversation_turns}")
    console.print("")
    
    # Start session cleanup task
    session_manager = get_session_manager()
    await session_manager.start_cleanup_task()
    
    yield
    
    # Shutdown
    console.print("\n[bold yellow]🛑 Shutting down...[/bold yellow]")
    await session_manager.stop_cleanup_task()
    console.print("[bold green]✅ Shutdown complete[/bold green]\n")


# Create FastAPI application
app = FastAPI(
    title="Agentic Honeypot API",
    description="""
## 🍯 Agentic Honeypot for Scam Detection & Intelligence Extraction

An AI-powered honeypot system that:
- **Detects** scam messages using a multi-model Detection Council
- **Engages** scammers autonomously using LangGraph-based agents
- **Extracts** actionable intelligence (UPI IDs, phone numbers, phishing links)
- **Reports** results to the GUVI evaluation endpoint

### Detection Council Members
- 🕵️‍♂️ **RuleGuard**: Rule-based heuristic engine
- 🧮 **FastML**: TF-IDF + RandomForest classifier
- 🤖 **BertLite**: DistilBERT transformer model
- 📜 **LexJudge**: LLM-based text classifier (Groq)
- 🔍 **OutlierSentinel**: SBERT anomaly detector
- 🧵 **ContextSeer**: LLM with conversation context
- 🧰 **MetaModerator**: Ensemble aggregator

### Authentication
All endpoints require `x-api-key` header for authentication.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# Add CORS middleware
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
    """Handle uncaught exceptions."""
    console.print(f"[bold red]❌ Unhandled exception: {exc}[/bold red]")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "An unexpected error occurred",
            "detail": str(exc)
        }
    )


# Include routers
app.include_router(health_router)
app.include_router(honeypot_router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Agentic Honeypot API",
        "version": "1.0.0",
        "description": "AI-Powered Scam Detection & Intelligence Extraction",
        "docs": "/docs",
        "health": "/health"
    }


def main():
    """Run the application."""
    settings = get_settings()
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
