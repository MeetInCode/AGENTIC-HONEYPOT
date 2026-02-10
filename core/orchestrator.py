"""
Core Orchestrator — coordinates the entire honeypot pipeline.

Architecture (PRD §2 + §5):
  Reply Path  (SYNC)  — generate human-like reply IMMEDIATELY, return it
  Intel Path  (ASYNC) — council detection, intelligence extraction, callback

The reply is ALWAYS sent BEFORE detection, extraction, or callback logic.
These are two independent paths that share session state.
"""

import asyncio
import logging
import time
from typing import Optional
from datetime import datetime

from models.schemas import (
    HoneypotRequest, HoneypotResponse, SessionState, CouncilVerdict
)
from agents.detection_council import DetectionCouncil
from engagement.response_generator import ResponseGenerator
from services.session_manager import SessionManager
from services.callback_service import CallbackService
from services.intelligence_extractor import IntelligenceExtractor
from config.settings import get_settings
from utils.rich_printer import (
    print_incoming_message,
    print_agent_response,
    print_api_response,
    print_pipeline_summary,
)

logger = logging.getLogger(__name__)


class HoneypotOrchestrator:
    """Central orchestrator that ties together detection, engagement, and intelligence."""

    def __init__(self):
        settings = get_settings()
        
        self.detection_council = DetectionCouncil()
        self.response_generator = ResponseGenerator()
        self.session_manager = SessionManager(
            inactivity_timeout=settings.inactivity_timeout_seconds
        )
        self.callback_service = CallbackService()
        self.intelligence_extractor = IntelligenceExtractor()
        self.max_turns = settings.max_conversation_turns
        self.confidence_threshold = settings.scam_confidence_threshold

        # Wire up inactivity timer callback
        self.session_manager.set_callback_handler(self._on_inactivity_timeout)

        logger.info("HoneypotOrchestrator initialized")

    async def process_message(self, request: HoneypotRequest) -> HoneypotResponse:
        """
        Process an incoming message.

        Reply Path (sync):  Generate reply immediately → return to caller
        Intel Path (async): Council → intelligence extraction → callback
        """
        reply_start = time.time()

        session = self.session_manager.get_or_create_session(request.sessionId)

        # Record incoming message
        session.messages.append({
            "sender": request.message.sender,
            "text": request.message.text,
            "timestamp": request.message.timestamp,
        })
        session.turn_count += 1

        # ── Rich Print: Incoming Message (with raw JSON) ──
        raw_request = {
            "sessionId": request.sessionId,
            "message": {
                "sender": request.message.sender,
                "text": request.message.text,
                "timestamp": request.message.timestamp,
            },
            "conversationHistory": request.conversationHistory,
            "metadata": {
                "channel": request.metadata.channel if request.metadata else "SMS",
                "language": request.metadata.language if request.metadata else None,
                "locale": request.metadata.locale if request.metadata else None,
            } if request.metadata else None,
        }
        print_incoming_message(
            session_id=request.sessionId,
            sender=request.message.sender,
            text=request.message.text,
            turn=session.turn_count,
            channel=request.metadata.channel if request.metadata else "SMS",
            raw_request=raw_request,
        )

        # ══════════════════════════════════════════════════════════════
        # REPLY PATH (sync, immediate) — PRD §5
        # The reply is generated FIRST, independent of council voting.
        # We always respond as the persona — the council determines
        # scam detection in the background, but the reply doesn't wait.
        # ══════════════════════════════════════════════════════════════
        response_start = time.time()

        reply, persona_id = await self.response_generator.generate(
            message=request.message.text,
            conversation_history=session.messages,
            scam_type=session.scam_type,        # may be "unknown" on first turn
            persona_id=session.persona_id,
            turn_count=session.turn_count,
        )
        session.persona_id = persona_id
        session.agent_responses.append(reply)

        response_elapsed = time.time() - response_start

        # ── Rich Print: Agent Response ──
        print_agent_response(
            response_text=reply,
            persona_name="Ramesh Kumar",
            elapsed_seconds=response_elapsed,
        )

        # Record agent response in session
        session.messages.append({
            "sender": "agent",
            "text": reply,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

        # Update session (resets inactivity timer)
        self.session_manager.update_session(session)

        # ══════════════════════════════════════════════════════════════
        # INTEL PATH (async, background) — PRD §6
        # Council voting, intelligence extraction, and callback all
        # happen AFTER the reply is returned. Never blocks reply.
        # ══════════════════════════════════════════════════════════════
        asyncio.create_task(
            self._run_intel_pipeline(request.sessionId, request.message.text, request.conversationHistory)
        )

        # Build response
        reply_elapsed = time.time() - reply_start
        response_obj = HoneypotResponse(
            sessionId=request.sessionId,
            reply=reply,
            scamDetected=session.is_scam_detected,  # may be False on first turn
            confidence=session.scam_confidence,
        )

        # ── Rich Print: Full API Response JSON ──
        print_api_response(
            response_dict=response_obj.model_dump(),
            total_elapsed=reply_elapsed,
        )

        # ── Rich Print: Reply Path Summary ──
        print_pipeline_summary(
            total_elapsed=reply_elapsed,
            session_id=request.sessionId,
            scam=session.is_scam_detected,
        )

        return response_obj

    async def _run_intel_pipeline(self, session_id: str, message: str, history: list):
        """
        Background intel pipeline: council → update session → extract → callback.
        This runs independently of the reply path.
        """
        try:
            session = self.session_manager.get_session(session_id)
            if not session:
                return

            # Build context for detection
            context = self._build_context(history)

            # ── Step 1: Detection Council ──
            # (rich printing of votes + verdict happens inside detection_council.analyze)
            verdict = await self.detection_council.analyze(
                message=message,
                context=context,
                session_id=session_id,
                turn_count=session.turn_count,
            )

            # Update session with detection results
            if verdict.is_scam and verdict.confidence >= self.confidence_threshold:
                session.is_scam_detected = True
                session.scam_confidence = verdict.confidence
                session.scam_type = verdict.scam_type
                session.council_verdict = verdict

            # ── Step 2: Intelligence Extraction ──
            intel = await self.intelligence_extractor.extract(session.messages)

            # Merge with existing intelligence
            for key, values in intel.items():
                if isinstance(values, list):
                    existing = session.extracted_intelligence.get(key, [])
                    merged = list(set(existing + values))
                    session.extracted_intelligence[key] = merged

            self.session_manager.update_session(session)

            # ── Step 3: Check if callback should fire ──
            if session.turn_count >= self.max_turns and not session.callback_sent:
                logger.info(f"Max turns reached for {session_id} — sending callback")
                await self._send_callback(session_id)

        except Exception as e:
            logger.error(f"Intel pipeline error for {session_id}: {e}")

    async def _on_inactivity_timeout(self, session_id: str):
        """Called when a session's inactivity timer fires (30s no messages)."""
        logger.info(f"Inactivity timeout for session {session_id}")
        await self._send_callback(session_id)

    async def _send_callback(self, session_id: str):
        """Send the final callback for a session."""
        session = self.session_manager.get_session(session_id)
        if not session or session.callback_sent:
            return

        try:
            # Final intelligence extraction before callback
            if session.messages:
                intel = await self.intelligence_extractor.extract(session.messages)
                for key, values in intel.items():
                    if isinstance(values, list):
                        existing = session.extracted_intelligence.get(key, [])
                        merged = list(set(existing + values))
                        session.extracted_intelligence[key] = merged

            # (rich printing of callback payload happens inside callback_service)
            response = await self.callback_service.send_from_session(session)
            self.session_manager.mark_callback_sent(session_id, response)
            logger.info(f"Callback sent for session {session_id}: {response[:100]}")

        except Exception as e:
            logger.error(f"Callback failed for session {session_id}: {e}")
            self.session_manager.mark_callback_sent(session_id, f"Error: {str(e)}")

    def _build_context(self, history: list) -> str:
        """Build a concise context string from conversation history."""
        if not history:
            return "No prior context — this is the first message."

        recent = history[-6:]  # Last 6 messages
        lines = []
        for msg in recent:
            sender = msg.get("sender", "unknown")
            text = msg.get("text", "")[:200]
            lines.append(f"[{sender}]: {text}")

        return "Previous conversation:\n" + "\n".join(lines)
