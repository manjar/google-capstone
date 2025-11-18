"""
SQLite-backed session service for persistent conversation memory.

This service implements the ADK SessionService interface using SQLite
for storage, enabling conversation history to persist across server restarts.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from google.adk.sessions import Session, Message


class SQLiteSessionService:
    """
    SQLite-backed implementation of ADK SessionService.

    Design Decision: Using SQLite instead of VertexAI services because:
    1. Consistent with existing stack (timers and preferences already use SQLite)
    2. No cloud dependencies for local development
    3. Simple to implement and debug
    4. Can be migrated to cloud storage later if needed
    """

    def __init__(self, db_path: Path):
        """
        Initialize the SQLite session service.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create sessions and messages tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    app_name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT,
                    UNIQUE(app_name, user_id, id)
                )
            """)

            # Messages table for conversation history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)

            # Index for faster message retrieval
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session_id
                ON messages(session_id, timestamp)
            """)

            conn.commit()

    async def create_session(
        self,
        app_name: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Session:
        """
        Create a new session.

        Args:
            app_name: Application identifier
            user_id: User identifier
            metadata: Optional metadata dictionary

        Returns:
            New Session object
        """
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sessions (id, app_name, user_id, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                app_name,
                user_id,
                now,
                now,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()

        # Return Session object with empty messages
        return Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            messages=[]
        )

    async def get_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str
    ) -> Optional[Session]:
        """
        Retrieve an existing session with its message history.

        Args:
            app_name: Application identifier
            user_id: User identifier
            session_id: Session identifier

        Returns:
            Session object with message history, or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            # Check if session exists
            cursor = conn.execute("""
                SELECT id, app_name, user_id FROM sessions
                WHERE id = ? AND app_name = ? AND user_id = ?
            """, (session_id, app_name, user_id))

            row = cursor.fetchone()
            if not row:
                return None

            # Load message history
            cursor = conn.execute("""
                SELECT role, content, timestamp, metadata FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))

            messages = []
            for role, content, timestamp, metadata_json in cursor.fetchall():
                # Create Message object
                msg = Message(role=role, content=content)
                messages.append(msg)

        return Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            messages=messages
        )

    async def update_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        messages: List[Message]
    ) -> Session:
        """
        Update session with new messages.

        Args:
            app_name: Application identifier
            user_id: User identifier
            session_id: Session identifier
            messages: Complete list of messages (will replace existing)

        Returns:
            Updated Session object
        """
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # Update session timestamp
            conn.execute("""
                UPDATE sessions
                SET updated_at = ?
                WHERE id = ? AND app_name = ? AND user_id = ?
            """, (now, session_id, app_name, user_id))

            # Delete old messages
            conn.execute("""
                DELETE FROM messages WHERE session_id = ?
            """, (session_id,))

            # Insert new messages
            for msg in messages:
                conn.execute("""
                    INSERT INTO messages (session_id, role, content, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    msg.role,
                    msg.content,
                    now,
                    None  # We could store message metadata if needed
                ))

            conn.commit()

        return Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            messages=messages
        )

    async def delete_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str
    ) -> bool:
        """
        Delete a session and all its messages.

        Args:
            app_name: Application identifier
            user_id: User identifier
            session_id: Session identifier

        Returns:
            True if session was deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM sessions
                WHERE id = ? AND app_name = ? AND user_id = ?
            """, (session_id, app_name, user_id))

            # Messages are automatically deleted due to CASCADE
            conn.commit()

            return cursor.rowcount > 0

    async def list_sessions(
        self,
        app_name: str,
        user_id: str
    ) -> List[Session]:
        """
        List all sessions for a user.

        Args:
            app_name: Application identifier
            user_id: User identifier

        Returns:
            List of Session objects (without messages loaded)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id FROM sessions
                WHERE app_name = ? AND user_id = ?
                ORDER BY updated_at DESC
            """, (app_name, user_id))

            sessions = []
            for (session_id,) in cursor.fetchall():
                sessions.append(Session(
                    id=session_id,
                    app_name=app_name,
                    user_id=user_id,
                    messages=[]
                ))

            return sessions
