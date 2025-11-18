"""
Database migrations for TimerMind.

This module contains functions to migrate existing databases to support new features.
Each migration function is designed to be idempotent (safe to run multiple times).
"""

import sqlite3
from config import DB_PATH


def migrate_add_rationale_column():
    """
    Add rationale column to timers table if it doesn't exist.

    This migration supports storing the AI's reasoning for urgency/importance scores.
    """
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("ALTER TABLE timers ADD COLUMN rationale TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists


def migrate_add_location_fields():
    """
    Add location-aware fields for travel time calculations.

    This migration supports location-based timers with Google Maps integration.
    """
    with sqlite3.connect(DB_PATH) as conn:
        location_columns = [
            ("destination_address", "TEXT"),
            ("origin_address", "TEXT"),
            ("departure_time", "TEXT"),
            ("arrival_time", "TEXT"),
            ("travel_time_minutes", "INTEGER"),
            ("distance_km", "REAL"),
            ("last_travel_update", "TEXT"),
            ("is_appointment", "INTEGER DEFAULT 0")  # 1 = fixed appointment, 0 = flexible task
        ]
        for col_name, col_type in location_columns:
            try:
                conn.execute(f"ALTER TABLE timers ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists


def run_all_migrations():
    """
    Run all database migrations.

    Call this function to ensure the database schema is up to date with all features.
    """
    migrate_add_rationale_column()
    migrate_add_location_fields()
