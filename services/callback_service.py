"""
Callback Service — sends final results to GUVI evaluation endpoint.
"""

import logging
import time
import httpx
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from models.schemas import CallbackPayload, EngagementMetrics, SessionState
from config.settings import get_settings
from utils.rich_printer import print_callback_payload

logger = logging.getLogger(__name__)


class CallbackService:
    """Handles sending final results to the GUVI endpoint."""

    def __init__(self):
        settings = get_settings()
        self.callback_url = settings.guvi_callback_url
        logger.info(f"CallbackService initialized → {self.callback_url}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def send_callback(self, payload: CallbackPayload) -> str:
        """Send final result to GUVI endpoint with retry logic."""
        callback_start = time.time()
        status_code = None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.callback_url,
                    json=payload.model_dump(),
                    headers={"Content-Type": "application/json"},
                )
                
                status_code = response.status_code
                response_text = response.text

                callback_elapsed = time.time() - callback_start

                # ── Rich Print: Callback Payload ──
                print_callback_payload(
                    payload_dict=payload.model_dump(),
                    elapsed_seconds=callback_elapsed,
                    status_code=status_code,
                )

                logger.info(
                    f"Callback sent for session {payload.sessionId}: "
                    f"status={response.status_code}, response={response_text[:200]}"
                )
                return response_text

        except Exception as e:
            callback_elapsed = time.time() - callback_start

            # Still print what we tried to send
            print_callback_payload(
                payload_dict=payload.model_dump(),
                elapsed_seconds=callback_elapsed,
                status_code=status_code or 0,
            )

            logger.error(f"Callback failed for session {payload.sessionId}: {e}")
            raise

    async def send_from_session(self, session: SessionState) -> str:
        """Build callback payload from session state and send it."""
        # Calculate engagement metrics
        created = session.created_at
        now = datetime.utcnow()
        duration = (now - created).total_seconds()


        # Use Judge's final payload if available (Strict Mode)
        if session.final_callback_payload:
            payload_dict = session.final_callback_payload.copy()
            # Strict filtering for extractedIntelligence
            if "extractedIntelligence" in payload_dict:
                raw_intel = payload_dict["extractedIntelligence"]
                filtered_intel = {
                    k: v for k, v in raw_intel.items() 
                    if k in {"bankAccounts", "upiIds", "phishingLinks", "phoneNumbers", "suspiciousKeywords"}
                }
                payload_dict["extractedIntelligence"] = filtered_intel
                
            # Ensure strict adherence to user schema (no conversationLog)
            if "conversationLog" in payload_dict:
                 del payload_dict["conversationLog"]

        else:
            # Fallback construction
            verdict = session.council_verdict
            raw_intel = session.extracted_intelligence
            filtered_intel = {
                k: v for k, v in raw_intel.items() 
                if k in {"bankAccounts", "upiIds", "phishingLinks", "phoneNumbers", "suspiciousKeywords"}
            }
            
            payload_dict = {
                "sessionId": session.session_id,
                "scamDetected": session.is_scam_detected,
                "totalMessagesExchanged": session.turn_count,
                "extractedIntelligence": filtered_intel,
                "agentNotes": verdict.reasoning if verdict else "No verdict available"
            }
        
        # Log before sending
        try:
            payload = CallbackPayload(**payload_dict)
        except Exception as e:
            logger.error(f"Failed to validate payload: {e}")
            # Try to send dict directly if validation fails (last resort)
            payload = payload_dict

        return await self.send_callback(payload)
