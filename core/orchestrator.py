"""
Core Orchestrator — coordinates the entire honeypot pipeline with worker pool.

Flow per request:
  1. Check if a worker is already handling this session → abort if so
  2. Generate reply (llama-3.3-70b via Groq) → return to caller immediately
  3. Assign a worker from the pool for background intel:
     a. If no conversation history: wait 3s (interruptible) before council
     b. If conversation history exists: send to council immediately
     c. Council detection (5 LLM calls in parallel via asyncio.gather)
     d. Intelligence extraction (regex + 1 LLM call)
     e. Judge aggregation (llama-3.3-70b via Groq)
     f. Send callback to GUVI (if not aborted)
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
from core.worker_pool import WorkerPool
from utils.rich_printer import (
    print_incoming_message,
    print_agent_response,
    print_api_response,
    print_pipeline_summary,
)

logger = logging.getLogger(__name__)


class HoneypotOrchestrator:
    """Worker-pool based orchestrator. Reply returns fast, intel runs on a pooled worker."""

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
        self.council_delay = settings.council_delay_seconds

        # Worker pool: bounded concurrent background tasks
        self.worker_pool = WorkerPool(num_workers=settings.worker_pool_size)

        logger.info(
            f"HoneypotOrchestrator initialized "
            f"(pool={settings.worker_pool_size} workers, "
            f"council_delay={self.council_delay}s)"
        )

    async def process_message(self, request: HoneypotRequest) -> HoneypotResponse:
        """
        Process a message:
        1. Abort any existing worker for this session
        2. Generate reply → return immediately
        3. Assign a worker for background intel
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

        # ── ABORT existing worker for this session (if any) ──
        existing_worker = self.worker_pool.get_worker_for_session(request.sessionId)
        if existing_worker is not None:
            logger.warning(
                f"🔄 Duplicate session {request.sessionId} — aborting Worker {existing_worker}"
            )
            self.worker_pool.abort_session(request.sessionId)
            # Reset callback_sent so the new worker can send a fresh callback
            session.callback_sent = False
            session.final_callback_payload = None

        # ── STEP 1: Generate Reply (fast, 1 LLM call) — always immediate ──
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
            status="success",
            reply=reply,
        )

        elapsed = time.time() - pipeline_start
        print_api_response(response_obj.model_dump(), elapsed)
        print_pipeline_summary(elapsed, request.sessionId, session.is_scam_detected)

        # ── STEP 2: Assign worker for background intel ──
        context = self._build_context(request.conversationHistory)
        conversation_history_count = len(request.conversationHistory) if request.conversationHistory else 0

        # Create a cancel event for this worker
        cancel_event = asyncio.Event()

        # Build the coroutine (not started yet)
        coro = self._background_intel(
            session_id=request.sessionId,
            message=request.message.text,
            context=context,
            conversation_history_count=conversation_history_count,
            cancel_event=cancel_event,
        )

        # Fire-and-forget: assign to worker pool in background
        # This ensures the HTTP response returns immediately
        asyncio.create_task(
            self._assign_worker(request.sessionId, coro, cancel_event)
        )

        return response_obj

    async def _assign_worker(self, session_id: str, coro, cancel_event: asyncio.Event):
        """Wrapper to assign worker in background with error handling."""
        try:
            await self.worker_pool.assign(
                session_id=session_id,
                coro=coro,
                cancel_event=cancel_event,
            )
        except Exception as e:
            logger.error(f"Failed to assign worker for {session_id}: {e}")

    async def _background_intel(
        self,
        session_id: str,
        message: str,
        context: str,
        conversation_history_count: int = 0,
        cancel_event: asyncio.Event = None,
    ):
        """Background task: [optional delay] → council → intel → judge → callback."""
        try:
            session = self.session_manager.get_session(session_id)
            if not session or session.callback_sent:
                return

            # Delay removed per user request: proceed to council immediately.
            logger.info(
                f"⚡ Session {session_id}: Processing intelligence immediately (no delay)"
            )

            # ── Check cancellation before council ──
            if cancel_event and cancel_event.is_set():
                logger.info(f"🚫 Session {session_id}: Aborted before council")
                return

            # ── Council: 5 LLM calls in parallel ──
            votes, verdict = await self.detection_council.analyze(
                message=message,
                context=context,
                session_id=session_id,
                turn_count=session.turn_count,
            )

            # ── Check cancellation after council ──
            if cancel_event and cancel_event.is_set():
                logger.info(f"🚫 Session {session_id}: Aborted after council — discarding votes")
                return

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

            # ── Check cancellation before intel extraction ──
            if cancel_event and cancel_event.is_set():
                logger.info(f"🚫 Session {session_id}: Aborted before intel extraction")
                return

            # ── Intelligence extraction ──
            try:
                intel = await self.intelligence_extractor.extract(session.messages)
                for key, values in intel.items():
                    if isinstance(values, list):
                        existing = session.extracted_intelligence.get(key, [])
                        session.extracted_intelligence[key] = list(set(existing + values))
            except Exception as e:
                logger.error(f"Intel extraction failed: {e}")

            # ── Check cancellation before judge ──
            if cancel_event and cancel_event.is_set():
                logger.info(f"🚫 Session {session_id}: Aborted before judge")
                return

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

            # ── Check cancellation before callback ──
            if cancel_event and cancel_event.is_set():
                logger.info(
                    f"🚫 Session {session_id}: Aborted before callback — "
                    f"discarding payload (no callback sent)"
                )
                return

            # Merge extracted intelligence into payload
            if callback_payload:
                merged = dict(callback_payload.get("extractedIntelligence", {}))
                for key, vals in session.extracted_intelligence.items():
                    if isinstance(vals, list):
                        existing = merged.get(key, [])
                        merged[key] = list(set(existing + vals))
                callback_payload["extractedIntelligence"] = merged

                # Final sanitization — enforce strict extraction rules
                callback_payload = self._sanitize_intel(callback_payload)

            # ── Send callback (once per session, only if not aborted) ──
            if callback_payload and not session.callback_sent:
                if cancel_event and cancel_event.is_set():
                    logger.info(f"🚫 Session {session_id}: Last-second abort — no callback")
                    return

                session.final_callback_payload = callback_payload
                try:
                    resp = await self.callback_service.send_from_session(session)
                    self.session_manager.mark_callback_sent(session_id, resp)
                    logger.info(f"✅ Callback sent for {session_id}")
                except Exception as e:
                    logger.error(f"Callback send failed for {session_id}: {e}")

            self.session_manager.update_session(session)

        except asyncio.CancelledError:
            logger.info(f"🚫 Session {session_id}: Worker task cancelled")
            raise  # Re-raise so WorkerPool._run_and_release handles cleanup
        except Exception as e:
            logger.error(f"Background intel failed for {session_id}: {e}", exc_info=True)

    def _build_context(self, history: list) -> str:
        if not history:
            return "No prior context."
        recent = history[-6:]
        lines = [f"[{m.get('sender','?')}]: {m.get('text','')[:200]}" for m in recent]
        return "Previous conversation:\n" + "\n".join(lines)

    def _sanitize_intel(self, payload: dict) -> dict:
        """Final gatekeeper — enforce strict extraction rules before callback dispatch."""
        import re as _re

        intel = payload.get("extractedIntelligence", {})
        is_scam = payload.get("scamDetected", False)

        # bankAccounts: digits only, min 4 digits
        if "bankAccounts" in intel:
            clean = []
            for val in intel["bankAccounts"]:
                digits = ''.join(c for c in str(val) if c.isdigit())
                if len(digits) >= 4:
                    clean.append(digits)
            intel["bankAccounts"] = sorted(set(clean))

        # upiIds: must contain @
        if "upiIds" in intel:
            intel["upiIds"] = sorted(set(
                u for u in intel["upiIds"] if isinstance(u, str) and "@" in u
            ))

        # phishingLinks: must be valid URL (http(s)://domain, no spaces before domain)
        if "phishingLinks" in intel:
            valid_links = []
            for link in intel["phishingLinks"]:
                link = str(link).strip()
                if link.startswith("http") and " " not in link.split("?")[0]:
                    valid_links.append(link)
            intel["phishingLinks"] = sorted(set(valid_links))

        # phoneNumbers: must have 10+ digits
        if "phoneNumbers" in intel:
            clean = []
            for p in intel["phoneNumbers"]:
                digits = ''.join(c for c in str(p) if c.isdigit())
                if len(digits) >= 10:
                    clean.append(str(p))
            intel["phoneNumbers"] = sorted(set(clean))

        # suspiciousKeywords: max 7, lowercase deduplicated, empty if not scam
        if "suspiciousKeywords" in intel:
            if not is_scam:
                intel["suspiciousKeywords"] = []
            else:
                seen = set()
                unique = []
                kws = sorted(intel["suspiciousKeywords"], key=len)
                for kw in kws:
                    kw_lower = kw.strip().lower()
                    if not kw_lower:
                        continue
                    is_dup = False
                    for s in seen:
                        if s in kw_lower:
                            is_dup = True
                            break
                    if not is_dup:
                        seen.add(kw_lower)
                        unique.append(kw_lower)
                intel["suspiciousKeywords"] = unique[:7]

        payload["extractedIntelligence"] = intel
        return payload
