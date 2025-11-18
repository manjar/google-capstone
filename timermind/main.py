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

Please assess the importance score and provide your rationale. Remember to check user preferences for category weights."""

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
    tags: list = None
) -> dict:
    """
    Create a new timer in the database.

    This function is called by the agent's create_timer tool.
    """
    tags_str = json.dumps(tags or [])
    now = datetime.utcnow().isoformat()

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
                rationale, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            label, description, deadline, estimated_duration_minutes,
            category, tags_str, urgency, importance, priority,
            rationale, now, now
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
) -> dict:
    """
    Create a new timer/task in the system.

    Args:
        label: Short, clear name for the task (e.g., "Submit report")
        description: Optional longer description of what needs to be done
        deadline_iso: Optional deadline in ISO 8601 format (e.g., "2025-11-20T17:00:00")
        estimated_duration_minutes: Optional estimate of how long the task will take
        category: Task category - one of: work, personal, health, finance, maintenance, other

    Returns:
        dict with timer_id, computed scores, and creation status
    """
    log_event("tool_called", {
        "tool": "create_timer",
        "args": {"label": label, "deadline_iso": deadline_iso, "category": category}
    })

    result = create_timer_in_db(
        label=label,
        description=description if description else None,
        deadline=deadline_iso if deadline_iso else None,
        estimated_duration_minutes=estimated_duration_minutes if estimated_duration_minutes > 0 else None,
        category=category,
        tags=[]
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

        if status:
            updates.append("status = ?")
            params.append(status)
        if category:
            updates.append("category = ?")
            params.append(category)
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
                # Update priority score (simple average for now)
                updates.append("priority_score = (? + importance_score) / 2")
                params.append(new_urgency)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())
            params.append(timer_id)
            conn.execute(f"UPDATE timers SET {', '.join(updates)} WHERE id = ?", params)

    result = {"timer_id": timer_id, "updated": True}
    if new_urgency is not None:
        result["new_urgency_score"] = new_urgency
        result["deadline"] = deadline_iso

    return result

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
            "category_weights": {
                "work": 1.0,
                "personal": 0.8,
                "health": 1.2,
                "finance": 1.1,
                "maintenance": 0.7,
                "other": 0.5
            },
            "rules": []
        }

    return {"preferences": prefs}

def update_category_weight_tool(category: str, weight: float) -> dict:
    """
    Update the priority weight for a specific category.

    Higher weights mean tasks in that category are considered more important.

    Args:
        category: Category name (work, personal, health, finance, maintenance, other)
        weight: New weight value (0.1 to 2.0, where 1.0 is neutral)

    Returns:
        dict with update confirmation
    """
    log_event("tool_called", {"tool": "update_category_weight", "category": category, "weight": weight})

    # Get current weights
    prefs = get_user_preferences_tool()["preferences"]
    weights = prefs.get("category_weights", {})
    weights[category] = max(0.1, min(2.0, weight))  # Clamp to valid range

    # Save to database
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO preferences (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
        """, ("category_weights", json.dumps(weights), now, json.dumps(weights), now))

    return {"category": category, "new_weight": weights[category], "updated": True}

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
    model="gemini-2.0-flash-exp",
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
    model="gemini-2.0-flash-exp",
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

# Context Resolution Agent - Maps natural language to existing timer data
context_agent = Agent(
    name="context_agent",
    model="gemini-2.0-flash-exp",
    description="Resolves natural language references to existing timers and their data",
    instruction="""
You are the Context Resolution Agent. Your ONLY job is to map natural language task references to existing timer data.

When given a query about existing tasks:
1. ALWAYS call get_current_timers_tool first
2. Find timers that match the natural language references
3. Return the relevant timer details (especially deadlines)

Examples:
- "getting the mail" → Look for timer with "mail" in label, return its deadline
- "picking up Willem" → Look for timer with "Willem" in label, return its deadline
- "the report" → Look for timer with "report" in label, return its deadline
- "between X and Y" → Find both timers, return both deadlines so caller can calculate middle time

You must be fuzzy-matching friendly:
- "getting the mail" matches "Get mail from mailbox"
- "picking up willem" matches "Pick up Willem"
- "my appointment" matches "Doctor appointment" or "Dentist appointment"

Return structured data about the matched timers including their IDs, labels, and deadlines.
If no match is found, clearly state that.
""",
    tools=[get_current_timers_tool]
)

# Planning Agent - Creates and tracks execution plans
planning_agent = Agent(
    name="planning_agent",
    model="gemini-2.0-flash-exp",
    description="Creates step-by-step execution plans and ensures all steps are completed",
    instruction="""
You are the Planning Agent. Your job is to EXECUTE multi-step tasks to completion.

IMPORTANT: Do NOT output a plan first. Instead:
1. Internally plan the steps needed
2. IMMEDIATELY start executing by calling tools
3. Only report results AFTER all steps are done

For "between getting the mail and picking up willem, I need lunch":
1. Call get_current_timers_tool to find the mail and willem timers
2. Extract their deadlines from the results
3. Calculate midpoint: if mail=13:39 and willem=14:44, midpoint is ~14:11
4. Call create_timer_tool with label="Lunch", deadline_iso="2025-11-17T14:11:00", category="personal"
5. Report: "Created Lunch timer at 14:11 (between mail at 13:39 and Willem at 14:44)"

YOU MUST:
- Call tools immediately, don't just describe what you would do
- Use the ACTUAL data from tool results
- Complete ALL steps before responding
- End with the final action (create/update/delete) being executed
- Report what you accomplished, not what you plan to do

If you need to resolve task references, delegate to context_agent first, then use those results.
""",
    tools=[create_timer_tool, get_current_timers_tool, update_timer_tool],
    sub_agents=[context_agent]
)

# Extraction Agent - Specializes in parsing tasks from natural language
extraction_agent = Agent(
    name="extraction_agent",
    model="gemini-2.0-flash-exp",
    description="Extracts structured timer/task information from natural language input",
    instruction="""
You are the Extraction Agent, specialized in parsing task information from natural language.

Your job is to:
1. Identify tasks, deadlines, and time-sensitive items in user messages
2. Extract structured information (label, deadline, category, duration)
3. ALWAYS check existing timers first using get_current_timers_tool
4. Update existing timers if they match, or create new ones

IMPORTANT WORKFLOW:
1. If user references existing tasks by name (e.g., "between getting the mail and picking up willem"), DELEGATE to context_agent first to resolve those references to actual timer data
2. Once you have the timer data (deadlines, IDs), YOU MUST USE THAT DATA to complete the task - DO NOT just report what you found
3. ALWAYS finish by creating/updating/deleting the timer as requested
4. Call get_current_timers_tool to see what tasks exist if needed
5. If user mentions a task that matches an existing active timer, UPDATE it
6. If user references a recently completed task, use that info to CREATE a new one

CRITICAL: After getting context data, you MUST take action. Example:
- User says: "between getting the mail and picking up willem, I need lunch"
- Step 1: DELEGATE to context_agent → returns mail deadline (13:39) and willem deadline (14:44)
- Step 2: Calculate midpoint: (13:39 + 14:44) / 2 ≈ 14:11
- Step 3: CALL create_timer_tool with label="Lunch", deadline_iso="2025-11-17T14:11:00", category="personal"
- Step 4: Report success to user

You MUST call create_timer_tool or update_timer_tool to complete the task. Never just report data without acting on it.

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
    tools=[create_timer_tool, get_current_timers_tool, update_timer_tool]
)

# Preference Agent - Specializes in learning user preferences
preference_agent = Agent(
    name="preference_agent",
    model="gemini-2.0-flash-exp",
    description="Learns and manages user preferences for task prioritization",
    instruction="""
You are the Preference Agent, specialized in learning user preferences.

Your job is to:
1. Identify preference signals in user messages
2. Update category weights based on user statements
3. Create rules for special prioritization logic

Listen for statements like:
- "Work is more important than personal stuff" → increase work weight
- "Health should always come first" → set health weight to highest
- "Don't bother me with work on weekends" → add suppression rule
- "Bills are high priority" → increase finance weight

Weight scale (0.1 to 2.0):
- 0.1-0.5: Low priority
- 0.6-0.9: Below average
- 1.0: Neutral/average
- 1.1-1.5: Above average
- 1.6-2.0: High priority

When updating preferences:
1. Get current preferences first
2. Make incremental adjustments (don't overhaul everything)
3. Confirm changes with the user

Be conversational and confirm what you've learned.
""",
    tools=[get_user_preferences_tool, update_category_weight_tool, add_preference_rule_tool]
)

# =============================================================================
# Root Agent (Orchestrator)
# =============================================================================

root_agent = Agent(
    name="timermind_orchestrator",
    model="gemini-2.0-flash-exp",
    description="Orchestrates task extraction and preference learning for TimerMind",
    instruction="""
You are TimerMind, the main orchestrator agent for personal task prioritization.

You have three specialized sub-agents:
1. **planning_agent**: For complex, multi-step requests that need planning and execution tracking
2. **extraction_agent**: For simple, direct task operations (create, update, delete)
3. **preference_agent**: Learns user preferences for prioritization

Your job is to:
1. Understand what the user wants
2. Delegate to the appropriate sub-agent
3. Synthesize responses and provide a unified experience

Delegation guidelines:
- If request involves references to OTHER tasks (e.g., "between X and Y", "after the meeting") → delegate to planning_agent
- If request needs multiple steps or calculations → delegate to planning_agent
- If user describes a simple new task with explicit deadline → delegate to extraction_agent
- If user wants to UPDATE/COMPLETE/DELETE a task by name → delegate to extraction_agent
- If user expresses preferences/priorities/importance → delegate to preference_agent
- If user asks about current timers → use get_current_timers_tool directly

Examples:
- "I need to pick up Willem at 3pm" → extraction_agent (simple, explicit)
- "Between getting the mail and picking up Willem, I need lunch" → planning_agent (references other tasks, needs calculation)
- "Health is my top priority" → preference_agent
- "Mark the report as done" → extraction_agent (simple update)

IMPORTANT: Use planning_agent for anything that requires looking up existing timer data and then acting on it.

Today is {today}.
""".format(today=datetime.now().strftime("%A, %B %d, %Y")),
    tools=[get_current_timers_tool],
    sub_agents=[planning_agent, extraction_agent, preference_agent]
)

# Create session service (using InMemory for now, will upgrade to VertexAI later)
session_service = InMemorySessionService()

# Create runner for agent execution
runner = Runner(
    agent=root_agent,
    app_name="timermind",
    session_service=session_service
)

log_event("adk_multi_agent_initialized", {
    "root_agent": "timermind_orchestrator",
    "sub_agents": ["planning_agent", "extraction_agent", "preference_agent"],
    "planning_sub_agents": ["context_agent"],
    "planning_tools": ["create_timer_tool", "get_current_timers_tool", "update_timer_tool"],
    "extraction_tools": ["create_timer_tool", "get_current_timers_tool", "update_timer_tool"],
    "context_tools": ["get_current_timers_tool"],
    "preference_tools": ["get_user_preferences_tool", "update_category_weight_tool", "add_preference_rule_tool"],
    "session_service": "InMemorySessionService",
    "model": "gemini-2.0-flash-exp"
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
