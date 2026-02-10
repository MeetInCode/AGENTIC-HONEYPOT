"""
Honeypot API — POST /honeypot/message
PRD-aligned single endpoint with x-api-key auth.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Header, status
from models.schemas import HoneypotRequest, HoneypotResponse
from core.orchestrator import HoneypotOrchestrator
from config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Honeypot"])

# Singleton orchestrator — initialized on first request
_orchestrator: HoneypotOrchestrator = None


def get_orchestrator() -> HoneypotOrchestrator:
    """Get or create the orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = HoneypotOrchestrator()
    return _orchestrator


async def verify_api_key(x_api_key: str = Header(..., alias="x-api-key")) -> str:
    """Validate the API key from request header."""
    settings = get_settings()
    if x_api_key != settings.api_secret_key:
        logger.warning(f"Invalid API key attempt: {x_api_key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key


@router.post(
    "/honeypot/message",
    response_model=HoneypotResponse,
    status_code=status.HTTP_200_OK,
    summary="Process a scam message",
    description=(
        "Receives an incoming message, detects scam intent via a 5-model LLM council, "
        "and returns an immediate human-like engagement reply. Intelligence extraction "
        "and callback to GUVI happen asynchronously."
    ),
)
async def process_message(
    request: HoneypotRequest,
    api_key: str = Depends(verify_api_key),
) -> HoneypotResponse:
    """
    Main honeypot endpoint — PRD-aligned.
    
    Accepts a scam message, runs detection council,
    generates engagement reply, returns immediately.
    """
    logger.info(
        f"Incoming message: session={request.sessionId}, "
        f"sender={request.message.sender}, "
        f"text='{request.message.text[:80]}...'"
    )

    orchestrator = get_orchestrator()
    response = await orchestrator.process_message(request)

    logger.info(
        f"Response: session={response.sessionId}, "
        f"scam={response.scamDetected}, "
        f"conf={response.confidence:.2f}, "
        f"reply='{response.reply[:60]}...'"
    )

    return response
