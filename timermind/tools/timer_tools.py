"""
Timer management tools for the TimerMind agent system.

These tools handle creating, retrieving, and updating timers in the database.
"""

from typing import Optional
from database.operations import create_timer_in_db, list_timers_from_db
from utils.logging import log_event
import sqlite3
from config import DB_PATH
from algorithms.scoring import compute_urgency_score, compute_importance_score
from datetime import datetime, timezone


def create_timer_tool(
    label: str,
    description: str = "",
    deadline_iso: str = "",
    estimated_duration_minutes: int = 0,
    category: str = "other",
    destination_address: str = "",
    origin_address: str = "",
    departure_time: str = "",
    arrival_time: str = "",
    travel_time_minutes: int = 0,
    distance_km: float = 0.0,
    is_appointment: bool = False
) -> dict:
    """
    Create a new timer/task in the system.

    Args:
        label: Short, clear name for the task (e.g., "Submit report")
        description: Optional longer description of what needs to be done
        deadline_iso: Optional deadline in ISO 8601 format (e.g., "2025-11-20T17:00:00")
        estimated_duration_minutes: Optional estimate of how long the task will take
        category: Task category - one of: work, personal, health, finance, maintenance, other
        destination_address: Optional destination address for location-aware timers
        origin_address: Optional origin address (defaults to user's home if not specified)
        departure_time: Optional calculated departure time (ISO 8601 format)
        arrival_time: Optional arrival time / deadline for location-based tasks
        travel_time_minutes: Optional calculated travel time in minutes
        distance_km: Optional calculated distance in kilometers
        is_appointment: Whether this is a fixed appointment (True) or flexible task (False)
                       Appointments are not easily reschedulable (dentist, meeting, pickup)
                       Tasks can be moved to accommodate appointments (grocery, errands)

    Returns:
        dict with timer_id, computed scores, and creation status
    """
    # CRITICAL VALIDATION: Prevent timers with no deadline
    # User's directive: "Timer with no deadline is a concept we should go to great lengths to avoid"
    if not deadline_iso or deadline_iso.strip() == "":
        error_msg = (
            "ERROR: Cannot create timer without a deadline. Every task must have a specific time. "
            "Please extract or infer a deadline from the user's message. "
            "Examples: 'tomorrow' → tomorrow at 12:00 PM, 'next week' → next Monday at 5:00 PM, "
            "'later today' → today at 5:00 PM. If you truly cannot determine when, ask the user."
        )
        log_event("tool_error_no_deadline", {
            "tool": "create_timer",
            "label": label,
            "error": "Missing deadline_iso parameter"
        })
        return {
            "status": "error",
            "error": error_msg,
            "label": label
        }

    log_event("tool_called", {
        "tool": "create_timer",
        "args": {"label": label, "deadline_iso": deadline_iso, "category": category, "destination": destination_address}
    })

    result = create_timer_in_db(
        label=label,
        description=description if description else None,
        deadline=deadline_iso if deadline_iso else None,
        estimated_duration_minutes=estimated_duration_minutes if estimated_duration_minutes > 0 else None,
        category=category,
        tags=[],
        destination_address=destination_address if destination_address else None,
        origin_address=origin_address if origin_address else None,
        departure_time=departure_time if departure_time else None,
        arrival_time=arrival_time if arrival_time else None,
        travel_time_minutes=travel_time_minutes if travel_time_minutes > 0 else None,
        distance_km=distance_km if distance_km > 0.0 else None,
        is_appointment=is_appointment
    )
    return result


def get_current_timers_tool() -> dict:
    """
    Retrieve all current active timers sorted by priority.
    Also includes recently completed/deleted tasks for context.

    Returns:
        dict containing list of active timer objects and recently completed ones
    """
    log_event("tool_called", {"tool": "get_current_timers"})
    timers = list_timers_from_db()

    # Also get recently completed/deleted tasks (last 24 hours) for context
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        recent = conn.execute("""
            SELECT * FROM timers
            WHERE status IN ('completed', 'deleted')
            AND datetime(updated_at) > datetime('now', '-24 hours')
            ORDER BY updated_at DESC
            LIMIT 10
        """).fetchall()

    recent_tasks = [dict(row) for row in recent]

    return {
        "active_timers": timers,
        "count": len(timers),
        "recently_completed": recent_tasks
    }


def update_timer_tool(timer_id: int, status: str = "", category: str = "", deadline_iso: str = "") -> dict:
    """
    Update an existing timer's properties.

    Args:
        timer_id: ID of the timer to update
        status: New status (active, completed, snoozed, deleted)
        category: New category
        deadline_iso: New deadline in ISO 8601 format

    Returns:
        dict with update status and new scores if deadline changed
    """
    log_event("tool_called", {"tool": "update_timer", "timer_id": timer_id, "deadline_iso": deadline_iso})

    with sqlite3.connect(DB_PATH) as conn:
        updates = []
        params = []
        new_urgency = None
        new_importance = None

        if status:
            updates.append("status = ?")
            params.append(status)
        if category:
            updates.append("category = ?")
            params.append(category)
            # Fetch timer info for importance scoring when category changes
            timer_row = conn.execute("SELECT label, description FROM timers WHERE id = ?", (timer_id,)).fetchone()
            if timer_row:
                label, description = timer_row
                # Recompute importance score with new category
                new_importance, _ = compute_importance_score(category, label, description)
                updates.append("importance_score = ?")
                params.append(new_importance)
        if deadline_iso:
            updates.append("deadline = ?")
            params.append(deadline_iso)
            # Fetch timer info for urgency scoring
            timer_row = conn.execute("SELECT label, description FROM timers WHERE id = ?", (timer_id,)).fetchone()
            if timer_row:
                label, description = timer_row
                # Recompute urgency score
                new_urgency, _ = compute_urgency_score(deadline_iso, label, description)
                updates.append("urgency_score = ?")
                params.append(new_urgency)

        # Recalculate priority if either urgency or importance changed
        if new_urgency is not None or new_importance is not None:
            # Need to fetch current scores to calculate priority
            current = conn.execute(
                "SELECT urgency_score, importance_score FROM timers WHERE id = ?",
                (timer_id,)
            ).fetchone()
            if current:
                urgency = new_urgency if new_urgency is not None else current[0]
                importance = new_importance if new_importance is not None else current[1]
                # Use correct weighted priority: urgency * 0.6 + importance * 0.4
                priority = (urgency * 0.6) + (importance * 0.4)
                updates.append("priority_score = ?")
                params.append(priority)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(timer_id)
            conn.execute(f"UPDATE timers SET {', '.join(updates)} WHERE id = ?", params)

    result = {"timer_id": timer_id, "updated": True}
    if new_urgency is not None:
        result["new_urgency_score"] = new_urgency
    if new_importance is not None:
        result["new_importance_score"] = new_importance
    if deadline_iso:
        result["deadline"] = deadline_iso

    return result
