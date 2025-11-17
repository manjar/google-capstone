# TimerMind Capstone Project Specification

## Competition Context

**Track:** Concierge Agents
**Deadline:** December 1, 2025, 11:59 AM PT
**Team Size:** 1 (individual submission)

### Track Selection Justification

TimerMind fits the **Concierge Agents** track because it:

- Serves individuals in their personal lives (not enterprise/business workflows)
- Automates task prioritization and deadline management (similar to meal planning, travel planning)
- Learns personal preferences through conversation (personalized assistant)
- Reduces cognitive load for everyday life management
- Not healthcare/education/sustainability focused (rules out "Agents for Good")
- Not business workflow automation (rules out "Enterprise Agents")
- Fits a clear category, not experimental (rules out "Freestyle")

### Problem Statement

Managing multiple deadlines and time-sensitive tasks is cognitively overwhelming. People struggle to prioritize between urgent but unimportant tasks and important but non-urgent ones. Traditional to-do lists don't account for time pressure, and calendar apps don't understand context or personal priorities. Searching across multiple sources, multiple times per day, is a challenge unto itself.

### Solution Pitch

TimerMind is an AI-powered agent system that transforms unstructured task descriptions into prioritized, deadline-aware timers. It uses multiple specialized agents to extract task information, learn user preferences through conversation, and continuously re-prioritize based on both contextually-inferred and user-stated or user-implied urgency and importance. The system includes a "break mode" that temporarily suppresses urgency signals, allowing users to disconnect without anxiety.

### Value Proposition

- Reduces cognitive load of deadline tracking by 70%+
- Learns personal priorities through natural conversation
- Provides transparent explanations for all prioritization decisions
- Respects user's need for breaks while maintaining awareness

---

## 1. Product Overview

**Working name:** TimerMind
**Goal:** Turn all "due-ish" things in a user's life into prioritized timers, ranked by urgency (time pressure) and importance (meaning), with a special break mode ("down timer") that suppresses urgency temporarily.

**Core idea:**

- Ingest items written by the user (and later from calendar/email/reminders).
- Use Gemini-powered agents to extract structure, infer deadlines, durations, and categories.
- Maintain preferences learned conversationally via agent memory.
- Display everything on a simple timer board UI.

---

## 2. Competition Requirements

### Required Features (minimum 3 of these)

**Implementing:**

1. **Multi-agent system** - Sequential agents for extraction, scoring, and chat processing
2. **Custom Tools** - Timer CRUD operations, preference management, scoring calculations
3. **Sessions & Memory** - VertexAiSessionService for persistent conversation context + VertexAiMemoryBankService for long-term preference learning (Google Cloud integration)
4. **Observability** - Structured logging for agent decisions and scoring rationale

**Bonus Points (Planned):**

- Gemini as LLM backbone (+5 points) - **INCLUDED in core implementation**
- Vertex AI integration (+additional Google tech credibility)
- Agent deployment documentation (+5 points) - **PLANNED** (document Cloud Run steps)
- YouTube video submission (+10 points) - **PLANNED** (record 3-min demo video)

---

## 3. User Stories

### Primary

1. Input tasks/events in plain English → converted to timers.
2. See a dashboard of “what deserves attention right now.”
3. Start a “down timer” (break mode) that hides urgency.
4. Teach the system preferences via chat.
5. Ask “why is this prioritized?” and get explanations.

### Secondary

6. Pull in simple external sources (calendar mock or real).  
7. Detect recurring patterns (haircut, oil change, etc.) and suggest timers.

---

## 4. Architecture

### Technology Stack (Solidified)

- **Frontend:** Lightweight HTML (Jinja2 templates), minimal JS
- **Backend:** Python 3.11+ with FastAPI + Uvicorn
- **Agent Framework:** Google ADK (Agent Development Kit) - Python
- **LLM:** Gemini 2.0 Flash (via google-generativeai)
- **Storage:** SQLite (familiar, simple, sufficient for MVP)
- **Environment:** python-dotenv for configuration
- **Deployment:** Local development; Cloud Run for optional deployment

### Agent Architecture (ADK-based)

```
┌─────────────────────────────────────────────────────┐
│                   Root Agent                        │
│              (Orchestrator Agent)                   │
└─────────────┬───────────────────────┬───────────────┘
              │                       │
              ▼                       ▼
┌─────────────────────┐   ┌─────────────────────┐
│   Extraction Agent  │   │   Preference Agent  │
│   (Sub-agent)       │   │   (Sub-agent)       │
└─────────────────────┘   └─────────────────────┘
              │                       │
              ▼                       ▼
┌─────────────────────┐   ┌─────────────────────┐
│   Timer Tools       │   │   Preference Tools  │
│   - create_timer    │   │   - update_weights  │
│   - update_timer    │   │   - add_rule        │
│   - delete_timer    │   │   - get_preferences │
│   - score_timer     │   │                     │
└─────────────────────┘   └─────────────────────┘
```

**Agent Flow (Sequential):**

1. User input → Root Agent
2. Root Agent delegates to Extraction Agent (if creating timers)
3. Root Agent delegates to Preference Agent (if updating preferences)
4. Both agents use custom tools for database operations
5. Results aggregated and returned to user

### Subsystems

1. **Timer Engine** – CRUD operations, urgency/importance scoring
2. **Preference Manager** – rules, weights, and user-learned patterns
3. **Agent Layer (ADK)** – Gemini-powered agents with custom tools
4. **Session Manager** – VertexAiSessionService for persistent conversation context (Google Cloud)
5. **Memory Manager** – VertexAiMemoryBankService for long-term preference learning across sessions
6. **Web UI** – FastAPI routes serving Jinja2 templates + JSON API
7. **Observability** – Structured logging with Python logging module

---

## 5. Data Model

### Timer

```python
id: int
label: str
description: str | None
deadline: datetime | None
window_start: datetime | None
window_end: datetime | None
estimated_duration_minutes: int | None
category: str | None
tags: list[str]
urgency_score: float
importance_score: float
priority_score: float
source: str
status: str
created_at: datetime
updated_at: datetime
due_text: str | None
```

### UserPreferences

```python
priority_weights: dict
time_prefs: dict
source_prefs: dict
rules: list[dict]
```

Example rule:

```json
{
  "id": "hide_work_weekends",
  "match": {
    "tags_any": ["work"],
    "days": ["SAT", "SUN"]
  },
  "visibility": "hidden_unless_due_24h"
}
```

---

## 6. API Design

### Timer Endpoints

**GET `/api/timers`**  
Return all timers.

**POST `/api/timers`**
Body: `{ "text": "<freeform user input>" }`
Action: Route through Extraction Agent (Gemini-powered) to extract structured timers and save them.

**PATCH `/api/timers/{id}`**  
Modify status, snooze, override, etc.

**POST `/api/timers/refresh`**  
Recompute priority scores.

### Break Mode

**POST `/api/break/start`**  
Body: `{ "duration_minutes": N }`

**POST `/api/break/end`**

### Chat

**POST `/api/chat`**

- Routes user message through Root Agent (ADK)

- Agent uses session context to maintain conversation history

- Returns:
  
  ```json
  {
  "assistant_text": "...",
  "timers": [...],
  "session_id": "..."
  }
  ```

---

## 7. Agent Definitions (ADK)

### Root Agent (Orchestrator)

```python
from google.adk.agents import Agent, SequentialAgent
from google.adk.sessions import DatabaseSessionService

root_agent = Agent(
    name="timermind_orchestrator",
    model="gemini-2.0-flash",
    description="Orchestrates timer management and preference learning",
    instruction="""
    You are TimerMind, a personal task prioritization assistant.
    - When user provides task descriptions, delegate to extraction_agent
    - When user discusses preferences, delegate to preference_agent
    - Always explain your reasoning for prioritization decisions
    - Maintain context across the conversation using session memory
    """,
    sub_agents=[extraction_agent, preference_agent],
    tools=[get_all_timers, get_dashboard_state]
)
```

### Extraction Agent (Sub-agent)

```python
extraction_agent = Agent(
    name="extraction_agent",
    model="gemini-2.0-flash",
    description="Extracts structured timer data from natural language",
    instruction="""
    Parse user input to extract:
    - Task label and description
    - Deadline (explicit or inferred)
    - Time windows (when task can be done)
    - Duration estimate
    - Category and tags
    Use the create_timer tool to persist each extracted timer.
    """,
    tools=[create_timer, update_timer, score_importance]
)
```

### Preference Agent (Sub-agent)

```python
preference_agent = Agent(
    name="preference_agent",
    model="gemini-2.0-flash",
    description="Learns and updates user preferences from conversation",
    instruction="""
    Identify preference signals in user messages:
    - Priority weightings (e.g., "work is more important than personal")
    - Time preferences (e.g., "don't show work on weekends")
    - Category rules (e.g., "health always comes first")
    Update preferences using the provided tools.
    """,
    tools=[update_weights, add_rule, remove_rule, get_preferences]
)
```

### Custom Tools (ADK Function Tools)

```python
from google.adk.tools import FunctionTool

@FunctionTool
def create_timer(
    label: str,
    description: str = None,
    deadline_iso: str = None,
    estimated_duration_minutes: int = None,
    category: str = "other",
    tags: list[str] = []
) -> dict:
    """Create a new timer in the database and compute its priority score."""
    # Implementation: Insert into SQLite, calculate urgency/importance
    pass

@FunctionTool
def score_importance(timer_id: int) -> dict:
    """
    Score a timer's importance based on user preferences.
    Returns importance score (1-5) and rationale.
    """
    pass

@FunctionTool
def update_weights(category: str, weight: float) -> dict:
    """Update priority weight for a category."""
    pass

@FunctionTool
def add_rule(rule_definition: dict) -> dict:
    """Add a new preference rule."""
    pass
```

### Session & Memory Management

```python
from google.adk.sessions import VertexAiSessionService
from google.adk.memory import VertexAiMemoryBankService

# Vertex AI Session Service (persistent, cloud-managed)
# Requires: Google Cloud project with Vertex AI enabled
session_service = VertexAiSessionService(
    project_id="your-gcp-project-id",
    location="us-central1"
)

# Create/retrieve session for user
session = session_service.create_session(
    app_name="timermind",
    user_id=user_id
)

# Core session operations
session = session_service.get_session(session_id=session.id)
session_service.append_event(session_id=session.id, event=agent_event)
sessions = session_service.list_sessions(user_id=user_id)

# Vertex AI Memory Bank Service (persistent, semantic search)
memory_service = VertexAiMemoryBankService(
    project_id="your-gcp-project-id",
    location="us-central1"
)

# Store session into long-term memory after conversation
# Extracts relevant information automatically
memory_service.add_session_to_memory(session)

# Search long-term memory for relevant context
# Returns semantically relevant snippets from past sessions
results = memory_service.search_memory(
    query="user priority preferences",
    user_id=user_id
)

# Agent can use these results to personalize responses
# e.g., "Based on past conversations, you prefer work > personal priority"
```

**Memory Architecture:**

- **Session** - Single conversation thread, events, temporary state (VertexAiSessionService)
- **Memory** - Long-term knowledge store spanning multiple sessions (VertexAiMemoryBankService)
- **Timer Data** - Structured task storage (SQLite tables - local)

**Vertex AI Benefits:**

- Persistent across restarts (cloud-managed)
- Semantic search (not just keyword matching)
- LLM-powered memory extraction from sessions
- Free tier available for development
- Express mode for quick setup

---

## 8. UI Spec

### Main Dashboard

- List of timers sorted by priority score
- Show: label, time remaining (countdown), category badge, priority color indicator
- Actions: complete, snooze, edit, delete
- Break mode: prominent "On break until HH:MM" overlay
- Refresh button to re-score all timers

### Chat Panel

- Persistent textbox for natural language input
- Conversation history display
- Real-time timer list updates after agent responses
- "Why?" button next to each timer for explanation

---

## 9. Observability & Logging

### Structured Logging

```python
import logging
import json

logger = logging.getLogger("timermind")

def log_agent_decision(agent_name: str, input_data: dict, output_data: dict, rationale: str):
    logger.info(json.dumps({
        "event": "agent_decision",
        "agent": agent_name,
        "input": input_data,
        "output": output_data,
        "rationale": rationale,
        "timestamp": datetime.utcnow().isoformat()
    }))

def log_scoring_event(timer_id: int, urgency: float, importance: float, final_score: float):
    logger.info(json.dumps({
        "event": "timer_scored",
        "timer_id": timer_id,
        "urgency": urgency,
        "importance": importance,
        "final_score": final_score,
        "timestamp": datetime.utcnow().isoformat()
    }))
```

### Metrics to Track

- Agent invocation count and latency
- Tool usage frequency
- Scoring distribution
- User preference changes over time
- Session duration and message count

---

## 10. MVP Scope (Competition Submission)

### Must Have (MVP)

- Manual text input → timer extraction via Extraction Agent
- Timer dashboard with priority sorting
- Urgency scoring (time-based) + Importance scoring (agent-based)
- Break mode (suppress urgency display)
- Chat interface with Preference Agent for learning rules
- Session persistence (VertexAiSessionService - cloud-managed)
- Long-term memory (VertexAiMemoryBankService for learned preferences)
- Structured logging for observability
- README with architecture diagram and setup instructions
- Well-commented code with design decision explanations
- Deployment documentation (Cloud Run instructions for +5 bonus)
- YouTube demo video under 3 minutes (for +10 bonus)

### Nice to Have (Time Permitting)

- Pattern detection for recurring tasks
- External calendar integration mock
- Advanced rule system UI
- Actually deploy to Cloud Run (beyond just documentation)

### Out of Scope (Post-Competition)

- Multi-user authentication
- Real calendar/email integrations
- Mobile app
- Production-grade deployment

---

## 11. Implementation Plan

### Phase 1: Foundation (Days 1-2)

- FastAPI skeleton with SQLite setup
- Timer data model and basic CRUD endpoints
- Static dashboard UI (no agents yet)
- Basic urgency scoring (purely time-based)

### Phase 2: Agent Integration (Days 3-5)

- Set up Google ADK with Gemini
- Configure Vertex AI project (sessions + memory bank)
- Implement Extraction Agent with custom tools
- Timer extraction from natural language
- Session management with VertexAiSessionService

### Phase 3: Preference Learning (Days 6-8)

- Implement Preference Agent
- Importance scoring via agent
- Chat endpoint for preference conversations
- Preference persistence in SQLite

### Phase 4: Polish & Documentation (Days 9-12)

- Break mode implementation
- Observability/logging setup
- README.md with architecture, setup, diagrams
- Code comments and docstrings
- Test key flows end-to-end

### Phase 5: Submission Prep (Days 13-14)

- Record YouTube demo video under 3 minutes (+10 bonus points)
- Write Cloud Run deployment documentation (+5 bonus points)
- Prepare competition writeup (<1500 words)
- Create thumbnail/card image
- Final testing and bug fixes
- Submit to Kaggle competition

---

## 12. Project Structure

```
timermind/
├── README.md                 # Competition submission documentation
├── requirements.txt          # Dependencies
├── .gitignore                # Excludes .env, *.db, __pycache__, venv/, logs/
├── .env.example              # Environment variable template (NO REAL KEYS)
├── main.py                   # FastAPI app entry point
├── agents/
│   ├── __init__.py
│   ├── root_agent.py         # Orchestrator agent
│   ├── extraction_agent.py   # Timer extraction sub-agent
│   └── preference_agent.py   # Preference learning sub-agent
├── tools/
│   ├── __init__.py
│   ├── timer_tools.py        # Timer CRUD function tools
│   └── preference_tools.py   # Preference management tools
├── models/
│   ├── __init__.py
│   ├── timer.py              # Timer data model
│   └── preferences.py        # User preferences model
├── services/
│   ├── __init__.py
│   ├── scoring.py            # Urgency/importance calculations
│   ├── vertex_session.py     # VertexAiSessionService wrapper
│   ├── vertex_memory.py      # VertexAiMemoryBankService wrapper
│   └── database.py           # SQLite operations (local timer data)
├── templates/
│   ├── dashboard.html        # Main UI
│   └── base.html             # Base template
├── static/
│   ├── style.css
│   └── app.js                # Minimal frontend JS
├── data/
│   └── timermind.db          # Timer and preference rules (local SQLite)
└── logs/
    └── timermind.log         # Structured log output
```

---

## 13. Dependencies (requirements.txt)

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-dotenv==1.0.1
google-generativeai==0.8.3
google-adk
google-cloud-aiplatform
jinja2==3.1.2
httpx==0.27.2
```

**Setup Notes:**

- `google-adk` is the official ADK package: `pip install google-adk`
- `google-cloud-aiplatform` provides Vertex AI integration for sessions and memory
- Requires Google Cloud project with Vertex AI API enabled
- Set `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` in .env
- Authentication via `gcloud auth application-default login` or service account

**.env.example:**

```
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

---

## 14. Submission Deliverables (Kaggle Competition)

### Required Artifacts

**1. Code Repository (GitHub)**

- Public repository with all source code
- README.md with problem, solution, architecture, setup instructions
- Well-commented code explaining design decisions and behaviors
- .gitignore properly configured (NO API keys or passwords)

**2. Competition Writeup (<1500 words)**

- **Problem Statement**: Why deadline/priority management is hard
- **Solution Overview**: How TimerMind uses agents to solve this
- **Architecture**: Multi-agent system with tools and memory
- **Value Delivered**: Concrete benefits (cognitive load reduction, learned preferences)
- **Project Journey**: Challenges faced, iterations, lessons learned

**3. Thumbnail/Card Image**

- Visual representation of TimerMind
- Could be: architecture diagram, UI screenshot, or branded logo
- Should quickly convey "AI-powered timer prioritization"

**4. Title & Subtitle**

- **Title**: "TimerMind: AI-Powered Task Prioritization Agent"
- **Subtitle**: "A multi-agent system that learns your priorities and manages deadline anxiety"

### Bonus Deliverables

**5. YouTube Video (Under 3 minutes)** - +10 points

- Problem statement and why agents help
- Architecture overview with diagram
- Live demo of the system
- Build process and tools used
- Clear, concise messaging

**6. Deployment Documentation** - +5 points

- Cloud Run deployment instructions
- Or evidence of deployment attempt in writeup/code

---

## 15. Code Quality Standards

### Commenting Requirements (Competition Mandate)

The competition explicitly requires: "Your code should contain comments pertinent to implementation, design and behaviors."

**Required Comment Types:**

```python
# Module-level docstring explaining purpose
"""
timer_tools.py - Custom ADK tools for timer CRUD operations.

These tools are invoked by the Extraction Agent to persist timer data
extracted from natural language input. Each tool returns structured
responses that the agent uses to confirm actions to the user.
"""

# Function docstrings with clear purpose
def create_timer(label: str, deadline_iso: str = None) -> dict:
    """
    Create a new timer in the database.

    Design Decision: We compute urgency immediately on creation to ensure
    the dashboard always shows current priorities without requiring refresh.

    Args:
        label: Human-readable task name
        deadline_iso: Optional ISO 8601 deadline string

    Returns:
        dict with timer_id, computed scores, and success status
    """
    pass

# Inline comments for non-obvious logic
def compute_urgency(deadline: datetime) -> float:
    # Urgency increases exponentially as deadline approaches
    # Using sigmoid curve to avoid sudden jumps
    hours_remaining = (deadline - datetime.utcnow()).total_seconds() / 3600

    # Cap at 1.0 for overdue, floor at 0.1 for far-future
    return max(0.1, min(1.0, 1 / (1 + math.exp(hours_remaining / 24))))
```

**Comment Coverage Goals:**

- Every module: Top-level docstring explaining purpose
- Every public function: Docstring with args, returns, design decisions
- Complex logic: Inline comments explaining "why" not "what"
- Agent instructions: Comments explaining delegation strategy

---

## 16. Project Journey Documentation

Track these elements throughout development for the competition writeup:

### Challenges & Solutions

- [ ] ADK setup and package installation issues
- [ ] Agent delegation patterns that didn't work
- [ ] Memory persistence edge cases
- [ ] Scoring algorithm iterations

### Key Decisions

- [ ] Why sequential agents vs parallel
- [ ] DatabaseSessionService vs InMemorySessionService
- [ ] Urgency scoring formula rationale
- [ ] Preference rule structure design

### Metrics & Results

- [ ] Number of agent invocations per user session
- [ ] Average extraction accuracy
- [ ] Preference learning effectiveness
- [ ] User feedback (if any testing done)

### Lessons Learned

- [ ] What worked well with ADK
- [ ] What would you do differently
- [ ] Surprising findings about agent behavior
- [ ] Performance characteristics

---
