"""
Main Honeypot API endpoints.
Handles incoming scam messages and returns engagement responses.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import APIKeyHeader
from rich.console import Console
from typing import Optional

from models.schemas import HoneypotRequest, HoneypotResponse
from core.orchestrator import get_orchestrator, HoneypotOrchestrator
from config.settings import get_settings


router = APIRouter(prefix="/api/v1", tags=["Honeypot"])
console = Console()

# API Key authentication
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


async def verify_api_key(
    api_key: Optional[str] = Depends(api_key_header)
) -> str:
    """
    Verify the API key from request header.
    """
    settings = get_settings()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide x-api-key header."
        )
    
    if api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key."
        )
    
    return api_key


@router.post(
    "/analyze",
    response_model=HoneypotResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Message",
    description="Analyze an incoming message for scam intent and engage if detected.",
    responses={
        200: {
            "description": "Successful analysis and response",
            "model": HoneypotResponse
        },
        401: {"description": "Missing API key"},
        403: {"description": "Invalid API key"},
        500: {"description": "Internal server error"}
    }
)
async def analyze_message(
    request: HoneypotRequest,
    api_key: str = Depends(verify_api_key)
) -> HoneypotResponse:
    """
    Main endpoint for analyzing incoming messages.
    
    This endpoint:
    1. Receives a suspected scam message
    2. Runs it through the Detection Council (multi-model ensemble)
    3. If scam is detected, activates the AI engagement agent
    4. Extracts intelligence from the conversation
    5. Returns structured response with agent's reply
    
    The sessionId is used to track multi-turn conversations.
    """
    console.print(f"\n[bold blue]{'='*60}[/bold blue]")
    console.print(f"[bold blue]📥 Received request for session: {request.sessionId}[/bold blue]")
    console.print(f"[dim]Message: {request.message.text[:100]}...[/dim]" if len(request.message.text) > 100 else f"[dim]Message: {request.message.text}[/dim]")
    
    try:
        orchestrator = await get_orchestrator()
        response = await orchestrator.process_message(request)
        
        console.print(f"[bold green]✅ Response ready - Scam: {response.scamDetected}[/bold green]")
        console.print(f"[bold blue]{'='*60}[/bold blue]\n")
        
        return response
        
    except Exception as e:
        console.print(f"[bold red]❌ Error processing message: {e}[/bold red]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )


@router.post(
    "/callback/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Force Callback",
    description="Manually trigger the GUVI callback for a session."
)
async def force_callback(
    session_id: str,
    api_key: str = Depends(verify_api_key)
) -> dict:
    """
    Manually trigger the GUVI callback for a specific session.
    Useful for testing or forcing early callback submission.
    """
    try:
        orchestrator = await get_orchestrator()
        success = await orchestrator.force_callback(session_id)
        
        if success:
            return {"status": "success", "message": f"Callback sent for session {session_id}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending callback: {str(e)}"
        )


@router.get(
    "/sessions",
    status_code=status.HTTP_200_OK,
    summary="List Sessions",
    description="List all active sessions."
)
async def list_sessions(
    api_key: str = Depends(verify_api_key)
) -> dict:
    """
    List all currently active sessions.
    """
    from services.session_manager import get_session_manager
    
    session_manager = get_session_manager()
    sessions = session_manager.list_sessions()
    
    return {
        "active_sessions": len(sessions),
        "session_ids": sessions
    }


@router.get(
    "/session/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Get Session Details",
    description="Get details of a specific session."
)
async def get_session(
    session_id: str,
    api_key: str = Depends(verify_api_key)
) -> dict:
    """
    Get detailed information about a specific session.
    """
    from services.session_manager import get_session_manager
    
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    
    return {
        "session_id": session.session_id,
        "is_scam_detected": session.is_scam_detected,
        "total_messages": session.total_messages,
        "duration_seconds": session.get_duration_seconds(),
        "callback_sent": session.callback_sent,
        "extracted_intelligence": session.extracted_intelligence.model_dump(),
        "agent_notes": session.agent_notes
    }
