"""
Database operations for TimerMind.

This module provides functions for creating and querying timers in the database.
Includes conflict detection and scoring integration.
"""

import json
import sqlite3
from datetime import datetime
from typing import Optional

from config import DB_PATH
from utils.logging import log_event


def create_timer_in_db(
    label: str,
    description: Optional[str] = None,
    deadline: Optional[str] = None,
    estimated_duration_minutes: Optional[int] = None,
    category: str = "other",
    tags: list = None,
    destination_address: Optional[str] = None,
    origin_address: Optional[str] = None,
    departure_time: Optional[str] = None,
    arrival_time: Optional[str] = None,
    travel_time_minutes: Optional[int] = None,
    distance_km: Optional[float] = None,
    is_appointment: bool = False
) -> dict:
    """
    Create a new timer in the database.

    This function is called by the agent's create_timer tool.
    Supports location-aware timers with travel time calculations.
    Checks for timeline conflicts before creating.
    """
    # Import here to avoid circular dependencies
    from algorithms.conflict_detection import detect_timeline_conflicts, detect_nearby_timers
    from algorithms.scoring import compute_urgency_score, compute_importance_score

    tags_str = json.dumps(tags or [])
    now = datetime.utcnow().isoformat()

    # Check for timeline conflicts BEFORE creating the timer
    new_timer_data = {
        'label': label,
        'deadline': deadline,
        'destination_address': destination_address,
        'arrival_time': arrival_time,
        'departure_time': departure_time,
        'estimated_duration_minutes': estimated_duration_minutes
    }
    conflicts = detect_timeline_conflicts(new_timer_data)

    # Check for nearby timers that warrant location confirmation
    proximity_warnings = detect_nearby_timers(new_timer_data)

    # Compute scoring
    urgency, urgency_rationale = compute_urgency_score(deadline, label, description)
    importance, importance_rationale = compute_importance_score(category, label, description)

    # Combine rationales
    rationale = f"Urgency: {urgency_rationale}. Importance: {importance_rationale}"

    # Priority = weighted combination (urgency is slightly more important due to deadlines)
    priority = (urgency * 0.6) + (importance * 0.4)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("""
            INSERT INTO timers (
                label, description, deadline, estimated_duration_minutes,
                category, tags, urgency_score, importance_score, priority_score,
                rationale, created_at, updated_at,
                destination_address, origin_address, departure_time, arrival_time,
                travel_time_minutes, distance_km, last_travel_update, is_appointment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            label, description, deadline, estimated_duration_minutes,
            category, tags_str, urgency, importance, priority,
            rationale, now, now,
            destination_address, origin_address, departure_time, arrival_time,
            travel_time_minutes, distance_km, now if destination_address else None,
            1 if is_appointment else 0
        ))
        timer_id = cursor.lastrowid

    result = {
        "timer_id": timer_id,
        "label": label,
        "deadline": deadline,
        "urgency_score": urgency,
        "importance_score": importance,
        "priority_score": priority,
        "rationale": rationale,
        "status": "created"
    }

    # Add location data to result if present
    if destination_address:
        result["destination_address"] = destination_address
        result["origin_address"] = origin_address
        result["departure_time"] = departure_time
        result["arrival_time"] = arrival_time
        result["travel_time_minutes"] = travel_time_minutes
        result["distance_km"] = distance_km

    # Add conflicts to result if any were detected
    if conflicts:
        result["conflicts"] = conflicts
        result["has_conflicts"] = True
        # Simplify conflicts for logging
        conflict_summaries = [
            {
                'type': c['type'],
                'severity': c['severity'],
                'description': c['description']
            }
            for c in conflicts
        ]
        log_event("timer_created_with_conflicts", {
            "timer_id": timer_id,
            "label": label,
            "conflicts": conflict_summaries
        })
    else:
        result["has_conflicts"] = False

    # Add proximity warnings to result if any were detected
    if proximity_warnings:
        result["proximity_warnings"] = proximity_warnings
        result["has_proximity_warnings"] = True
        # Simplify proximity warnings for logging
        proximity_summaries = [
            {
                'type': w['type'],
                'severity': w['severity'],
                'suggested_question': w['suggested_question']
            }
            for w in proximity_warnings
        ]
        log_event("timer_created_with_proximity_warnings", {
            "timer_id": timer_id,
            "label": label,
            "proximity_warnings": proximity_summaries
        })
    else:
        result["has_proximity_warnings"] = False

    log_event("timer_created", result)
    return result


def list_timers_from_db() -> list:
    """Retrieve all active timers sorted by priority."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM timers
            WHERE status = 'active'
            ORDER BY priority_score DESC
        """).fetchall()

    return [dict(row) for row in rows]
