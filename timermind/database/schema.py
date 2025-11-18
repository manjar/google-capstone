"""
Database schema initialization for TimerMind.

This module handles the initial creation of database tables.
For schema migrations, see database/migrations.py.
"""

import sqlite3
from config import DB_PATH
from utils.logging import log_event


def init_database():
    """
    Initialize SQLite database with timer schema.

    Design Decision: SQLite for local timer storage because it's simple,
    familiar, and sufficient for MVP. Vertex AI handles session/memory.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS timers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                description TEXT,
                deadline TEXT,
                estimated_duration_minutes INTEGER,
                category TEXT DEFAULT 'other',
                tags TEXT,
                urgency_score REAL DEFAULT 0.5,
                importance_score REAL DEFAULT 0.5,
                priority_score REAL DEFAULT 0.5,
                rationale TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        log_event("database_initialized", {"db_path": str(DB_PATH)})
