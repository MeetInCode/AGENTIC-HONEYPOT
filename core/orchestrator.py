"""
Core Orchestrator — coordinates the entire honeypot pipeline.

Flow per request:
  1. Generate reply (llama-3.3-70b via Groq) → return to caller immediately
  2. Background task on same worker:
     a. Council detection (5 LLM calls in parallel via asyncio.gather)
     b. Intelligence extraction (regex + 1 LLM call)
     c. Judge aggregation (llama-3.3-70b via Groq)
     d. Send callback to GUVI (once per session)
"""

import asyncio
import logging
import time

from models.schemas import HoneypotRequest, HoneypotResponse
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
    """Each session gets a worker. Reply returns fast, intel runs in background."""

    def __init__(self):
        settings = get_settings()
        self.detection_council = DetectionCouncil()
        self.response_generator = ResponseGenerator()
        self.session_manager = SessionManager()
        self.callback_service = CallbackService()
        self.judge_agent = JudgeAgent()
        self.intelligence_extractor = IntelligenceExtractor()
        self.max_turns = settings.max_conversation_turns
        self.confidence_threshold = settings.scam_confidence_threshold
        logger.info("HoneypotOrchestrator initialized")

    async def process_message(self, request: HoneypotRequest) -> HoneypotResponse:
        """
        Process a message:
        1. Generate reply → return immediately
        2. Fire background task: council → intel → judge → callback
        """
        pipeline_start = time.time()
        session = self.session_manager.get_or_create_session(request.sessionId)

        # Record incoming message
        session.messages.append({
            "sender": request.message.sender,
            "text": request.message.text,
        })
        session.turn_count += 1

        # Rich print
        print_incoming_message(
            session_id=request.sessionId,
            sender=request.message.sender,
            text=request.message.text,
            turn=session.turn_count,
            channel=request.metadata.channel if request.metadata else "SMS",
            raw_request={"sessionId": request.sessionId, "message": {"sender": request.message.sender, "text": request.message.text}},
        )

        # ── STEP 1: Generate Reply (fast, 1 LLM call) ──
        reply = None
        t0 = time.time()
        try:
            reply, persona_id, status = await self.response_generator.generate(
                message=request.message.text,
                conversation_history=session.messages,
                scam_type=session.scam_type,
                persona_id=session.persona_id,
                turn_count=session.turn_count,
            )
            session.persona_id = persona_id
        except Exception as e:
            logger.error(f"Reply generation failed: {e}", exc_info=True)

        if reply:
            session.agent_responses.append(reply)
            session.messages.append({"sender": "agent", "text": reply})
            print_agent_response(reply, "Ramesh Kumar", time.time() - t0)

        # Save session before returning
        self.session_manager.update_session(session)

        # Build response
        response_obj = HoneypotResponse(
            sessionId=request.sessionId,
            status="success",
            reply=reply,
            scamDetected=session.is_scam_detected,
            confidence=session.scam_confidence,
        )

        elapsed = time.time() - pipeline_start
        print_api_response(response_obj.model_dump(), elapsed)
        print_pipeline_summary(elapsed, request.sessionId, session.is_scam_detected)

        # ── STEP 2: Fire background intel task (council → judge → callback) ──
        context = self._build_context(request.conversationHistory)
        conversation_history_count = len(request.conversationHistory) if request.conversationHistory else 0
        asyncio.create_task(
            self._background_intel(
                session_id=request.sessionId,
                message=request.message.text,
                context=context,
                conversation_history_count=conversation_history_count,
            )
        )

        return response_obj

    async def _background_intel(self, session_id: str, message: str, context: str, conversation_history_count: int = 0):
        """Background task: council → intel → judge → callback."""
        try:
            session = self.session_manager.get_session(session_id)
            if not session or session.callback_sent:
                return

            # ── Council: 5 LLM calls in parallel ──
            votes, verdict = await self.detection_council.analyze(
                message=message,
                context=context,
                session_id=session_id,
                turn_count=session.turn_count,
            )

            # Update session with verdict
            if votes:
                session.council_votes.extend(votes)
            if verdict:
                if verdict.is_scam and verdict.confidence >= self.confidence_threshold and verdict.scam_votes >= 2:
                    session.is_scam_detected = True
                    session.scam_confidence = verdict.confidence
                    session.scam_type = verdict.scam_type
                    session.council_verdict = verdict
                else:
                    session.is_scam_detected = False
                    session.scam_confidence = 0.0
                    session.scam_type = "safe"

            # ── Intelligence extraction ──
            try:
                intel = await self.intelligence_extractor.extract(session.messages)
                for key, values in intel.items():
                    if isinstance(values, list):
                        existing = session.extracted_intelligence.get(key, [])
                        session.extracted_intelligence[key] = list(set(existing + values))
            except Exception as e:
                logger.error(f"Intel extraction failed: {e}")

            # Total messages = conversation history + session messages (incoming + reply)
            total_msg_count = conversation_history_count + len(session.messages)

            # ── Judge aggregation (llama-3.3-70b) → builds callback JSON ──
            callback_payload = None
            try:
                callback_payload = await self.judge_agent.adjudication(
                    message=message,
                    votes=votes,
                    session_id=session_id,
                    total_msg_count=total_msg_count,
                )
            except Exception as e:
                logger.error(f"Judge failed: {e}")
                callback_payload = self.judge_agent._fallback_aggregation(
                    votes=votes,
                    session_id=session_id,
                    total_msg_count=total_msg_count,
                )

            # Merge extracted intelligence into payload
            if callback_payload:
                merged = dict(callback_payload.get("extractedIntelligence", {}))
                for key, vals in session.extracted_intelligence.items():
                    if isinstance(vals, list):
                        existing = merged.get(key, [])
                        merged[key] = list(set(existing + vals))
                callback_payload["extractedIntelligence"] = merged

            # ── Send callback (once per session) ──
            if callback_payload and not session.callback_sent:
                session.final_callback_payload = callback_payload
                try:
                    resp = await self.callback_service.send_from_session(session)
                    self.session_manager.mark_callback_sent(session_id, resp)
                    logger.info(f"Callback sent for {session_id}")
                except Exception as e:
                    logger.error(f"Callback send failed for {session_id}: {e}")

            self.session_manager.update_session(session)

        except Exception as e:
            logger.error(f"Background intel failed for {session_id}: {e}", exc_info=True)

    def _build_context(self, history: list) -> str:
        if not history:
            return "No prior context."
        recent = history[-6:]
        lines = [f"[{m.get('sender','?')}]: {m.get('text','')[:200]}" for m in recent]
        return "Previous conversation:\n" + "\n".join(lines)
