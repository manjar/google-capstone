"""
Preference management tools for the TimerMind agent system.

These tools handle user preferences, learning, and timer importance recalculation.
"""

import json
import sqlite3
from datetime import datetime, timezone
from utils.logging import log_event
from config import DB_PATH
from algorithms.scoring import compute_importance_score


def get_user_preferences_tool() -> dict:
    """
    Retrieve current user preferences for task prioritization.

    Returns:
        dict containing preference weights and rules
    """
    log_event("tool_called", {"tool": "get_user_preferences"})

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT key, value FROM preferences").fetchall()

    prefs = {row["key"]: json.loads(row["value"]) for row in rows}

    # Return defaults if no preferences set
    if not prefs:
        prefs = {
            "rules": []
        }

    return {"preferences": prefs}


def add_preference_rule_tool(rule_description: str, rule_type: str, condition: str, action: str) -> dict:
    """
    Add a new preference rule for task prioritization.

    Args:
        rule_description: Human-readable description of the rule
        rule_type: Type of rule (boost, suppress, filter)
        condition: When the rule applies (e.g., "category=work AND day=weekend")
        action: What to do (e.g., "multiply_priority=0.5")

    Returns:
        dict with rule creation confirmation
    """
    log_event("tool_called", {"tool": "add_preference_rule", "rule_type": rule_type})

    # Get current rules
    prefs = get_user_preferences_tool()["preferences"]
    rules = prefs.get("rules", [])

    # Add new rule
    new_rule = {
        "id": len(rules) + 1,
        "description": rule_description,
        "type": rule_type,
        "condition": condition,
        "action": action,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    rules.append(new_rule)

    # Save to database
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO preferences (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
        """, ("rules", json.dumps(rules), now, json.dumps(rules), now))

    return {"rule_id": new_rule["id"], "description": rule_description, "created": True}


def recalculate_timer_importance_tool(timer_id: int) -> dict:
    """
    Recalculate the importance score for an existing timer.

    This is useful when user preferences have changed and you want to update
    the importance of existing timers to reflect new priorities.

    Args:
        timer_id: ID of the timer to recalculate importance for

    Returns:
        dict with timer_id, old and new importance scores, and updated priority
    """
    log_event("tool_called", {"tool": "recalculate_timer_importance", "timer_id": timer_id})

    with sqlite3.connect(DB_PATH) as conn:
        # Fetch timer data
        timer_row = conn.execute(
            "SELECT label, description, category, urgency_score, importance_score FROM timers WHERE id = ?",
            (timer_id,)
        ).fetchone()

        if not timer_row:
            return {
                "success": False,
                "error": f"Timer {timer_id} not found"
            }

        label, description, category, old_urgency, old_importance = timer_row

        # Recalculate importance score
        new_importance, importance_rationale = compute_importance_score(category, label, description)

        # Recalculate priority with correct weighting
        new_priority = (old_urgency * 0.6) + (new_importance * 0.4)

        # Update database
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            UPDATE timers
            SET importance_score = ?, priority_score = ?, updated_at = ?
            WHERE id = ?
        """, (new_importance, new_priority, now, timer_id))

    return {
        "timer_id": timer_id,
        "old_importance_score": old_importance,
        "new_importance_score": new_importance,
        "new_priority_score": new_priority,
        "rationale": importance_rationale,
        "updated": True
    }


def set_default_location_tool(address: str) -> dict:
    """
    Set the user's default location (home address) for location-aware timers.

    This address will be used as the default origin for travel time calculations
    when no origin is specified.

    Args:
        address: Full address of user's home/default location (e.g., "123 Main St, Campbell, CA 95008")

    Returns:
        dict with confirmation of location being set
    """
    log_event("tool_called", {"tool": "set_default_location", "address": address})

    # Save to database
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO preferences (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
        """, ("default_location", json.dumps(address), now, json.dumps(address), now))

    return {
        "success": True,
        "message": f"Default location set to: {address}",
        "location": address
    }
