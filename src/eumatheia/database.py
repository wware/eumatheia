"""SQLite database for session persistence."""

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class Database:
    """SQLite database for session storage."""

    def __init__(self, db_path: Path | str = "eumatheia.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create database tables if they don't exist."""
        with self.connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    exhibit_id TEXT NOT NULL,
                    current_step TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_activity REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS restore_tokens (
                    token TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                        ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_restore_tokens_session_id
                ON restore_tokens(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_last_activity
                ON sessions(last_activity)
            """)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """
        Context manager for database connections.

        Yields:
            SQLite connection with row factory enabled
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_session(
        self, session_id: str, exhibit_id: str, current_step: str
    ) -> None:
        """
        Insert a new session into the database.

        Args:
            session_id: Unique session identifier
            exhibit_id: Exhibit ID for this session
            current_step: Initial step ID
        """
        now = time.time()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, exhibit_id, current_step, created_at, last_activity)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, exhibit_id, current_step, now, now),
            )

    def get_session(self, session_id: str) -> dict | None:
        """
        Retrieve session from database.

        Args:
            session_id: Session identifier

        Returns:
            Session data as dict or None if not found
        """
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT session_id, exhibit_id, current_step, created_at, last_activity
                FROM sessions
                WHERE session_id = ?
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_activity(self, session_id: str) -> None:
        """
        Update last activity timestamp.

        Args:
            session_id: Session identifier
        """
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET last_activity = ?
                WHERE session_id = ?
                """,
                (time.time(), session_id),
            )

    def update_step(self, session_id: str, new_step: str) -> None:
        """
        Update current step for a session.

        Args:
            session_id: Session identifier
            new_step: New step ID
        """
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET current_step = ?, last_activity = ?
                WHERE session_id = ?
                """,
                (new_step, time.time(), session_id),
            )

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from database.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted, False if not found
        """
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session_id,)
            )
            return cursor.rowcount > 0

    def get_idle_sessions(self, idle_timeout_seconds: int) -> list[str]:
        """
        Find sessions that have been idle too long.

        Args:
            idle_timeout_seconds: Timeout threshold

        Returns:
            List of session IDs that are idle
        """
        cutoff = time.time() - idle_timeout_seconds
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT session_id
                FROM sessions
                WHERE last_activity < ?
                """,
                (cutoff,),
            )
            return [row["session_id"] for row in cursor.fetchall()]

    def create_restore_token(
        self, token: str, session_id: str, expires_at: float
    ) -> None:
        """
        Create a restore token for a session.

        Args:
            token: Secure random token
            session_id: Session to restore
            expires_at: Unix timestamp when token expires
        """
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO restore_tokens (token, session_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, session_id, time.time(), expires_at),
            )

    def get_restore_token(self, token: str) -> dict | None:
        """
        Retrieve restore token data.

        Args:
            token: Restore token

        Returns:
            Token data including session_id, or None if not found/expired
        """
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT token, session_id, created_at, expires_at
                FROM restore_tokens
                WHERE token = ? AND expires_at > ?
                """,
                (token, time.time()),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def delete_restore_token(self, token: str) -> bool:
        """
        Delete a restore token.

        Args:
            token: Restore token

        Returns:
            True if token was deleted, False if not found
        """
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM restore_tokens WHERE token = ?", (token,)
            )
            return cursor.rowcount > 0

    def cleanup_expired_tokens(self) -> int:
        """
        Delete all expired restore tokens.

        Returns:
            Number of tokens deleted
        """
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM restore_tokens WHERE expires_at <= ?", (time.time(),)
            )
            return cursor.rowcount
