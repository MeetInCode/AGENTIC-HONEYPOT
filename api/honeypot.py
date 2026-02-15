"""
Honeypot API — POST /honeypot/message
PRD-aligned single endpoint with x-api-key auth.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Header, status
from models.schemas import HoneypotRequest, HoneypotResponse, Message, Metadata
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
    try:
        logger.info(
            f"Incoming message: session={request.sessionId}, "
            f"sender={request.message.sender}, "
            f"text='{request.message.text[:80]}...'"
        )
        
        # Validate request
        if not request.message.text or not request.message.text.strip():
            logger.warning(f"Empty message text for session {request.sessionId}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message text cannot be empty"
            )
        
        if len(request.message.text) > 10000:
            logger.warning(f"Message too long for session {request.sessionId}: {len(request.message.text)} chars")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message text exceeds maximum length of 10000 characters"
            )
        
        # Drop timestamps from the payload before it enters the core pipeline to
        # keep downstream objects (session state + LLM prompts) as lean as possible.
        # The external schema still accepts/validates a timestamp field, but we do
        # not propagate those values internally.
        sanitized_history = [
            {
                "sender": h.get("sender"),
                "text": h.get("text", ""),
            }
            for h in (request.conversationHistory or [])
        ]
        sanitized_message = Message(
            sender=request.message.sender,
            text=request.message.text,
            # Use a trivial placeholder; internal logic never reads this value.
            timestamp=0,
        )
        sanitized_request = HoneypotRequest(
            sessionId=request.sessionId,
            message=sanitized_message,
            conversationHistory=sanitized_history,
            metadata=request.metadata,
        )

        orchestrator = get_orchestrator()
        response = await orchestrator.process_message(sanitized_request)

        logger.info(
            f"Response: session={request.sessionId}, "
            f"status={response.status}, "
            f"reply='{(response.reply or '')[:60]}...'"
        )

        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing message for session {request.sessionId}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )
