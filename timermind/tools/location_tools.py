"""
Location-aware tools for the TimerMind agent system.

These tools handle travel time calculations and location-based timer features.
"""

import json
import sqlite3
from services.google_maps_service import get_maps_service
from dateutil import parser as date_parser
from utils.logging import log_event
from config import DB_PATH


def calculate_travel_time_tool(
    destination: str,
    arrival_time_iso: str,
    origin: str = ""
) -> dict:
    """
    Calculate travel time and recommended departure time for a location-based timer.

    Args:
        destination: Destination address (e.g., "Naschmarkt, Campbell, CA")
        arrival_time_iso: When you need to arrive (ISO 8601 format)
        origin: Optional origin address (defaults to user's home address from preferences)

    Returns:
        dict with travel_time_minutes, distance_km, departure_time_iso, origin_address, destination_address
        or error message if Maps API not configured or calculation fails
    """
    log_event("tool_called", {
        "tool": "calculate_travel_time",
        "destination": destination,
        "arrival_time": arrival_time_iso
    })

    maps_service = get_maps_service()

    if not maps_service.is_enabled():
        return {
            "success": False,
            "error": "Location features not available - GOOGLE_MAPS_API_KEY not configured",
            "travel_time_minutes": 0,
            "distance_km": 0.0
        }

    # Get origin (default to user's home if not specified)
    if not origin:
        # Try to get default location from preferences
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT value FROM preferences WHERE key = ?",
                ("default_location",)
            ).fetchone()
            if row:
                origin = json.loads(row[0])
            else:
                return {
                    "success": False,
                    "error": "No origin specified and no default location set in preferences",
                    "travel_time_minutes": 0,
                    "distance_km": 0.0
                }

    # Parse arrival time
    try:
        arrival_time = date_parser.isoparse(arrival_time_iso)
    except Exception as e:
        return {
            "success": False,
            "error": f"Invalid arrival_time format: {e}",
            "travel_time_minutes": 0,
            "distance_km": 0.0
        }

    # Calculate travel time
    result = maps_service.calculate_departure_time(
        origin=origin,
        destination=destination,
        arrival_time=arrival_time
    )

    if not result:
        return {
            "success": False,
            "error": f"Could not calculate route from '{origin}' to '{destination}'",
            "travel_time_minutes": 0,
            "distance_km": 0.0
        }

    departure_time, travel_minutes, distance_km = result

    return {
        "success": True,
        "travel_time_minutes": travel_minutes,
        "distance_km": distance_km,
        "departure_time_iso": departure_time.isoformat(),
        "arrival_time_iso": arrival_time_iso,
        "origin_address": origin,
        "destination_address": destination
    }
