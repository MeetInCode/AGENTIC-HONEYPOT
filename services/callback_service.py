"""
Callback Service for GUVI Evaluation Endpoint.
Handles mandatory result submission.
"""

import httpx
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.console import Console

from models.schemas import CallbackPayload, ExtractedIntelligence, SessionState
from config.settings import get_settings


console = Console()


class CallbackService:
    """
    Handles the mandatory final result callback to GUVI evaluation endpoint.
    Implements retry logic for reliability.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.callback_url = self.settings.guvi_callback_url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def send_final_result(
        self,
        session_id: str,
        scam_detected: bool,
        total_messages: int,
        intelligence: ExtractedIntelligence,
        agent_notes: str
    ) -> tuple[bool, str]:
        """
        Send the final result to GUVI evaluation endpoint.
        
        Args:
            session_id: Unique session identifier
            scam_detected: Whether scam was confirmed
            total_messages: Total messages exchanged
            intelligence: Extracted intelligence data
            agent_notes: Summary notes from the agent
            
        Returns:
            True if callback was successful
        """
        # Build the payload
        payload = CallbackPayload(
            sessionId=session_id,
            scamDetected=scam_detected,
            totalMessagesExchanged=total_messages,
            extractedIntelligence={
                "bankAccounts": intelligence.bankAccounts,
                "upiIds": intelligence.upiIds,
                "phishingLinks": intelligence.phishingLinks,
                "phoneNumbers": intelligence.phoneNumbers,
                "suspiciousKeywords": intelligence.suspiciousKeywords,
            },
            agentNotes=agent_notes
        )
        
        console.print(f"\n[bold blue]📤 Sending callback to GUVI...[/bold blue]")
        console.print(f"   Session: {session_id}")
        console.print(f"   Scam Detected: {scam_detected}")
        console.print(f"   Messages: {total_messages}")
        
        try:
            client = await self._get_client()
            
            response = await client.post(
                self.callback_url,
                json=payload.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in [200, 201, 202]:
                console.print(f"[bold green]✅ Callback successful![/bold green]")
                return True, f"Success ({response.status_code}): {response.text}"
            else:
                console.print(
                    f"[bold red]❌ Callback failed: {response.status_code}[/bold red]"
                )
                console.print(f"   Response: {response.text[:200]}")
                return False, f"Failed ({response.status_code}): {response.text[:200]}"
                
        except httpx.TimeoutException:
            console.print("[bold red]❌ Callback timeout[/bold red]")
            raise
        except Exception as e:
            console.print(f"[bold red]❌ Callback error: {e}[/bold red]")
            raise
    
    async def send_from_session(self, session: SessionState) -> bool:
        """
        Send callback using session state data.
        Convenience method that extracts all needed data from session.
        
        Args:
            session: The session state with all engagement data
            
        Returns:
            True if successful
        """
        if session.callback_sent:
            console.print("[yellow]⚠️ Callback already sent for this session[/yellow]")
            return True
        
        return await self.send_final_result(
            session_id=session.session_id,
            scam_detected=session.is_scam_detected,
            total_messages=session.total_messages,
            intelligence=session.extracted_intelligence,
            agent_notes=session.agent_notes
        )
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_callback_service: Optional[CallbackService] = None


def get_callback_service() -> CallbackService:
    """Get the callback service singleton."""
    global _callback_service
    if _callback_service is None:
        _callback_service = CallbackService()
    return _callback_service
