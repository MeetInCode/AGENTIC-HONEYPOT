"""
Session Manager — simple in-memory session store.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from models.schemas import SessionState

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages conversation sessions — simple dict-based storage."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        logger.info("SessionManager initialized")

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get an existing session."""
        return self._sessions.get(session_id)

    def create_session(self, session_id: str) -> SessionState:
        """Create a new session."""
        session = SessionState(session_id=session_id, created_at=datetime.utcnow())
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
        """Update session state."""
        session.last_activity = datetime.utcnow()
        self._sessions[session.session_id] = session

    def mark_callback_sent(self, session_id: str, response: str = ""):
        """Mark that callback has been sent for this session."""
        session = self.get_session(session_id)
        if session:
            session.callback_sent = True
            session.callback_response = response[:500] if response else ""
            self._sessions[session_id] = session
        else:
            logger.warning(f"Attempted to mark callback sent for non-existent session: {session_id}")

    def delete_session(self, session_id: str):
        """Clean up a session."""
        self._sessions.pop(session_id, None)
        logger.info(f"Session deleted: {session_id}")

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def all_sessions(self):
        """Return a list of all active sessions."""
        return list(self._sessions.values())
