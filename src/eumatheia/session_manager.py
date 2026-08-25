"""Session lifecycle management."""

import secrets
import time
from typing import Dict

from .models import Session


class SessionManager:
    """Manages learner sessions."""

    def __init__(self, idle_timeout_seconds: int = 1800):
        """
        Initialize session manager.

        Args:
            idle_timeout_seconds: Seconds of inactivity before session is reaped (default 30min)
        """
        self._sessions: Dict[str, Session] = {}
        self._idle_timeout = idle_timeout_seconds

    def create_session(self, exhibit_id: str, first_step: str) -> Session:
        """
        Create a new session.

        Args:
            exhibit_id: ID of the exhibit to start
            first_step: ID of the first step in the exhibit

        Returns:
            New session object
        """
        session_id = self._generate_session_id()
        session = Session(
            session_id=session_id,
            exhibit_id=exhibit_id,
            current_step=first_step,
            last_activity=time.time(),
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """
        Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session object or None if not found
        """
        return self._sessions.get(session_id)

    def update_activity(self, session_id: str) -> None:
        """
        Update last activity timestamp for a session.

        Args:
            session_id: Session identifier
        """
        session = self._sessions.get(session_id)
        if session:
            # Create new session with updated timestamp (frozen model)
            self._sessions[session_id] = session.model_copy(
                update={"last_activity": time.time()}
            )

    def update_step(self, session_id: str, new_step: str) -> None:
        """
        Update current step for a session.

        Args:
            session_id: Session identifier
            new_step: New step ID
        """
        session = self._sessions.get(session_id)
        if session:
            self._sessions[session_id] = session.model_copy(
                update={"current_step": new_step, "last_activity": time.time()}
            )

    def reap_idle_sessions(self) -> list[str]:
        """
        Find and remove idle sessions.

        Returns:
            List of reaped session IDs
        """
        now = time.time()
        reaped = []

        for session_id, session in list(self._sessions.items()):
            if now - session.last_activity > self._idle_timeout:
                del self._sessions[session_id]
                reaped.append(session_id)

        return reaped

    def delete_session(self, session_id: str) -> bool:
        """
        Explicitly delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    @staticmethod
    def _generate_session_id() -> str:
        """
        Generate a unique session ID.

        Returns:
            Session ID in format 'sess-XXXXXXXX' (8 hex chars)
        """
        return f"sess-{secrets.token_hex(4)}"
