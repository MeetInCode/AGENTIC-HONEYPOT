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
    HoneypotRequest,
    HoneypotResponse,
    SessionState,
    CouncilVerdict,
)
from agents.detection_council import DetectionCouncil
from engagement.response_generator import ResponseGenerator
from agents.meta_moderator import JudgeAgent
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
        self.judge_agent = JudgeAgent()
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

        reply, persona_id, status = await self.response_generator.generate(
            message=request.message.text,
            conversation_history=session.messages,
            scam_type=session.scam_type,        # may be "unknown" on first turn
            persona_id=session.persona_id,
            turn_count=session.turn_count,
        )
        session.persona_id = persona_id

        if status == "failure":
            logger.info(f"ResponseGenerator status=failure for {request.sessionId} — skipping reply and intel.")
            
            # We do NOT append to session.agent_responses or session.messages if we didn't reply?
            # Or should we record that we didn't reply?
            # For now, let's just return.
            
            response_elapsed = time.time() - response_start
            
            # Return response with no reply
            response_obj = HoneypotResponse(
                sessionId=request.sessionId,
                reply=None,
                scamDetected=session.is_scam_detected,
                confidence=session.scam_confidence,
            )
            
            # ── Rich Print: Skipped Summary ──
            print_pipeline_summary(
                total_elapsed=response_elapsed,
                session_id=request.sessionId,
                scam=session.is_scam_detected,
                note="Skipped (Agent Status: Failure)"
            )
            return response_obj

        # If success, reply is not None
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
        # Council voting, intelligence extraction, and final Judge
        # aggregation are completely decoupled from the reply latency.
        # This pipeline never blocks the reply agent.
        # ══════════════════════════════════════════════════════════════
        asyncio.create_task(
            self._run_intel_pipeline(
                request.sessionId,
                request.message.text,
                request.conversationHistory,
            )
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

            # ── Step 1: Detection Council (5 independent LLM agents) ──
            # Rich printing of votes + verdict happens inside detection_council.analyze
            votes, verdict = await self.detection_council.analyze(
                message=message,
                context=context,
                session_id=session_id,
                turn_count=session.turn_count,
            )

            # Persist raw council votes for Judge aggregation at callback time
            session.council_votes.extend(votes)

            # Update session with lightweight verdict (for in-API telemetry)
            if verdict.is_scam and verdict.confidence >= self.confidence_threshold:
                session.is_scam_detected = True
                session.scam_confidence = verdict.confidence
                session.scam_type = verdict.scam_type
                session.council_verdict = verdict

            # ── Step 2: Intelligence Extraction (regex + LLM) ──
            intel = await self.intelligence_extractor.extract(session.messages)

            # Merge with existing intelligence (deduplicated lists)
            for key, values in intel.items():
                if isinstance(values, list):
                    existing = session.extracted_intelligence.get(key, [])
                    merged = list(set(existing + values))
                    session.extracted_intelligence[key] = merged

            # Intentionally do NOT reset the inactivity timer here.
            # The 5-second window is measured from the last incoming request
            # (reply agent path), not from background intel updates. Session
            # state is already held by reference inside SessionManager.

        except Exception as e:
            logger.error(f"Intel pipeline error for {session_id}: {e}")

    async def _on_inactivity_timeout(self, session_id: str):
        """
        Called when a session's inactivity timer fires (no new messages within
        the configured window, default 5 seconds).
        """
        logger.info(f"Inactivity timeout for session {session_id} — triggering Judge + callback")
        await self._send_callback(session_id)

    async def _send_callback(self, session_id: str):
        """Run Judge aggregation and send the final callback for a session."""
        session = self.session_manager.get_session(session_id)
        if not session or session.callback_sent:
            return

        try:
            # One more intelligence sweep over full conversation (best-effort enrichment)
            if session.messages:
                intel = await self.intelligence_extractor.extract(session.messages)
                for key, values in intel.items():
                    if isinstance(values, list):
                        existing = session.extracted_intelligence.get(key, [])
                        merged = list(set(existing + values))
                        session.extracted_intelligence[key] = merged

            # ── Judge LLM: build final callback JSON from all council votes ──
            try:
                last_message_text = session.messages[-1]["text"] if session.messages else ""
            except Exception:
                last_message_text = ""

            votes = session.council_votes or []
            if votes:
                judge_payload = await self.judge_agent.adjudication(
                    message=last_message_text,
                    votes=votes,
                    session_id=session.session_id,
                    turn_count=session.turn_count,
                )
            else:
                judge_payload = None

            # Merge Judge's extractedIntelligence with locally accumulated intel
            if judge_payload:
                merged_intel = dict(judge_payload.get("extractedIntelligence", {}))
                for key, values in session.extracted_intelligence.items():
                    if isinstance(values, list):
                        existing = merged_intel.get(key, [])
                        merged_intel[key] = list(set(existing + values))
                judge_payload["extractedIntelligence"] = merged_intel
                session.final_callback_payload = judge_payload

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
