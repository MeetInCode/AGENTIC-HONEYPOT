"""
Session Manager for tracking conversation sessions.
Handles in-memory state management for active sessions.
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio
from rich.console import Console

from models.schemas import SessionState, Message, ExtractedIntelligence, CouncilVerdict


console = Console()


class SessionManager:
    """
    Manages active conversation sessions.
    Stores and retrieves session state for multi-turn conversations.
    """
    
    def __init__(self, session_timeout_minutes: int = 30):
        self._sessions: Dict[str, SessionState] = {}
        self._session_timeout = timedelta(minutes=session_timeout_minutes)
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get an existing session by ID.
        
        Args:
            session_id: The session identifier
            
        Returns:
            SessionState if found, None otherwise
        """
        session = self._sessions.get(session_id)
        if session:
            # Update last activity
            session.last_activity = datetime.utcnow()
        return session
    
    def create_session(self, session_id: str) -> SessionState:
        """
        Create a new session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            New SessionState
        """
        session = SessionState(
            session_id=session_id,
            is_scam_detected=False,
            total_messages=0,
            start_time=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            extracted_intelligence=ExtractedIntelligence(),
            conversation_history=[],
            engagement_goals=[],
            council_verdict=None,
            agent_notes="",
            callback_sent=False
        )
        self._sessions[session_id] = session
        console.print(f"[bold blue]📝 Created new session: {session_id}[/bold blue]")
        return session
    
    def get_or_create_session(self, session_id: str) -> SessionState:
        """
        Get existing session or create new one.
        
        Args:
            session_id: The session identifier
            
        Returns:
            SessionState
        """
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id)
        return session
    
    def update_session(
        self,
        session_id: str,
        message: Optional[Message] = None,
        is_scam: Optional[bool] = None,
        intelligence: Optional[ExtractedIntelligence] = None,
        verdict: Optional[CouncilVerdict] = None,
        agent_note: Optional[str] = None,
        callback_sent: Optional[bool] = None
    ) -> SessionState:
        """
        Update an existing session with new data.
        
        Args:
            session_id: The session identifier
            message: New message to add to history
            is_scam: Update scam detection status
            intelligence: New intelligence to merge
            verdict: Council verdict to store
            agent_note: Note to append to agent notes
            callback_sent: Update callback status
            
        Returns:
            Updated SessionState
        """
        session = self.get_or_create_session(session_id)
        
        if message:
            session.conversation_history.append(message)
            session.total_messages += 1
        
        if is_scam is not None:
            session.is_scam_detected = is_scam
        
        if intelligence:
            session.extracted_intelligence = session.extracted_intelligence.merge(intelligence)
        
        if verdict:
            session.council_verdict = verdict
        
        if agent_note:
            if session.agent_notes:
                session.agent_notes += f" | {agent_note}"
            else:
                session.agent_notes = agent_note
        
        if callback_sent is not None:
            session.callback_sent = callback_sent
        
        session.last_activity = datetime.utcnow()
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: The session identifier
            
        Returns:
            True if session was deleted
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            console.print(f"[dim]🗑️ Deleted session: {session_id}[/dim]")
            return True
        return False
    
    def list_sessions(self) -> list:
        """List all active session IDs."""
        return list(self._sessions.keys())
    
    def get_active_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self._sessions)
    
    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        now = datetime.utcnow()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.last_activity > self._session_timeout
        ]
        
        for sid in expired:
            del self._sessions[sid]
        
        if expired:
            console.print(f"[dim]🧹 Cleaned up {len(expired)} expired sessions[/dim]")
        
        return len(expired)
    
    async def start_cleanup_task(self, interval_minutes: int = 5) -> None:
        """Start background task for session cleanup."""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_minutes * 60)
                self.cleanup_expired_sessions()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass


# Singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
