"""API routes for Agentic Honeypot."""

from .honeypot import router as honeypot_router
from .health import router as health_router

__all__ = [
    "honeypot_router",
    "health_router",
]
