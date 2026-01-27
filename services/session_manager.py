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
        session.last_activity = datetime.utcnow()
        self._save_session(session)
        return session
    
    def _get_storage_path(self, session_id: str) -> str:
        """Get the file path for session storage."""
        import os
        storage_dir = "session_data"
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        return os.path.join(storage_dir, f"{session_id}.json")

    def _save_session(self, session: SessionState) -> None:
        """Persist session to disk."""
        import json
        try:
            path = self._get_storage_path(session.session_id)
            with open(path, 'w') as f:
                f.write(session.model_dump_json())
        except Exception as e:
            console.print(f"[bold red]❌ Failed to save session {session.session_id}: {e}[/bold red]")

    def _load_session_from_disk(self, session_id: str) -> Optional[SessionState]:
        """Load session from disk if exists."""
        import json
        import os
        try:
            path = self._get_storage_path(session_id)
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    # Handle datetime deserialization if needed, but pydantic should handle standard types
                    # We might need to parse datetime strings manually if simple json load doesn't work for Pydantic init associated with simpler types
                    # Actually, Pydantic's model_validate_json is better
                    return SessionState.model_validate(data)
        except Exception as e:
            console.print(f"[bold red]❌ Failed to load session {session_id}: {e}[/bold red]")
        return None

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get an existing session by ID, checking memory then disk.
        """
        session = self._sessions.get(session_id)
        if not session:
            session = self._load_session_from_disk(session_id)
            if session:
                self._sessions[session_id] = session
        
        if session:
            # Update last activity
            session.last_activity = datetime.utcnow()
            # self._save_session(session) # Optional: don't save on every read to save IO
        return session
    
    def create_session(self, session_id: str) -> SessionState:
        """
        Create a new session.
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
        self._save_session(session)
        console.print(f"[bold blue]📝 Created new session: {session_id}[/bold blue]")
        return session

    def get_or_create_session(self, session_id: str) -> SessionState:
        """
        Get existing session or create new one.
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
        callback_sent: Optional[bool] = None,
        callback_response_log: Optional[str] = None,
        **kwargs
    ) -> SessionState:
        """
        Update an existing session with new data and persist it.
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
            
        if callback_response_log:
            session.callback_response_log = callback_response_log
            
        # Update any other field from kwargs if they exist in SessionState
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        session.last_activity = datetime.utcnow()
        self._save_session(session)
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
