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
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

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
DB_PATH = DATA_DIR / "timermind.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

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

def compute_urgency_score(deadline_str: Optional[str]) -> float:
    """
    Compute urgency based on time remaining until deadline.

    Design Decision: Sigmoid curve to avoid sudden jumps in urgency.
    Score increases exponentially as deadline approaches.

    Returns:
        float: 0.1 (far future) to 1.0 (overdue/imminent)
    """
    if not deadline_str:
        return 0.3  # No deadline = low urgency

    try:
        deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.now()

        hours_remaining = (deadline - now).total_seconds() / 3600

        if hours_remaining <= 0:
            return 1.0  # Overdue
        elif hours_remaining > 168:  # More than a week
            return 0.1
        else:
            # Sigmoid-like curve: urgency increases as deadline approaches
            import math
            urgency = 1 / (1 + math.exp(hours_remaining / 24 - 2))
            return max(0.1, min(1.0, urgency))
    except Exception as e:
        log_event("urgency_calculation_error", {"error": str(e), "deadline": deadline_str})
        return 0.5

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

    urgency = compute_urgency_score(deadline)
    importance = 0.5  # Default; will be agent-scored later
    priority = (urgency + importance) / 2  # Simple average for now

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("""
            INSERT INTO timers (
                label, description, deadline, estimated_duration_minutes,
                category, tags, urgency_score, importance_score, priority_score,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            label, description, deadline, estimated_duration_minutes,
            category, tags_str, urgency, importance, priority,
            now, now
        ))
        timer_id = cursor.lastrowid

    result = {
        "timer_id": timer_id,
        "label": label,
        "deadline": deadline,
        "urgency_score": urgency,
        "importance_score": importance,
        "priority_score": priority,
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

# Define tools as Python functions with proper signatures for ADK
def create_timer_tool(
    label: str,
    description: str = "",
    deadline_iso: str = "",
    estimated_duration_minutes: int = 0,
    category: str = "other",
) -> dict:
    """
    Create a new timer/task in the system.

    Use this tool when the user describes something they need to do,
    a deadline they need to meet, or a task they want to track.

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
        "args": {
            "label": label,
            "description": description,
            "deadline_iso": deadline_iso,
            "category": category
        }
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
    Retrieve all current active timers.

    Use this tool to see what tasks the user is currently tracking.

    Returns:
        dict containing list of timer objects with their details and scores
    """
    log_event("tool_called", {"tool": "get_current_timers"})
    timers = list_timers_from_db()
    log_event("tool_result", {"tool": "get_current_timers", "count": len(timers)})
    return {"timers": timers, "count": len(timers)}

# Create the root agent using ADK
root_agent = Agent(
    name="timermind",
    model="gemini-2.0-flash-exp",
    description="Personal task prioritization assistant that extracts timers from natural language",
    instruction="""
You are TimerMind, a personal task prioritization assistant.

Your primary job is to help users track deadlines and tasks by:
1. Extracting task information from natural language descriptions
2. Creating timers with appropriate deadlines and categories
3. Explaining what you've created and why

When a user describes something they need to do:
- Extract the task label (clear, concise name)
- Infer or extract the deadline if mentioned
- Determine the category (work, personal, health, finance, maintenance, other)
- Use the create_timer_tool to save it

For deadlines (today is {today}):
- "by Friday" = end of this Friday (17:00 local time), use ISO format like "2025-11-21T17:00:00"
- "next week" = following Monday at 17:00
- "in 3 days" = 3 days from now at 17:00
- If no time specified, default to end of day (17:00)

Always confirm what you've created and show the urgency score.
If the user mentions multiple tasks, create multiple timers.

Be conversational but efficient. Focus on accurately capturing their tasks.
""".format(today=datetime.now().strftime("%A, %B %d, %Y")),
    tools=[create_timer_tool, get_current_timers_tool]
)

# Create session service (using InMemory for now, will upgrade to VertexAI later)
session_service = InMemorySessionService()

# Create runner for agent execution
runner = Runner(
    agent=root_agent,
    app_name="timermind",
    session_service=session_service
)

log_event("adk_agent_initialized", {
    "name": "timermind",
    "model": "gemini-2.0-flash-exp",
    "tools": ["create_timer_tool", "get_current_timers_tool"],
    "session_service": "InMemorySessionService"
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

@app.get("/")
async def root():
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

        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=request.message)]
            )
        ):
            # Log each event for observability
            log_event("runner_event", {
                "event_type": type(event).__name__,
                "session_id": session_id
            })

            # Extract text from response events
            if hasattr(event, "content") and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text

        if not response_text:
            response_text = "I processed your request."

        # Get updated timers
        updated_timers = list_timers_from_db()

        log_event("chat_response", {
            "response_length": len(response_text),
            "timers_count": len(updated_timers),
            "session_id": session_id
        })

        return ChatResponse(
            response=response_text,
            timers=updated_timers,
            session_id=session_id
        )

    except Exception as e:
        import traceback
        log_event("chat_error", {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/timers/{timer_id}")
async def delete_timer(timer_id: int):
    """Delete a timer by ID."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE timers SET status = 'deleted' WHERE id = ?", (timer_id,))
    log_event("timer_deleted", {"timer_id": timer_id})
    return {"status": "deleted", "timer_id": timer_id}

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    log_event("server_starting", {"host": "127.0.0.1", "port": 8000})
    print("\n" + "="*50)
    print("TimerMind Server Starting")
    print("="*50)
    print(f"API: http://127.0.0.1:8000")
    print(f"Docs: http://127.0.0.1:8000/docs")
    print(f"Database: {DB_PATH}")
    print(f"Logs: {LOGS_DIR}")
    print("="*50 + "\n")

    uvicorn.run(app, host="127.0.0.1", port=8000)
