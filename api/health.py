"""
Health check endpoints.
"""

from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime

from services.session_manager import get_session_manager


router = APIRouter(prefix="/health", tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    active_sessions: int
    version: str = "1.0.0"


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Check if the API is running and healthy."
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    Returns basic health information about the service.
    """
    session_manager = get_session_manager()
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        active_sessions=session_manager.get_active_session_count(),
        version="1.0.0"
    )


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict:
    """
    Readiness probe for container orchestration.
    """
    return {"ready": True}


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_check() -> dict:
    """
    Liveness probe for container orchestration.
    """
    return {"alive": True}
