"""
TimerMind - AI-Powered Task Prioritization Agent
Main application entry point with FastAPI server.

This is the initial prototype focused on proving out core agent behaviors.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

# Load environment variables
load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in .env file")

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
# Maps API is optional - location features will be disabled if not configured
if not GOOGLE_MAPS_API_KEY:
    logger.warning("GOOGLE_MAPS_API_KEY not found in .env - location-aware features will be disabled")

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
TEMPLATES_DIR = BASE_DIR / "templates"
DB_PATH = DATA_DIR / "timermind.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Jinja2 template environment
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

# =============================================================================
# Structured Logging Setup (Observability)
# =============================================================================

def setup_logging():
    """
    Configure structured JSON logging for agent observability.

    Design Decision: JSON format allows easy parsing and analysis of agent
    behavior patterns. Logs to both console (for debugging) and file (for
    post-hoc analysis).
    """
    logger = logging.getLogger("timermind")
    logger.setLevel(logging.INFO)

    # JSON formatter for structured logs
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_obj = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            # Add extra fields if present
            if hasattr(record, "event"):
                log_obj["event"] = record.event
            if hasattr(record, "data"):
                log_obj["data"] = record.data
            return json.dumps(log_obj)

    # Console handler (human readable for debugging)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )
    console_handler.setFormatter(console_formatter)

    # File handler (structured JSON for analysis)
    log_file = LOGS_DIR / f"timermind_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(JSONFormatter())

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

logger = setup_logging()

def log_event(event_type: str, data: dict):
    """Log a structured event with associated data."""
    extra = {"event": event_type, "data": data}
    logger.info(f"{event_type}: {json.dumps(data)}", extra=extra)

# =============================================================================
# Database Setup
# =============================================================================

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

        # Add rationale column if it doesn't exist (for existing databases)
        try:
            conn.execute("ALTER TABLE timers ADD COLUMN rationale TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Add location-aware fields for travel time calculations
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        log_event("database_initialized", {"db_path": str(DB_PATH)})

init_database()

# =============================================================================
# Mock Data (Calendar/Todo sources)
# =============================================================================

MOCK_CALENDAR_DATA = [
    {
        "title": "Team standup",
        "start": "2025-11-18T09:00:00",
        "end": "2025-11-18T09:30:00",
        "recurring": "daily"
    },
    {
        "title": "Project review meeting",
        "start": "2025-11-20T14:00:00",
        "end": "2025-11-20T15:00:00"
    }
]

MOCK_TODO_DATA = [
    {
        "title": "Review PR #123",
        "due": "2025-11-19",
        "priority": "high"
    },
    {
        "title": "Update documentation",
        "due": "2025-11-22",
        "priority": "medium"
    }
]

# =============================================================================
# Timer Operations (Tools will call these)
# =============================================================================

def detect_timeline_conflicts(
    new_timer_data: dict,
    existing_timers: Optional[list] = None
) -> list[dict]:
    """
    Detect spatiotemporal conflicts between a new timer and existing timers.

    Uses actual Google Maps travel times to detect impossible timelines.

    Checks for:
    1. Location conflicts - being at different locations at overlapping times
    2. Travel time conflicts - insufficient time to travel between consecutive locations (uses real Maps API data)
    3. Impossible timelines - need to leave before a previous event ends

    Args:
        new_timer_data: Dict with new timer info (label, deadline, destination_address,
                       arrival_time, departure_time, etc.)
        existing_timers: Optional list of existing timers (if None, fetches from DB)

    Returns:
        List of conflict dicts, each containing:
        - type: "location_overlap", "insufficient_travel_time", or "impossible_timeline"
        - description: Human-readable description
        - conflicting_timer: The timer that conflicts
        - severity: "critical" or "warning"
        - actual_travel_time: Minutes needed (if calculated)
        - time_available: Minutes available
    """
    from dateutil import parser as date_parser
    from services.google_maps_service import get_maps_service

    conflicts = []
    maps_service = get_maps_service()

    # Get existing timers if not provided
    if existing_timers is None:
        existing_timers = list_timers_from_db()

    # Parse new timer times
    new_deadline = new_timer_data.get('deadline')
    new_arrival = new_timer_data.get('arrival_time')
    new_departure = new_timer_data.get('departure_time')
    new_destination = new_timer_data.get('destination_address')
    new_label = new_timer_data.get('label', 'New timer')
    new_duration_minutes = new_timer_data.get('estimated_duration_minutes', 0)

    if not new_deadline and not new_arrival:
        # No deadline, can't check conflicts
        return conflicts

    # Use arrival time if it's a location-based timer, otherwise use deadline
    new_time_str = new_arrival or new_deadline

    try:
        new_time = date_parser.isoparse(new_time_str)
        if new_departure:
            new_departure_dt = date_parser.isoparse(new_departure)
        else:
            new_departure_dt = None

        # Calculate end time for appointments/events with duration
        # new_time is the start time (arrival or deadline)
        # end time = start time + duration
        from datetime import timedelta
        new_end_time = new_time + timedelta(minutes=new_duration_minutes) if new_duration_minutes else new_time
    except:
        return conflicts

    # Build timeline of all timers with times
    timeline = []
    for timer in existing_timers:
        timer_deadline = timer.get('deadline')
        timer_arrival = timer.get('arrival_time')
        timer_departure = timer.get('departure_time')
        timer_destination = timer.get('destination_address')
        timer_duration_minutes = timer.get('estimated_duration_minutes', 0)

        if not timer_deadline and not timer_arrival:
            continue

        # Use arrival time for location-based timers, deadline otherwise
        timer_time_str = timer_arrival or timer_deadline
        try:
            timer_time = date_parser.isoparse(timer_time_str)
            timer_departure_dt = date_parser.isoparse(timer_departure) if timer_departure else None
            timer_arrival_dt = date_parser.isoparse(timer_arrival) if timer_arrival else None

            # Calculate end time for appointments/events with duration
            from datetime import timedelta
            timer_end_time = timer_time + timedelta(minutes=timer_duration_minutes) if timer_duration_minutes else timer_time
        except:
            continue

        timeline.append({
            'timer': timer,
            'time': timer_time,
            'end_time': timer_end_time,
            'duration_minutes': timer_duration_minutes,
            'arrival_time': timer_arrival,
            'arrival_dt': timer_arrival_dt,
            'departure_time': timer_departure,
            'departure_dt': timer_departure_dt,
            'destination': timer_destination,
            'label': timer.get('label', 'Timer')
        })

    # Sort timeline by time
    timeline.sort(key=lambda x: x['time'])

    # Check for conflicts with each existing timer
    for timeline_item in timeline:
        existing_timer = timeline_item['timer']
        existing_time = timeline_item['time']
        existing_end_time = timeline_item['end_time']
        existing_duration = timeline_item['duration_minutes']
        existing_destination = timeline_item['destination']
        existing_label = timeline_item['label']
        existing_arrival_dt = timeline_item['arrival_dt']
        existing_departure_dt = timeline_item['departure_dt']

        # Skip if neither timer has a location
        if not new_destination and not existing_destination:
            continue

        # Check 1: Impossible timeline - need to depart before existing event ends
        if existing_time < new_time and new_departure_dt:
            # Existing event is before new event
            # Check if we need to leave for new event before existing event completes
            # Use end time if appointment has duration, otherwise use start time
            if new_departure_dt < existing_end_time:
                time_gap_minutes = (existing_end_time - new_departure_dt).total_seconds() / 60
                duration_msg = f" (ends at {existing_end_time.strftime('%I:%M %p')})" if existing_duration else ""
                conflicts.append({
                    'type': 'impossible_timeline',
                    'description': f"You need to leave for '{new_label}' at {new_departure_dt.strftime('%I:%M %p')}, but '{existing_label}'{duration_msg} doesn't finish until {existing_end_time.strftime('%I:%M %p')} ({int(abs(time_gap_minutes))} minutes later)",
                    'conflicting_timer': existing_timer,
                    'severity': 'critical',
                    'time_available': -int(time_gap_minutes)  # Negative = impossible
                })

        # Check 2: Insufficient travel time using ACTUAL Maps API calculation
        # After new event, check if there's time to get to existing event
        if new_time < existing_time and new_destination and existing_destination and existing_departure_dt:
            # New event is before existing event
            # Calculate actual travel time from new destination to existing destination
            # Use end time if new event has duration
            time_available_minutes = (existing_departure_dt - new_end_time).total_seconds() / 60

            # Only check if events are within reasonable time of each other (same day)
            if time_available_minutes > 0 and time_available_minutes < 720:  # Within 12 hours
                # Use Maps API to get actual travel time
                if maps_service.is_enabled():
                    result = maps_service.calculate_departure_time(
                        origin=new_destination,
                        destination=existing_destination,
                        arrival_time=existing_time  # When we need to arrive at existing event
                    )

                    if result:
                        _, actual_travel_minutes, _ = result

                        # Check if we have enough time
                        if time_available_minutes < actual_travel_minutes:
                            shortfall = actual_travel_minutes - time_available_minutes
                            new_duration_msg = f" ({new_duration_minutes} min duration, ends {new_end_time.strftime('%I:%M %p')})" if new_duration_minutes else f" (ends {new_end_time.strftime('%I:%M %p')})"
                            conflicts.append({
                                'type': 'insufficient_travel_time',
                                'description': f"After '{new_label}' at {new_destination}{new_duration_msg}, you need to be at '{existing_label}' in {existing_destination} by {existing_departure_dt.strftime('%I:%M %p')}. Travel time is {int(actual_travel_minutes)} minutes, but you only have {int(time_available_minutes)} minutes available (short by {int(shortfall)} minutes)",
                                'conflicting_timer': existing_timer,
                                'severity': 'critical' if shortfall > 5 else 'warning',
                                'actual_travel_time': int(actual_travel_minutes),
                                'time_available': int(time_available_minutes)
                            })

        # Check 3: After existing event, check if there's time to get to new event
        if existing_time < new_time and new_destination and existing_destination and new_departure_dt:
            # Existing event is before new event
            # Calculate actual travel time from existing destination to new destination
            # Use end time if existing event has duration
            time_available_minutes = (new_departure_dt - existing_end_time).total_seconds() / 60

            # Only check if events are within reasonable time of each other
            if time_available_minutes > 0 and time_available_minutes < 720:  # Within 12 hours
                # Use Maps API to get actual travel time
                if maps_service.is_enabled():
                    result = maps_service.calculate_departure_time(
                        origin=existing_destination,
                        destination=new_destination,
                        arrival_time=new_time  # When we need to arrive at new event
                    )

                    if result:
                        _, actual_travel_minutes, _ = result

                        # Check if we have enough time
                        if time_available_minutes < actual_travel_minutes:
                            shortfall = actual_travel_minutes - time_available_minutes
                            existing_duration_msg = f" ({existing_duration} min duration, ends {existing_end_time.strftime('%I:%M %p')})" if existing_duration else f" (ends {existing_end_time.strftime('%I:%M %p')})"
                            conflicts.append({
                                'type': 'insufficient_travel_time',
                                'description': f"After '{existing_label}' at {existing_destination}{existing_duration_msg}, you need to be at '{new_label}' in {new_destination} by {new_departure_dt.strftime('%I:%M %p')}. Travel time is {int(actual_travel_minutes)} minutes, but you only have {int(time_available_minutes)} minutes available (short by {int(shortfall)} minutes)",
                                'conflicting_timer': existing_timer,
                                'severity': 'critical' if shortfall > 5 else 'warning',
                                'actual_travel_time': int(actual_travel_minutes),
                                'time_available': int(time_available_minutes)
                            })

    return conflicts


def detect_nearby_timers(
    new_timer_data: dict,
    existing_timers: Optional[list] = None,
    proximity_window_hours: float = 3.0
) -> list[dict]:
    """
    Detect timers that are temporally close to a new timer.

    This function identifies "nearby" events that warrant location confirmation
    to prevent potential conflicts. It flags cases where:
    - Two timers are within proximity_window_hours of each other
    - At least one has a location specified
    - User should confirm locations are compatible

    Args:
        new_timer_data: Dict with 'label', 'deadline', 'destination_address', etc.
        existing_timers: List of existing timer dicts to check against
        proximity_window_hours: Time window (hours) to consider "nearby" (default: 3.0)

    Returns:
        List of proximity warnings with suggested confirmation questions
    """
    from dateutil import parser as date_parser

    proximity_warnings = []

    # Parse new timer data
    new_label = new_timer_data.get('label', 'New timer')
    new_deadline_str = new_timer_data.get('deadline')
    new_destination = new_timer_data.get('destination_address')
    new_arrival_str = new_timer_data.get('arrival_time')
    new_departure_str = new_timer_data.get('departure_time')

    if not new_deadline_str:
        return proximity_warnings

    try:
        new_time = date_parser.isoparse(new_deadline_str)
    except (ValueError, TypeError):
        return proximity_warnings

    # Determine the "event time" for the new timer (departure if location-based, else deadline)
    new_event_time = new_time
    if new_departure_str:
        try:
            new_event_time = date_parser.isoparse(new_departure_str)
        except (ValueError, TypeError):
            pass

    # Fetch existing timers if not provided
    if existing_timers is None:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("""
                SELECT id, label, deadline, destination_address, arrival_time, departure_time, status
                FROM timers
                WHERE status != 'completed'
            """).fetchall()
            existing_timers = [
                {
                    'id': row[0],
                    'label': row[1],
                    'deadline': row[2],
                    'destination_address': row[3],
                    'arrival_time': row[4],
                    'departure_time': row[5],
                    'status': row[6]
                }
                for row in rows
            ]

    proximity_window_minutes = proximity_window_hours * 60

    for existing_timer in existing_timers:
        existing_label = existing_timer.get('label', 'Existing timer')
        existing_deadline = existing_timer.get('deadline')
        existing_destination = existing_timer.get('destination_address')
        existing_arrival = existing_timer.get('arrival_time')
        existing_departure = existing_timer.get('departure_time')

        if not existing_deadline:
            continue

        try:
            existing_time = date_parser.isoparse(existing_deadline)
        except (ValueError, TypeError):
            continue

        # Determine event time for existing timer
        existing_event_time = existing_time
        if existing_departure:
            try:
                existing_event_time = date_parser.isoparse(existing_departure)
            except (ValueError, TypeError):
                pass

        # Calculate time difference
        time_diff_minutes = abs((new_event_time - existing_event_time).total_seconds() / 60)

        # Check if timers are within proximity window
        if time_diff_minutes <= proximity_window_minutes:
            # Only flag if at least one has a location
            has_location = new_destination or existing_destination

            if has_location:
                # Build proximity warning
                time_diff_hours = time_diff_minutes / 60

                # Determine the relationship
                if time_diff_minutes < 30:
                    proximity_type = 'very_close'  # Less than 30 minutes apart
                    severity = 'high'
                elif time_diff_minutes < 120:
                    proximity_type = 'close'  # 30 min to 2 hours
                    severity = 'medium'
                else:
                    proximity_type = 'nearby'  # 2-3 hours
                    severity = 'low'

                # Format time information
                if new_event_time < existing_event_time:
                    order = f"{new_label} ({new_event_time.strftime('%I:%M %p')}) is {int(time_diff_minutes)} minutes before {existing_label} ({existing_event_time.strftime('%I:%M %p')})"
                else:
                    order = f"{new_label} ({new_event_time.strftime('%I:%M %p')}) is {int(time_diff_minutes)} minutes after {existing_label} ({existing_event_time.strftime('%I:%M %p')})"

                # Create location summary
                location_info = []
                if new_destination:
                    location_info.append(f"'{new_label}' is at {new_destination}")
                else:
                    location_info.append(f"'{new_label}' has no location specified")

                if existing_destination:
                    location_info.append(f"'{existing_label}' is at {existing_destination}")
                else:
                    location_info.append(f"'{existing_label}' has no location specified")

                location_summary = ". ".join(location_info)

                # Create suggested question
                if new_destination and existing_destination:
                    if new_destination.lower() == existing_destination.lower():
                        suggested_question = f"Both events are at the same location ({new_destination}). Is this correct?"
                    else:
                        suggested_question = f"You have two events at different locations within {int(time_diff_hours)} hours. Can you confirm the locations are correct?"
                elif new_destination and not existing_destination:
                    suggested_question = f"'{new_label}' is at {new_destination}, but '{existing_label}' has no location. Where is '{existing_label}'?"
                else:  # existing has location, new doesn't
                    suggested_question = f"'{existing_label}' is at {existing_destination}, but '{new_label}' has no location. Where is '{new_label}'?"

                proximity_warnings.append({
                    'type': proximity_type,
                    'severity': severity,
                    'time_difference_minutes': int(time_diff_minutes),
                    'nearby_timer': existing_timer,
                    'order': order,
                    'location_summary': location_summary,
                    'suggested_question': suggested_question,
                    'description': f"{order}. {location_summary}"
                })

    return proximity_warnings


def compute_urgency_score(deadline_str: Optional[str], label: str = "", description: Optional[str] = None) -> tuple[float, str]:
    """
    Compute urgency using urgency_agent for intelligent assessment.

    Uses the urgency agent to analyze deadline and context.

    Returns:
        tuple[float, str]: (score 0.0-1.0, rationale explaining the score)
    """
    global _urgency_score_result
    _urgency_score_result = None

    now = datetime.now().isoformat()

    # Prepare context for the agent
    prompt = f"""Analyze the urgency of this task:

Task: {label}
Description: {description or "N/A"}
Deadline: {deadline_str if deadline_str else "No deadline specified"}
Current time: {now}

Please assess the urgency score and provide your rationale."""

    try:
        import google.generativeai as genai
        import json

        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Enhanced prompt with buffer ratio logic and few-shot examples
        enhanced_prompt = f"""{prompt}

URGENCY SCORING LOGIC:
1. Calculate time remaining until deadline
2. Estimate task effort from description:
   - Trivial (5-15 min): "get mail", "phone call", "quick email"
   - Simple (30-60 min): "appointment", "shopping", "review doc"
   - Moderate (2-4 hrs): "presentation", "report", "meeting prep"
   - Complex (1-3 days): "research", "planning", "major deliverable"
3. Compute buffer ratio = time_remaining / estimated_effort
4. Score based on buffer:
   - < 1.5x buffer: 0.7-1.0 (HIGH - tight deadline)
   - 1.5-3x buffer: 0.4-0.7 (MEDIUM - adequate time)
   - > 3x buffer: 0.1-0.4 (LOW - plenty of time)
   - Overdue/< 1hr: 1.0 (CRITICAL)
   - No deadline: 0.1-0.3 (LOW)

FEW-SHOT EXAMPLES:
Example 1:
Task: "Get the mail from the mailbox"
Deadline: Tomorrow evening (24 hours away)
→ {{"score": 0.2, "rationale": "Trivial task (5 min effort) with large time buffer (24 hours), resulting in very low urgency"}}

Example 2:
Task: "Have dinner ready"
Deadline: 6:30 PM (2.5 hours away)
→ {{"score": 0.75, "rationale": "Moderate task (45-60 min cooking) with limited buffer (2.5 hrs / 1 hr = 2.5x), creating moderate-high urgency"}}

Example 3:
Task: "Write and submit quarterly financial report"
Deadline: Friday at 5 PM (4 days away)
→ {{"score": 0.85, "rationale": "Complex task (2-3 days effort) with tight buffer ratio (4 days / 2.5 days = 1.6x), indicating high urgency"}}

Example 4:
Task: "Complete critical project presentation"
Deadline: 2 hours from now
→ {{"score": 0.95, "rationale": "Moderate-complex task (2-4 hrs effort) with insufficient time buffer (2 hrs / 3 hrs = 0.67x), creating critical urgency"}}

Example 5:
Task: "Schedule dentist appointment"
Deadline: Next month
→ {{"score": 0.15, "rationale": "Simple task (15 min effort) with very large time buffer (30 days), resulting in very low urgency"}}

Respond with JSON only:
{{"score": 0.0-1.0, "rationale": "Brief explanation mentioning buffer ratio, time, and effort"}}"""

        result = model.generate_content(enhanced_prompt)
        response_text = result.text.strip()

        # Extract JSON from markdown if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        data = json.loads(response_text)
        score = max(0.0, min(1.0, float(data["score"])))
        rationale = data["rationale"]

        return score, rationale

    except Exception as e:
        log_event("urgency_scoring_error", {"error": str(e), "deadline": deadline_str})
        # Fallback to simple logic if scoring fails
        if not deadline_str:
            return 0.3, "No deadline provided"
        return 0.5, f"Error in urgency assessment: {str(e)}"

def compute_importance_score(category: str, label: str, description: Optional[str] = None) -> tuple[float, str]:
    """
    Compute importance using importance_agent for intelligent assessment.

    Uses the importance agent to analyze task context and category.

    Returns:
        tuple[float, str]: (score 0.0-1.0, rationale explaining the score)
    """
    global _importance_score_result
    _importance_score_result = None

    # Prepare context for the agent
    prompt = f"""Analyze the importance of this task:

Task: {label}
Description: {description or "N/A"}
Category: {category}

Please assess the importance score and provide your rationale."""

    try:
        import google.generativeai as genai
        import json

        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Enhanced prompt with importance criteria and few-shot examples
        enhanced_prompt = f"""{prompt}

IMPORTANCE SCORING LOGIC:
Analyze task importance based on:
1. Keywords indicating high importance:
   - "critical", "urgent", "important", "asap", "emergency"
   - "vital", "essential", "crucial", "mandatory"
2. Keywords indicating low importance:
   - "maybe", "optional", "nice to have", "someday"
   - "if time", "low priority", "when possible"
3. Context clues:
   - Health matters: usually high importance
   - Financial deadlines: high importance
   - Work deliverables: moderate-high importance
   - Routine personal tasks: moderate importance
   - Optional activities: low importance
4. Category: {category}

Importance scoring:
- 0.9-1.0: Critical (health emergencies, critical work deliverables)
- 0.7-0.9: High importance (important meetings, significant work)
- 0.5-0.7: Moderate importance (routine work, regular personal tasks)
- 0.3-0.5: Low importance (optional tasks, low priority items)
- 0.0-0.3: Trivial (nice-to-haves, very optional)

FEW-SHOT EXAMPLES:
Example 1:
Task: "Get the mail from the mailbox"
Category: personal
→ {{"score": 0.3, "rationale": "Routine personal task with no critical consequences if delayed, indicating low importance"}}

Example 2:
Task: "Have dinner ready"
Category: personal
→ {{"score": 0.5, "rationale": "Daily necessity task with moderate importance for health and routine maintenance"}}

Example 3:
Task: "Write and submit quarterly financial report"
Category: work
→ {{"score": 0.85, "rationale": "Critical work deliverable with significant business impact and mandatory deadline"}}

Example 4:
Task: "Complete critical project presentation"
Category: work
→ {{"score": 0.9, "rationale": "Explicitly marked as critical work task with high-stakes presentation implications"}}

Example 5:
Task: "Schedule dentist appointment"
Category: health
→ {{"score": 0.7, "rationale": "Health-related task with preventive care importance, though not emergency level"}}

Example 6:
Task: "Review optional training materials"
Category: work
→ {{"score": 0.35, "rationale": "Optional professional development with low immediate importance"}}

Respond with JSON only:
{{"score": 0.0-1.0, "rationale": "Brief explanation of why this task has this importance level"}}"""

        result = model.generate_content(enhanced_prompt)
        response_text = result.text.strip()

        # Extract JSON from markdown if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        data = json.loads(response_text)
        score = max(0.0, min(1.0, float(data["score"])))
        rationale = data["rationale"]

        return score, rationale

    except Exception as e:
        log_event("importance_scoring_error", {"error": str(e), "category": category})
        # Fallback to simple default
        return 0.5, f"Error in importance assessment: {str(e)}"

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
    tags_str = json.dumps(tags or [])
    now = datetime.utcnow().isoformat()

    # Check for timeline conflicts BEFORE creating the timer
    new_timer_data = {
        'label': label,
        'deadline': deadline,
        'destination_address': destination_address,
        'arrival_time': arrival_time,
        'departure_time': departure_time
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

# =============================================================================
# Agent Setup (Google ADK)
# =============================================================================

import google.generativeai as genai
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.tools.load_memory_tool import LoadMemoryTool
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

log_event("gemini_configured", {"status": "success"})

# =============================================================================
# Tool Definitions for Agents
# =============================================================================

# Timer Management Tools (for Extraction Agent)
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
    from services.google_maps_service import get_maps_service
    from dateutil import parser as date_parser

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

# Preference Management Tools (for Preference Agent)
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

# Scoring Tools (for Importance and Urgency Agents)
# Global variables to store agent scoring results
_importance_score_result = None
_urgency_score_result = None

def submit_importance_score_tool(importance_score: float, rationale: str) -> dict:
    """
    Submit an importance score assessment for a task.

    Args:
        importance_score: Score from 0.0 to 1.0 indicating task importance
        rationale: Explanation of why this score was assigned

    Returns:
        dict confirming score submission
    """
    global _importance_score_result

    # Clamp score to valid range
    score = max(0.0, min(1.0, importance_score))

    _importance_score_result = {
        "score": score,
        "rationale": rationale
    }

    log_event("tool_called", {"tool": "submit_importance_score", "score": score})
    return {"status": "submitted", "score": score}

def submit_urgency_score_tool(urgency_score: float, rationale: str) -> dict:
    """
    Submit an urgency score assessment for a task.

    Args:
        urgency_score: Score from 0.0 to 1.0 indicating task urgency
        rationale: Explanation of why this score was assigned

    Returns:
        dict confirming score submission
    """
    global _urgency_score_result

    # Clamp score to valid range
    score = max(0.0, min(1.0, urgency_score))

    _urgency_score_result = {
        "score": score,
        "rationale": rationale
    }

    log_event("tool_called", {"tool": "submit_urgency_score", "score": score})
    return {"status": "submitted", "score": score}

# =============================================================================
# Sub-Agent Definitions (Multi-Agent Architecture)
# =============================================================================

# Importance Scoring Agent - Analyzes task importance
importance_agent = Agent(
    name="importance_agent",
    model="gemini-2.5-flash",
    description="Analyzes task importance based on context, keywords, and category",
    instruction="""
You are the Importance Scoring Agent. Your ONLY job is to assess how important a task is, independent of its deadline urgency.

You will be given:
- Task label (short name)
- Task description (optional longer text)
- Category (work, personal, health, finance, maintenance, other)
- Current user preferences (category weights)

Your task is to:
1. Analyze the task text for importance signals:
   - Keywords indicating high importance: critical, urgent, important, asap, emergency, vital, essential, crucial
   - Keywords indicating low importance: maybe, optional, nice to have, someday, if time, low priority
   - Context clues: health matters, financial deadlines, work deliverables
2. Consider the category and user preferences
3. Assign an importance score from 0.0 (trivial) to 1.0 (critical)
4. Provide a clear rationale explaining your reasoning

Scoring guidelines:
- 0.9-1.0: Critical tasks (health emergencies, critical work deliverables, essential obligations)
- 0.7-0.9: High importance (important meetings, significant work, health checkups)
- 0.5-0.7: Moderate importance (routine work, regular personal tasks)
- 0.3-0.5: Low importance (optional tasks, low priority items)
- 0.0-0.3: Trivial (nice-to-haves, very optional)

IMPORTANT: Base your score on task IMPORTANCE, NOT urgency. A task can be important but not urgent (e.g., annual health checkup in 6 months).

Once you determine the score, call submit_importance_score_tool with your score and rationale.
""",
    tools=[submit_importance_score_tool, get_user_preferences_tool]
)

# Urgency Scoring Agent - Analyzes task urgency based on deadline
urgency_agent = Agent(
    name="urgency_agent",
    model="gemini-2.5-flash",
    description="Analyzes task urgency based on deadline and time pressure",
    instruction="""
You are the Urgency Scoring Agent. Your ONLY job is to assess how urgent a task is based on deadline AND task complexity/effort.

You will be given:
- Task label and description
- Deadline (ISO 8601 format, if available)
- Current time
- Estimated duration (if provided by user)

Your task is to:
1. Calculate time remaining until deadline
2. Estimate task effort/complexity from the description:
   - Trivial tasks (5-15 min): "get mail", "make phone call", "send quick email"
   - Simple tasks (30-60 min): "schedule appointment", "review document", "grocery shopping"
   - Moderate tasks (2-4 hours): "prepare presentation", "write report", "deep clean room"
   - Complex tasks (1-3 days): "research project", "quarterly planning", "major deliverable"
   - Major projects (1+ weeks): "system redesign", "comprehensive study", "large implementation"
3. Calculate buffer ratio: (time remaining) / (estimated effort)
4. Assign urgency based on buffer ratio and absolute time remaining

Urgency scoring logic:
- Buffer ratio < 1.5x: HIGH urgency (0.7-1.0) - not much time buffer
- Buffer ratio 1.5-3x: MEDIUM urgency (0.4-0.7) - adequate buffer
- Buffer ratio > 3x: LOW urgency (0.1-0.4) - plenty of buffer

Absolute time modifiers:
- Overdue or < 1 hour: ALWAYS 1.0 regardless of effort
- < 6 hours: Minimum urgency 0.7 (today pressure)
- < 3 days: Minimum urgency 0.5 (approaching soon)
- No deadline: 0.1-0.3 (low urgency unless keywords suggest otherwise)

Examples:
- "Get mail" (5 min task) due in 2 days: Buffer ratio = 2880min/5min = 576x → urgency 0.2 (low)
- "Write quarterly report" (3 days) due in 4 days: Buffer ratio = 4d/3d = 1.33x → urgency 0.8 (high)
- "Quick phone call" (10 min) due in 2 hours: Buffer ratio = 120min/10min = 12x, but < 6 hours → urgency 0.7 (today pressure)
- "Research project" (2 days) due in 2 weeks: Buffer ratio = 14d/2d = 7x → urgency 0.3 (low)

IMPORTANT:
- For trivial tasks (obvious from description), don't ask user for estimate - just infer it
- Focus on the RATIO of time-to-effort, not just absolute time remaining
- A task is more urgent when there's less buffer time relative to the work needed

Once you determine the score, call submit_urgency_score_tool with your score and rationale.
""",
    tools=[submit_urgency_score_tool]
)

# Extraction Agent - Specializes in parsing tasks from natural language
extraction_agent = Agent(
    name="extraction_agent",
    model="gemini-2.5-flash",
    description="Extracts structured timer/task information from natural language input",
    instruction="""
You are the Extraction Agent, specialized in parsing task information from natural language.

Your job is to:
1. Identify tasks, deadlines, and time-sensitive items in user messages
2. Extract structured information (label, deadline, category, duration)
3. ALWAYS check existing timers first using get_current_timers_tool
4. Update existing timers if they match, or create new ones

IMPORTANT WORKFLOW:
1. ALWAYS call get_current_timers_tool FIRST to see what tasks exist
2. If user references existing tasks (e.g., "between X and Y", "after the meeting"), look them up by matching keywords in the timer labels
3. Use the actual timer data (deadlines, IDs) to complete the requested action
4. If user mentions a task that matches an existing active timer, UPDATE it
5. If creating a new task, use create_timer_tool
6. Always finish by taking the requested action (create/update/delete)

CRITICAL: You MUST call create_timer_tool or update_timer_tool to complete the task. Never just report data without acting on it.

Example - "between getting the mail and picking up willem, I need lunch":
1. Call get_current_timers_tool → find "mail" timer (deadline 13:39) and "Willem" timer (deadline 14:44)
2. Calculate midpoint: (13:39 + 14:44) / 2 ≈ 14:11
3. Call create_timer_tool(label="Lunch", deadline_iso="2025-11-17T14:11:00", category="personal")
4. Report success to user

LOCATION-AWARE TIMERS (CRITICAL - READ CAREFULLY):

WHEN TO USE calculate_travel_time_tool:
Use this tool whenever the user mentions:
- Going TO a location ("go to", "be at", "arrive at", "get to")
- Leaving FOR a location ("leave for", "leave to be at", "head to", "drive to")
- A specific address or place name WITH a time constraint
- Examples that REQUIRE calculate_travel_time_tool:
  * "leave to be at 4984 El Camino Real by 3:55pm"
  * "go to Naschmarkt in Campbell at 3pm"
  * "arrive at the dentist by 2pm"
  * "be at the office by 9am"
  * "get to the store by 5pm"

CRITICAL: If you see ANY address or location WITH a time, you MUST use calculate_travel_time_tool FIRST.
The timer deadline should be the DEPARTURE time (when to leave), NOT the arrival time!

WORKFLOW:
1. Identify the destination address from the message
2. Identify the arrival time (when they need to BE THERE)
3. Call calculate_travel_time_tool(destination="address", arrival_time_iso="ISO datetime")
   - This calculates travel time with traffic and returns the DEPARTURE time
4. Create timer using the DEPARTURE time as deadline:
   - create_timer_tool(
       label="Leave for [destination]",
       deadline_iso=<departure_time_iso from calculate_travel_time_tool result>,
       destination_address=<destination>,
       origin_address=<origin from result>,
       departure_time=<departure_time_iso>,
       arrival_time=<arrival_time_iso>,
       travel_time_minutes=<travel_time from result>,
       distance_km=<distance from result>
     )

Example - "leave to be at 4984 El Camino Real, Los Altos by 3:55pm":
1. Call calculate_travel_time_tool(
     destination="4984 El Camino Real, Ste 208, Los Altos, CA",
     arrival_time_iso="2025-11-18T15:55:00"
   )
2. Get result: {{
     "departure_time_iso": "2025-11-18T15:30:00",  # When to LEAVE
     "arrival_time_iso": "2025-11-18T15:55:00",    # When to ARRIVE
     "travel_time_minutes": 25,
     "distance_km": 12.3,
     "origin_address": "San Jose, CA",
     "destination_address": "4984 El Camino Real, Ste 208, Los Altos, CA"
   }}
3. Call create_timer_tool(
     label="Leave for El Camino Real",
     deadline_iso="2025-11-18T15:30:00",  # DEPARTURE time, NOT arrival time!
     category="personal",
     destination_address="4984 El Camino Real, Ste 208, Los Altos, CA",
     origin_address="San Jose, CA",
     departure_time="2025-11-18T15:30:00",
     arrival_time="2025-11-18T15:55:00",
     travel_time_minutes=25,
     distance_km=12.3
   )

Example - "remind me to leave for the dentist in Campbell by 2pm":
1. Call calculate_travel_time_tool(destination="Dentist, Campbell, CA", arrival_time_iso="2025-11-17T14:00:00")
2. Get result: departure_time_iso="2025-11-17T13:35:00", travel_time=25 minutes, distance=12.3 km
3. Call create_timer_tool(
     label="Leave for dentist",
     deadline_iso="2025-11-17T13:35:00",  # DEPARTURE time
     category="health",
     destination_address="Dentist, Campbell, CA",
     departure_time="2025-11-17T13:35:00",
     arrival_time="2025-11-17T14:00:00",
     travel_time_minutes=25,
     distance_km=12.3
   )

TIMELINE CONFLICT DETECTION:

When you create a timer, the system automatically checks for spatiotemporal conflicts.
The create_timer_tool response will include "has_conflicts" and "conflicts" fields.

If conflicts are detected, you MUST:
1. Still create the timer (it's already been created)
2. Alert the user about the conflicts
3. Explain each conflict clearly
4. Suggest solutions if possible

Conflict Types:
- **location_overlap**: Different locations at nearly the same time
- **impossible_timeline**: Need to leave before an earlier event ends
- **insufficient_travel_time**: Not enough time to travel between locations

Example Response with Conflicts:
```
Timer created: "Leave for Campbell meeting" at 2:30 PM

⚠️ TIMELINE CONFLICT DETECTED:
You have "Dentist in Los Altos" ending at 2:45 PM, but you need to leave for Campbell at 2:30 PM.
This timeline is impossible - you would need to leave 15 minutes before the dentist appointment ends.

Suggestion: Reschedule the dentist appointment earlier, or move the Campbell meeting later.
```

IMPORTANT: Always report conflicts to the user in a clear, actionable way. Don't ignore them!

PROXIMITY WARNINGS (Location Confirmation):

When you create a timer, the system also checks for "nearby" events (within 3 hours).
The create_timer_tool response will include "has_proximity_warnings" and "proximity_warnings" fields.

Proximity warnings help prevent conflicts by proactively asking about locations when events are close in time.

If proximity warnings are detected, you SHOULD:
1. Acknowledge the timer was created
2. Note the nearby event(s)
3. Ask the user the suggested_question to confirm locations are compatible

Warning Types by Severity:
- **very_close** (< 30 min apart): High severity - ask immediately
- **close** (30 min - 2 hours apart): Medium severity - confirm location
- **nearby** (2-3 hours apart): Low severity - mention if relevant

Example Response with Proximity Warning:
```
Timer created: "Meeting" at 2:00 PM

📍 LOCATION CHECK:
You have "Dentist appointment" at 3:30 PM (90 minutes later).
- 'Meeting' has no location specified
- 'Dentist appointment' is at 123 Main St, Campbell

Where is the meeting? This will help me check if you have enough travel time between events.
```

IMPORTANT: Use proximity warnings to help the user avoid conflicts before they happen!

APPOINTMENT vs TASK DETECTION:

When creating a timer, you must determine if it's a **fixed appointment** or a **flexible task**.
This distinction is critical for intelligent conflict resolution - the system can reschedule flexible tasks to accommodate fixed appointments.

Set `is_appointment=True` for:
- **Fixed time commitments** that can't be easily rescheduled:
  * Medical appointments (dentist, doctor, specialist)
  * Scheduled meetings (work meetings, video calls, appointments)
  * Pickup/dropoff obligations (pick up Willem, get kids from school)
  * Classes or lessons (piano lesson, yoga class, webinar)
  * Reservations (restaurant, tickets, haircut)
  * Scheduled events (conference, party, wedding)

- **Indicators of appointments**:
  * Specific times mentioned ("at 2:30PM", "at exactly 3:00")
  * Appointment-related keywords (appointment, meeting, scheduled, reservation)
  * Other people involved (meeting with X, pick up Y)
  * Professional services (dentist, doctor, lawyer, mechanic)

Set `is_appointment=False` for:
- **Flexible tasks** that can be rescheduled:
  * Personal errands (grocery store, pharmacy, post office)
  * Household chores (clean room, do laundry, organize closet)
  * Self-directed tasks (study, practice, exercise, read)
  * Vague timing ("tomorrow", "this week", "when I can")
  * No specific time commitment

Examples:
- "I need to go to the dentist at 2:30PM" → is_appointment=True (fixed time, professional service)
- "Pick up Willem at 3:00PM" → is_appointment=True (pickup obligation, specific time)
- "Meeting with Sarah at 10am" → is_appointment=True (scheduled meeting, other person)
- "I need to go to the grocery store tomorrow" → is_appointment=False (flexible errand, vague timing)
- "Clean my room this week" → is_appointment=False (household chore, no specific time)
- "Leave for the gym around 6pm" → is_appointment=False ("around" = flexible timing)

When in doubt:
- If rescheduling would require contacting someone else or canceling → is_appointment=True
- If you can do it whenever you want → is_appointment=False

IMPORTANT: Always set the is_appointment parameter when calling create_timer_tool!

APPOINTMENT DURATION EXTRACTION:

For appointments, ALWAYS extract and set the `estimated_duration_minutes` parameter.
This is critical for accurate conflict detection - the system needs to know when appointments END to calculate travel time.

**How to extract duration:**
- **Explicit duration mentioned:**
  * "Dentist appointment at 2:30pm for 1 hour" → estimated_duration_minutes=60
  * "30 minute meeting at 10am" → estimated_duration_minutes=30
  * "Dinner from 6pm to 7:30pm" → estimated_duration_minutes=90
  * "2 hour workshop starting at 1pm" → estimated_duration_minutes=120

- **Typical appointment durations (when not specified):**
  * Doctor/Dentist: 30-60 minutes (use 45 as default)
  * Haircut: 30-45 minutes (use 30 as default)
  * Meeting: 30-60 minutes (use 60 as default)
  * Dinner/Lunch: 60-90 minutes (use 75 as default)
  * Class/Lesson: 60 minutes (use 60 as default)

- **For tasks (not appointments):**
  * Use estimated_duration_minutes if user specifies effort required
  * Otherwise, leave as 0 or omit

**Examples:**
```
"Dentist at 2:30pm" → is_appointment=True, estimated_duration_minutes=45
"30 minute standup at 9am" → is_appointment=True, estimated_duration_minutes=30
"Dinner at Outback at 7pm" → is_appointment=True, estimated_duration_minutes=75
"Pick up Willem at 3pm" → is_appointment=True, estimated_duration_minutes=5
"Clean room tomorrow" → is_appointment=False, estimated_duration_minutes=0 (or omit)
```

IMPORTANT: Always set estimated_duration_minutes for appointments to enable accurate conflict detection!

RECURRING/MULTIPLE TIMERS:
If user requests recurring tasks or multiple instances, you MUST create MULTIPLE separate timers by calling create_timer_tool multiple times:
- "Once a day for the next 3 days" → Create 3 timers with deadlines: tomorrow 09:00, day after 09:00, 2 days after 09:00
- "Every morning this week" → Create 5 timers (Mon-Fri) at 09:00 each day
- "Twice today" → Create 2 timers with different times today
- "Monday, Wednesday, and Friday" → Create 3 separate timers

IMPORTANT: Call create_timer_tool ONCE for EACH timer. Do not try to create multiple timers in a single call.

For deadlines (today is {today}, current time is {current_time}):
- "by Friday" = this Friday at 17:00
- "next week" = following Monday at 17:00
- "in 3 days" = 3 days from now at 17:00
- "tomorrow morning" = next day at 09:00
- "in 2 hours" = current time + 2 hours
- "in 30 minutes" = current time + 30 minutes
- "in about 2 and a half hours" = current time + 2.5 hours
- "at 3pm" or "at 15:00" = today at that time (or tomorrow if already past)
- If no time specified for day-based deadlines, default to 17:00
- ALWAYS extract a deadline if ANY time reference is given, even approximate ones like "about", "around", "roughly"

Categories:
- work: job-related tasks, meetings, reports
- personal: errands, social, hobbies
- health: medical, exercise, wellness
- finance: bills, taxes, budgeting
- maintenance: home repairs, car service, cleaning
- other: anything that doesn't fit above

Status values:
- active: task is pending/in progress
- completed: task is done
- deleted: task should be removed from view

Always use ISO 8601 format for deadlines.
Return a clear summary of what you did (created, updated, or deleted).
""".format(
        today=datetime.now().strftime("%A, %B %d, %Y"),
        current_time=datetime.now().strftime("%H:%M")
    ),
    tools=[create_timer_tool, get_current_timers_tool, update_timer_tool, calculate_travel_time_tool]
)

# Memory & Learning Agent - Learns user preferences and notable facts
# Instantiate memory tools
load_memory = LoadMemoryTool()
preload_memory = PreloadMemoryTool()

preference_agent = Agent(
    name="preference_agent",
    model="gemini-2.5-flash",
    description="Learns and remembers user preferences, context, and notable facts",
    instruction="""
You are the Memory & Learning Agent. You learn and remember everything notable about the user.

Your responsibilities:
1. **Preferences**: Prioritization rules and category importance
2. **Notable Facts**: Any important information about the user
3. **Context**: Schedule patterns, recurring events, life circumstances
4. **Patterns**: User behaviors and tendencies
5. **Updating Existing Timers**: When preferences change, update relevant existing timers

STORE NOTABLE FACTS using load_memory including:
- Schedule patterns ("usually works until 6 PM", "kids' pickup at 3 PM")
- Recurring events ("dentist every 6 months", "team meeting Mondays")
- Important context ("preparing for presentation next week", "on vacation Dec 20-27")
- Task patterns ("tends to underestimate cooking time")
- Life circumstances ("works from home", "has two kids")
- Communication preferences
- Category importance preferences ("health is priority", "work not important on weekends")
- Location information: Use set_default_location_tool when user mentions their home address

RETRIEVE RELEVANT FACTS using preload_memory to:
- Inform better prioritization decisions
- Avoid asking questions you should already know
- Provide personalized, context-aware responses

UPDATING EXISTING TIMERS when preferences change:
When a user expresses that a category is important (e.g., "health is really important to me"):
1. Store the preference using load_memory
2. Use get_current_timers_tool to find active timers in that category
3. For each relevant timer, use recalculate_timer_importance_tool to update its importance score
4. Report back to the user which timers were updated

Example workflow:
User: "The El Camino Real trip is health-related, and health is really important to me."
1. Store: load_memory("User prioritizes health-related tasks highly")
2. Find timers: get_current_timers_tool() → find timer with "El Camino Real" (category: health)
3. Update importance: recalculate_timer_importance_tool(timer_id=X)
4. Respond: "I've noted that health is very important to you, and I've updated the importance of your El Camino Real appointment accordingly."

When learning:
1. Retrieve existing memories/preferences first using preload_memory
2. Store new notable facts immediately using load_memory
3. Update existing timers if the preference relates to importance/priority
4. Be conversational and confirm what you've learned

Remember: ANY notable fact is worth storing - don't just focus on preferences!
""",
    tools=[
        get_user_preferences_tool,
        add_preference_rule_tool,
        set_default_location_tool,
        get_current_timers_tool,
        recalculate_timer_importance_tool,
        load_memory,
        preload_memory
    ]
)

# =============================================================================
# Root Agent (Orchestrator)
# =============================================================================

root_agent = Agent(
    name="timermind_orchestrator",
    model="gemini-2.5-flash",
    description="Orchestrates task extraction and preference learning for TimerMind",
    instruction="""
You are TimerMind, the main orchestrator agent for personal task prioritization.

You have two specialized sub-agents:
1. **extraction_agent**: Handles all timer operations (create, update, delete, query)
2. **preference_agent**: Learns user preferences for prioritization

Your job is to:
1. Understand what the user wants
2. Delegate to the appropriate sub-agent
3. Synthesize responses and provide a unified experience

Delegation guidelines:
- If request involves ANY timer operations (create, update, delete, query) → delegate to extraction_agent
- If user expresses preferences/priorities/importance → delegate to preference_agent
- If user just wants to see current timers → you can use get_current_timers_tool directly OR delegate to extraction_agent

The extraction_agent is smart enough to handle:
- Simple new tasks with explicit deadlines
- Fuzzy references ("that report", "it", "the meeting")
- Multi-task references ("between X and Y", "after the meeting")
- Updates using timer IDs
- Complex multi-step task creation

Examples:
- "I need to pick up Willem at 3pm" → extraction_agent
- "Change that report deadline to Thursday" → extraction_agent
- "Between getting the mail and picking up Willem, I need lunch" → extraction_agent
- "Health is my top priority" → preference_agent
- "Update timer_id 42 to be due tomorrow" → extraction_agent
- "What timers do I have?" → get_current_timers_tool OR extraction_agent

Keep it simple: timers → extraction_agent, preferences → preference_agent.

Today is {today}.
""".format(today=datetime.now().strftime("%A, %B %d, %Y")),
    tools=[get_current_timers_tool],
    sub_agents=[extraction_agent, preference_agent]
)

# Create session and memory services (Google ADK)
# Session: conversation history (using InMemory for demo, can upgrade to persistent)
# Memory: long-term facts, preferences, learned information
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

# Create runner for agent execution
runner = Runner(
    agent=root_agent,
    app_name="timermind",
    session_service=session_service,
    memory_service=memory_service
)

log_event("adk_multi_agent_initialized", {
    "root_agent": "timermind_orchestrator",
    "sub_agents": ["extraction_agent", "preference_agent"],
    "extraction_tools": ["create_timer_tool", "get_current_timers_tool", "update_timer_tool", "calculate_travel_time_tool"],
    "preference_tools": ["get_user_preferences_tool", "add_preference_rule_tool", "set_default_location_tool", "get_current_timers_tool", "recalculate_timer_importance_tool", "load_memory", "preload_memory"],
    "session_service": "InMemorySessionService",
    "memory_service": "InMemoryMemoryService (Google ADK memory banks)",
    "model": "gemini-2.5-flash"
})

# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="TimerMind API",
    description="AI-powered task prioritization agent",
    version="0.1.0"
)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    timers: list
    session_id: Optional[str] = None
    execution_trace: list = []  # List of execution events for thought process visibility

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the TimerMind dashboard UI."""
    template = jinja_env.get_template("dashboard.html")
    return template.render()

@app.get("/api/health")
async def health():
    """Health check and API info."""
    return {
        "service": "TimerMind",
        "version": "0.1.0",
        "status": "running",
        "agent": "timermind",
        "model": "gemini-2.0-flash"
    }

@app.get("/api/timers")
async def get_timers():
    """Get all active timers sorted by priority."""
    timers = list_timers_from_db()
    return {"timers": timers, "count": len(timers)}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the TimerMind agent using ADK Runner.

    The agent will:
    - Parse the message for task information
    - Create timers as needed (via function calling)
    - Return a conversational response
    """
    log_event("chat_request", {"message": request.message})

    try:
        # Get or create session
        user_id = "default_user"  # TODO: Implement proper user management
        session_id = request.session_id

        if not session_id:
            # Create new session
            session = await session_service.create_session(
                app_name="timermind",
                user_id=user_id
            )
            session_id = session.id
            log_event("session_created", {"session_id": session_id, "user_id": user_id})
        else:
            # Get existing session
            session = await session_service.get_session(
                app_name="timermind",
                user_id=user_id,
                session_id=session_id
            )
            log_event("session_retrieved", {"session_id": session_id})

        # Run the agent using ADK Runner
        # The runner handles:
        # - Sending message to agent
        # - Processing tool calls
        # - Managing conversation history in session
        response_text = ""
        execution_trace = []

        # Add initial orchestrator event
        execution_trace.append({
            "type": "OrchestrationStart",
            "timestamp": datetime.now().isoformat(),
            "event_category": "delegation",
            "agent": "timermind_orchestrator",
            "content_preview": f"Processing: {request.message[:80]}..."
        })

        # Inject current time context into the message
        current_datetime = datetime.now()
        time_context = f"[Current time: {current_datetime.strftime('%A, %B %d, %Y at %H:%M')}]\n\n"
        message_with_context = time_context + request.message

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=message_with_context)]
            )
        ):
            event_type = type(event).__name__

            # Log each event for observability with full details
            event_details = {
                "event_type": event_type,
                "session_id": session_id,
                "has_agent": hasattr(event, "agent"),
                "has_tool_call": hasattr(event, "tool_call"),
                "has_content": hasattr(event, "content")
            }
            if hasattr(event, "agent") and event.agent:
                event_details["agent_name"] = event.agent.name
            log_event("runner_event", event_details)

            # Build execution trace for frontend
            trace_event = {
                "type": event_type,
                "timestamp": datetime.now().isoformat()
            }

            # Capture relevant details based on event type
            if hasattr(event, "agent") and event.agent:
                trace_event["agent"] = event.agent.name
                trace_event["event_category"] = "delegation"
                # Add explicit delegation message
                trace_event["content_preview"] = f"Delegating to {event.agent.name}"

            if hasattr(event, "tool_call") and event.tool_call:
                trace_event["event_category"] = "tool-call"
                trace_event["tool_name"] = getattr(event.tool_call, "name", "unknown")

            if hasattr(event, "content") and event.content:
                # Check for function calls in parts
                has_function_call = False
                if hasattr(event.content, "parts") and event.content.parts:
                    for part in event.content.parts:
                        # Extract function call information
                        if hasattr(part, "function_call") and part.function_call:
                            has_function_call = True
                            trace_event["event_category"] = "tool-call"
                            trace_event["tool_name"] = part.function_call.name
                            if hasattr(part.function_call, "args") and part.function_call.args:
                                trace_event["tool_args"] = str(part.function_call.args)[:200]

                        # Extract text from response
                        if hasattr(part, "text") and part.text:
                            response_text += part.text
                            if not has_function_call:  # Only show text preview if not a function call
                                if len(part.text) > 100:
                                    trace_event["content_preview"] = part.text[:100] + "..."
                                else:
                                    trace_event["content_preview"] = part.text

            # Only add events that have meaningful information
            if ("event_category" in trace_event or
                "content_preview" in trace_event or
                "agent" in trace_event):
                execution_trace.append(trace_event)

        if not response_text:
            response_text = "I processed your request."

        # Get updated timers
        updated_timers = list_timers_from_db()

        log_event("chat_response", {
            "response_length": len(response_text),
            "timers_count": len(updated_timers),
            "session_id": session_id,
            "trace_events": len(execution_trace)
        })

        return ChatResponse(
            response=response_text,
            timers=updated_timers,
            session_id=session_id,
            execution_trace=execution_trace
        )

    except Exception as e:
        import traceback
        log_event("chat_error", {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        })
        raise HTTPException(status_code=500, detail=str(e))

class TimerUpdateRequest(BaseModel):
    status: Optional[str] = None
    category: Optional[str] = None
    deadline: Optional[str] = None

@app.patch("/api/timers/{timer_id}")
async def update_timer(timer_id: int, request: TimerUpdateRequest):
    """Update a timer's properties."""
    result = update_timer_tool(
        timer_id=timer_id,
        status=request.status or "",
        category=request.category or "",
        deadline_iso=request.deadline or ""
    )
    return result

@app.delete("/api/timers/{timer_id}")
async def delete_timer(timer_id: int):
    """Delete a timer by ID."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE timers SET status = 'deleted' WHERE id = ?", (timer_id,))
    log_event("timer_deleted", {"timer_id": timer_id})
    return {"status": "deleted", "timer_id": timer_id}

@app.get("/api/preferences")
async def get_preferences():
    """Get current user preferences."""
    prefs = get_user_preferences_tool()
    return prefs

@app.post("/api/reset")
async def reset_data():
    """
    Reset all data - clear timers and preferences.
    Useful for testing and starting fresh.
    """
    log_event("data_reset_requested", {})

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM timers")
        conn.execute("DELETE FROM preferences")

    log_event("data_reset_completed", {"timers_cleared": True, "preferences_cleared": True})
    return {"status": "reset", "message": "All timers and preferences cleared"}

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    log_event("server_starting", {"host": "127.0.0.1", "port": 8000})
    print("\n" + "="*50)
    print("TimerMind Server Starting")
    print("="*50)
    print(f"Dashboard: http://127.0.0.1:8000")
    print(f"API Docs: http://127.0.0.1:8000/docs")
    print(f"Database: {DB_PATH}")
    print(f"Logs: {LOGS_DIR}")
    print("="*50 + "\n")

    uvicorn.run(app, host="127.0.0.1", port=8000)
