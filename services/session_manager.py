"""
Session Manager — in-memory session store with 30-second inactivity timer.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Callable, Awaitable
from models.schemas import SessionState

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages conversation sessions with per-session inactivity timers."""

    def __init__(self, inactivity_timeout: int = 30):
        self._sessions: Dict[str, SessionState] = {}
        self._timers: Dict[str, asyncio.Task] = {}
        self._inactivity_timeout = inactivity_timeout
        self._callback_handler: Optional[Callable[[str], Awaitable[None]]] = None
        logger.info(f"SessionManager initialized (inactivity timeout: {inactivity_timeout}s)")

    def set_callback_handler(self, handler: Callable[[str], Awaitable[None]]):
        """Set the function to call when inactivity timer fires."""
        self._callback_handler = handler

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get an existing session."""
        return self._sessions.get(session_id)

    def create_session(self, session_id: str) -> SessionState:
        """Create a new session."""
        session = SessionState(session_id=session_id)
        self._sessions[session_id] = session
        logger.info(f"Session created: {session_id}")
        return session

    def get_or_create_session(self, session_id: str) -> SessionState:
        """Get existing session or create a new one."""
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id)
        return session

    def update_session(self, session: SessionState):
        """Update session state and reset inactivity timer."""
        session.last_activity = datetime.utcnow()
        self._sessions[session.session_id] = session
        self._reset_inactivity_timer(session.session_id)

    def _reset_inactivity_timer(self, session_id: str):
        """Cancel existing timer and start fresh 30-second countdown."""
        # Cancel existing timer
        if session_id in self._timers:
            self._timers[session_id].cancel()
            logger.debug(f"Timer reset for session {session_id}")

        # Start new timer
        self._timers[session_id] = asyncio.create_task(
            self._inactivity_countdown(session_id)
        )

    async def _inactivity_countdown(self, session_id: str):
        """Wait for inactivity timeout, then trigger callback."""
        try:
            await asyncio.sleep(self._inactivity_timeout)
            
            session = self.get_session(session_id)
            if session and not session.callback_sent:
                logger.info(f"Inactivity timeout for session {session_id} — triggering callback")
                if self._callback_handler:
                    await self._callback_handler(session_id)
        except asyncio.CancelledError:
            # Timer was reset by a new message — normal behavior
            pass
        except Exception as e:
            logger.error(f"Inactivity callback error for {session_id}: {e}")

    def mark_callback_sent(self, session_id: str, response: str = ""):
        """Mark that callback has been sent for this session."""
        session = self.get_session(session_id)
        if session:
            session.callback_sent = True
            session.callback_response = response
            self._sessions[session_id] = session
        
        # Cancel timer since callback is done
        if session_id in self._timers:
            self._timers[session_id].cancel()
            del self._timers[session_id]

    def delete_session(self, session_id: str):
        """Clean up a session and its timer."""
        if session_id in self._timers:
            self._timers[session_id].cancel()
            del self._timers[session_id]
        self._sessions.pop(session_id, None)
        logger.info(f"Session deleted: {session_id}")

    @property
    def active_count(self) -> int:
        return len(self._sessions)
