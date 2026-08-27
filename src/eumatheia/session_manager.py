"""Session lifecycle management."""

import secrets
from pathlib import Path

from .database import Database
from .models import Session


class SessionManager:
    """Manages learner sessions."""

    def __init__(self, idle_timeout_seconds: int = 1800, db_path: Path | str = "eumatheia.db"):
        """
        Initialize session manager.

        Args:
            idle_timeout_seconds: Seconds of inactivity before session is reaped (default 30min)
            db_path: Path to SQLite database file
        """
        self._db = Database(db_path)
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
        self._db.create_session(session_id, exhibit_id, first_step)

        # Retrieve from DB to get exact timestamps
        session_data = self._db.get_session(session_id)
        return Session(**session_data)

    def get_session(self, session_id: str) -> Session | None:
        """
        Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session object or None if not found
        """
        session_data = self._db.get_session(session_id)
        if session_data:
            return Session(**session_data)
        return None

    def update_activity(self, session_id: str) -> None:
        """
        Update last activity timestamp for a session.

        Args:
            session_id: Session identifier
        """
        self._db.update_activity(session_id)

    def update_step(self, session_id: str, new_step: str) -> None:
        """
        Update current step for a session.

        Args:
            session_id: Session identifier
            new_step: New step ID
        """
        self._db.update_step(session_id, new_step)

    def reap_idle_sessions(self) -> list[str]:
        """
        Find and remove idle sessions.

        Returns:
            List of reaped session IDs
        """
        # Get idle sessions from database
        idle_sessions = self._db.get_idle_sessions(self._idle_timeout)

        # Delete them
        for session_id in idle_sessions:
            self._db.delete_session(session_id)

        return idle_sessions

    def delete_session(self, session_id: str) -> bool:
        """
        Explicitly delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted, False if not found
        """
        return self._db.delete_session(session_id)

    @staticmethod
    def _generate_session_id() -> str:
        """
        Generate a unique session ID.

        Returns:
            Session ID as 8 hex chars (no prefix - namespace_manager adds 'sess-' prefix)
        """
        return secrets.token_hex(4)
