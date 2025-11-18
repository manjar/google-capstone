# TimerMind System Specification

**Version:** 1.0
**Last Updated:** November 17, 2025
**Status:** Production

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Multi-Agent System Design](#multi-agent-system-design)
4. [Database Schema](#database-schema)
5. [API Endpoints](#api-endpoints)
6. [Tool Definitions](#tool-definitions)
7. [Scoring Algorithms](#scoring-algorithms)
8. [Location Services](#location-services)
9. [Testing Infrastructure](#testing-infrastructure)
10. [Appendix A: Spatiotemporal State Machine Model](#appendix-a-spatiotemporal-state-machine-model)

---

## Overview

TimerMind is a spatiotemporal state machine for intelligent daily planning. Unlike traditional task managers that treat location as metadata, TimerMind models the user's physical location as a first-class state variable and uses AI agents to reason about state transitions (travel) and optimal transition timing.

### Core Innovation

**Traditional Paradigm:** Calendar + Todo List
**TimerMind Paradigm:** Spatiotemporal State Machine with Intelligent Transition Planning

**Key Difference:** System maintains a model of user location over time and calculates when state transitions (departures) must occur to satisfy temporal constraints (deadlines).

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                         │
│                  (Web-based Chat Interface)                 │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Web Server                       │
│                    (main.py)                                │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                   Multi-Agent System                        │
│                   (Google ADK)                              │
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │  extraction_agent    │  │  preference_agent    │        │
│  │  (Gemini 2.5 Flash)  │  │  (Gemini 2.5 Flash)  │        │
│  └──────────────────────┘  └──────────────────────┘        │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                   Tool Layer                                │
│  • create_timer_tool          • calculate_travel_time_tool │
│  • update_timer_tool          • set_default_location_tool  │
│  • query_timers_tool          • store_notable_fact_tool    │
│  • complete_timer_tool                                      │
└───────────────┬─────────────────────────────────────────────┘
                │
    ┌───────────┴───────────┐
    ▼                       ▼
┌─────────────┐     ┌─────────────────┐
│  SQLite DB  │     │ Google Maps API │
│  (timers,   │     │ • Geocoding     │
│   prefs)    │     │ • Distance      │
└─────────────┘     │   Matrix        │
                    └─────────────────┘
```

### Technology Stack

**Backend:**
- Python 3.12+
- FastAPI (web framework)
- Uvicorn (ASGI server)
- SQLite (local database)

**AI/ML:**
- Google Gemini 2.5 Flash (LLM)
- Google ADK (Agent Development Kit)
- Google Vertex AI (cloud platform)

**Location Services:**
- Google Maps Geocoding API
- Google Maps Distance Matrix API

**Frontend:**
- Jinja2 templates
- Native JavaScript
- HTML5/CSS3

**Dependencies:**
- `google-generativeai` - Gemini SDK
- `google-adk` - Agent framework
- `google-cloud-aiplatform` - Vertex AI
- `python-dateutil` - ISO 8601 datetime parsing
- `requests` - HTTP client for Maps API
- `python-dotenv` - Environment configuration

---

## Multi-Agent System Design

### Agent Architecture

TimerMind uses a **two-agent architecture** with clear separation of concerns:

#### 1. extraction_agent

**Responsibility:** Task management and state machine operations

**Model:** `gemini-2.5-flash-001`

**Tools:**
- `create_timer_tool` - Create new timers/tasks
- `update_timer_tool` - Modify existing timers
- `query_timers_tool` - Search and list timers
- `complete_timer_tool` - Mark timers as done
- `calculate_travel_time_tool` - Calculate departure times for location-based timers

**System Instructions (Key Points):**
```
You are an extraction agent that creates, updates, queries, and completes timers.

CRITICAL: If user mentions going to a location or arriving somewhere by a time,
use calculate_travel_time_tool to determine when they need to LEAVE.

Create the timer for the DEPARTURE time, not the arrival time.

Store location metadata:
- destination_address: Where user is going
- origin_address: Where user is starting from (defaults to home)
- departure_time: When to leave (calculated)
- arrival_time: When to arrive (deadline)
- travel_time_minutes: Expected travel duration
- distance_km: Total distance

Urgency scoring: Based on buffer ratio (time_remaining / estimated_duration)
Priority: urgency × 0.6 + importance × 0.4
```

**Example Interaction:**
```
User: "Remind me to leave for Naschmarkt in Campbell by 3pm"

extraction_agent reasoning:
1. User wants to ARRIVE at Naschmarkt by 3pm
2. Need to calculate when to DEPART
3. Call calculate_travel_time_tool(
     destination="Naschmarkt, Campbell, CA",
     arrival_time_iso="2025-11-17T15:00:00"
   )
4. Tool returns: departure=2:35pm, travel_time=25min
5. Create timer:
   - label: "Leave for Naschmarkt"
   - deadline: 2:35pm (departure time)
   - destination_address: "Naschmarkt, Campbell, CA"
   - arrival_time: 3pm
   - travel_time_minutes: 25

Response: "I've set a reminder to leave at 2:35 PM. With current traffic,
it will take about 25 minutes to reach Naschmarkt in Campbell."
```

#### 2. preference_agent

**Responsibility:** Learning user preferences and managing persistent knowledge

**Model:** `gemini-2.5-flash-001`

**Tools:**
- `store_notable_fact_tool` - Save facts to Google ADK memory banks
- `set_default_location_tool` - Save user's home address

**Memory Banks:**
- `notable_facts` - User preferences and rules

**System Instructions (Key Points):**
```
You are a preference agent that learns user patterns and stores notable facts.

When user mentions:
- Category importance: "I care more about health tasks"
- Preference rules: "Always prioritize family over work"
- Default locations: "My home is at 123 Main St, San Jose"

Store these using:
- store_notable_fact_tool for preferences/rules
- set_default_location_tool for home address

Use memory banks to build persistent knowledge about user.
```

**Example Interaction:**
```
User: "My home address is 456 Elm Street, San Jose, CA"

preference_agent reasoning:
1. User is providing default location
2. Call set_default_location_tool(
     address="456 Elm Street, San Jose, CA"
   )
3. Store in database preferences table

Response: "I've saved your home address as 456 Elm Street, San Jose, CA.
I'll use this as the default starting point for travel calculations."
```

### Agent Orchestration

**Primary Agent:** extraction_agent handles most user interactions

**Secondary Agent:** preference_agent invoked when:
- User expresses preferences
- User provides home address
- User wants to save a rule or fact

**Session Management:**
- Each agent maintains separate session state
- Google ADK memory banks provide cross-session persistence
- SQLite database provides durable storage

**Handoff Protocol:**
```
User input → FastAPI endpoint → Determine agent
                                     ↓
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
             extraction_agent                  preference_agent
             (task operations)                 (learning)
                    │                                 │
                    └────────────→ Response ←─────────┘
```

---

## Database Schema

### timers table

Stores all timer/task data with spatiotemporal metadata.

```sql
CREATE TABLE IF NOT EXISTS timers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    description TEXT,
    deadline TEXT,  -- ISO 8601 datetime
    estimated_duration_minutes INTEGER,
    category TEXT DEFAULT 'other',
    tags TEXT,  -- JSON array
    urgency_score REAL,
    importance_score REAL,
    priority_score REAL,
    rationale TEXT,
    status TEXT DEFAULT 'pending',  -- pending, in_progress, completed
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    -- Location-aware fields (Phase 3)
    destination_address TEXT,
    origin_address TEXT,
    departure_time TEXT,  -- ISO 8601 datetime
    arrival_time TEXT,    -- ISO 8601 datetime
    travel_time_minutes INTEGER,
    distance_km REAL,
    last_travel_update TEXT  -- ISO 8601 datetime
)
```

**Field Descriptions:**

**Core Fields:**
- `id` - Unique identifier
- `label` - Short timer name (e.g., "Leave for Naschmarkt")
- `description` - Detailed notes
- `deadline` - When timer fires (departure time for location-based timers)
- `estimated_duration_minutes` - How long task takes
- `category` - Classification (work, health, family, personal, other)
- `tags` - JSON array of searchable tags
- `status` - Timer state (pending, in_progress, completed)
- `created_at` - Creation timestamp
- `updated_at` - Last modification timestamp

**Scoring Fields:**
- `urgency_score` - 0-100, based on buffer ratio
- `importance_score` - 0-100, based on category and user preferences
- `priority_score` - 0-100, weighted combination (urgency × 0.6 + importance × 0.4)
- `rationale` - Human-readable explanation of scores

**Location Fields:**
- `destination_address` - Where user needs to be
- `origin_address` - Where user is coming from (defaults to home)
- `departure_time` - When to leave (calculated from arrival - travel_time)
- `arrival_time` - Target arrival time (the deadline user cares about)
- `travel_time_minutes` - Expected travel duration with traffic
- `distance_km` - Total distance
- `last_travel_update` - When travel time was last calculated (for future re-evaluation)

### preferences table

Key-value store for user preferences and settings.

```sql
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT  -- JSON serialized
)
```

**Stored Preferences:**

- `default_location` - User's home address
  ```json
  "123 Main Street, San Jose, CA 95110"
  ```

- `preference_rules` - User-defined rules
  ```json
  [
    "Always prioritize family over work",
    "Exercise is important to me",
    "Prefer morning appointments"
  ]
  ```

---

## API Endpoints

### POST /api/chat

Send message to TimerMind agents.

**Request:**
```json
{
  "message": "Remind me to leave for Naschmarkt in Campbell by 3pm"
}
```

**Response:**
```json
{
  "response": "I've set a reminder to leave at 2:35 PM. With current traffic, it will take about 25 minutes to reach Naschmarkt in Campbell by your 3:00 PM deadline."
}
```

**Status Codes:**
- `200 OK` - Success
- `400 Bad Request` - Invalid message format
- `500 Internal Server Error` - Agent processing error

### GET /api/timers

Retrieve all active timers.

**Query Parameters:**
- `status` (optional) - Filter by status (pending, in_progress, completed)
- `category` (optional) - Filter by category

**Response:**
```json
{
  "timers": [
    {
      "id": 1,
      "label": "Leave for Naschmarkt",
      "deadline": "2025-11-17T14:35:00",
      "category": "other",
      "urgency_score": 85,
      "importance_score": 50,
      "priority_score": 71,
      "status": "pending",
      "destination_address": "Naschmarkt, Campbell, CA 95008",
      "origin_address": "San Jose, CA",
      "departure_time": "2025-11-17T14:35:00",
      "arrival_time": "2025-11-17T15:00:00",
      "travel_time_minutes": 25,
      "distance_km": 11.5
    }
  ]
}
```

### GET /api/preferences

Retrieve user preferences.

**Response:**
```json
{
  "preferences": {
    "default_location": "123 Main Street, San Jose, CA"
  }
}
```

### POST /api/reset

Clear all timers and preferences (for testing).

**Response:**
```json
{
  "message": "Database reset successfully"
}
```

**Status Codes:**
- `200 OK` - Reset successful

---

## Tool Definitions

### create_timer_tool

Create a new timer with automatic scoring.

**Signature:**
```python
def create_timer_tool(
    label: str,
    description: str = "",
    deadline_iso: str = "",
    estimated_duration_minutes: int = 30,
    category: str = "other",
    tags: list = None,
    destination_address: str = "",
    origin_address: str = "",
    departure_time_iso: str = "",
    arrival_time_iso: str = "",
    travel_time_minutes: int = 0,
    distance_km: float = 0.0
) -> dict
```

**Parameters:**
- `label` (required) - Timer name
- `description` - Detailed notes
- `deadline_iso` - ISO 8601 deadline (departure time for location-based)
- `estimated_duration_minutes` - Task duration estimate
- `category` - Classification
- `tags` - List of tags
- `destination_address` - Where user is going
- `origin_address` - Where user is starting from
- `departure_time_iso` - When to leave
- `arrival_time_iso` - When to arrive
- `travel_time_minutes` - Travel duration
- `distance_km` - Distance

**Returns:**
```json
{
  "success": true,
  "timer_id": 1,
  "message": "Timer created with priority score 71"
}
```

**Scoring:**
- Automatically calculates urgency, importance, priority
- Generates rationale for scores

### calculate_travel_time_tool

Calculate departure time for location-based timer.

**Signature:**
```python
def calculate_travel_time_tool(
    destination: str,
    arrival_time_iso: str,
    origin: str = ""
) -> dict
```

**Parameters:**
- `destination` (required) - Destination address
- `arrival_time_iso` (required) - ISO 8601 arrival deadline
- `origin` - Origin address (defaults to user's home)

**Returns:**
```json
{
  "success": true,
  "travel_time_minutes": 25,
  "distance_km": 11.5,
  "departure_time_iso": "2025-11-17T14:35:00",
  "arrival_time_iso": "2025-11-17T15:00:00",
  "origin_address": "San Jose, CA",
  "destination_address": "Naschmarkt, Campbell, CA 95008"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Location features not available - GOOGLE_MAPS_API_KEY not configured"
}
```

**Algorithm:**
1. Geocode destination address
2. Get origin (from parameter or default_location preference)
3. Call Distance Matrix API with arrival_time
4. Extract duration_in_traffic
5. Calculate: departure = arrival - travel_time
6. Return travel metadata

### update_timer_tool

Modify existing timer.

**Signature:**
```python
def update_timer_tool(
    timer_id: int = None,
    fuzzy_reference: str = "",
    label: str = None,
    description: str = None,
    deadline_iso: str = None,
    estimated_duration_minutes: int = None,
    category: str = None,
    tags: list = None,
    status: str = None
) -> dict
```

**Parameters:**
- `timer_id` - Exact timer ID, OR
- `fuzzy_reference` - Natural language reference (e.g., "the dinner timer")
- Update fields (all optional)

**Returns:**
```json
{
  "success": true,
  "message": "Timer updated successfully"
}
```

**Fuzzy Matching:**
- Uses LLM to interpret references
- "the dinner timer" → Matches timer with label containing "dinner"
- "my 3pm meeting" → Matches timer with deadline near 3pm

### query_timers_tool

Search and list timers.

**Signature:**
```python
def query_timers_tool(
    status: str = None,
    category: str = None,
    deadline_before: str = None,
    deadline_after: str = None,
    sort_by: str = "priority_score",
    limit: int = 10
) -> dict
```

**Parameters:**
- `status` - Filter by status
- `category` - Filter by category
- `deadline_before` - ISO 8601 upper bound
- `deadline_after` - ISO 8601 lower bound
- `sort_by` - Sort field (priority_score, deadline, urgency_score)
- `limit` - Max results

**Returns:**
```json
{
  "timers": [
    {
      "id": 1,
      "label": "Leave for Naschmarkt",
      "deadline": "2025-11-17T14:35:00",
      "priority_score": 71,
      "urgency_score": 85,
      "importance_score": 50
    }
  ],
  "count": 1
}
```

### complete_timer_tool

Mark timer as completed.

**Signature:**
```python
def complete_timer_tool(
    timer_id: int = None,
    fuzzy_reference: str = ""
) -> dict
```

**Returns:**
```json
{
  "success": true,
  "message": "Timer marked as completed"
}
```

### set_default_location_tool

Save user's home address.

**Signature:**
```python
def set_default_location_tool(
    address: str
) -> dict
```

**Returns:**
```json
{
  "success": true,
  "message": "Default location saved"
}
```

**Storage:**
```sql
INSERT OR REPLACE INTO preferences (key, value)
VALUES ('default_location', '"123 Main St, San Jose, CA"')
```

### store_notable_fact_tool

Save user preference or rule to memory bank.

**Signature:**
```python
def store_notable_fact_tool(
    fact: str
) -> dict
```

**Example:**
```python
store_notable_fact_tool("User prioritizes family over work")
```

**Storage:** Google ADK memory bank `notable_facts`

---

## Scoring Algorithms

### Urgency Score

Based on **buffer ratio** - time remaining relative to estimated duration.

**Formula:**
```python
buffer_ratio = time_remaining_minutes / estimated_duration_minutes

if buffer_ratio < 1.0:
    urgency = 100  # CRITICAL - past optimal start time
elif buffer_ratio < 2.0:
    urgency = 80   # HIGH - should start soon
elif buffer_ratio < 5.0:
    urgency = 60   # MODERATE
elif buffer_ratio < 10.0:
    urgency = 40   # LOW
else:
    urgency = 20   # VERY LOW
```

**Rationale:**
- Buffer ratio < 1.0 means insufficient time to complete task
- Ratio 1.0-2.0 means task should start within next duration period
- Scales naturally for both short and long tasks

**Example:**
```
Task: "Prepare presentation" (estimated 2 hours)
Deadline: 4 hours from now

buffer_ratio = 240 min / 120 min = 2.0
urgency_score = 60 (MODERATE)
```

### Importance Score

Based on task category and user preferences.

**Default Category Values:**
```python
DEFAULT_CATEGORY_IMPORTANCE = {
    "work": 80,
    "health": 90,
    "family": 95,
    "personal": 50,
    "other": 40
}
```

**Calculation:**
```python
base_importance = DEFAULT_CATEGORY_IMPORTANCE[category]

# Future: Adjust based on user preferences from memory bank
# e.g., "I care more about exercise" → health tasks +10

importance_score = min(100, base_importance + adjustments)
```

### Priority Score

Combined score for ranking.

**Formula:**
```python
priority_score = urgency_score × 0.6 + importance_score × 0.4
```

**Rationale:**
- Urgency weighted 60% - time pressure drives action
- Importance weighted 40% - user values influence ranking
- Produces scores in range 0-100

**Example:**
```
Task: "Prepare presentation" (work category)
urgency_score = 60
importance_score = 80

priority_score = 60 × 0.6 + 80 × 0.4
               = 36 + 32
               = 68
```

---

## Location Services

### Google Maps Service Integration

**Module:** `services/google_maps_service.py`

**Class:** `GoogleMapsService`

#### Geocoding

**Method:** `geocode(address: str) -> Optional[Dict]`

**API:** Google Maps Geocoding API

**Request:**
```
GET https://maps.googleapis.com/maps/api/geocode/json
  ?address=Naschmarkt,Campbell,CA
  &key=YOUR_API_KEY
```

**Response Processing:**
```python
{
  "formatted_address": "Naschmarkt, Campbell, CA 95008, USA",
  "lat": 37.2871651,
  "lng": -121.9499568
}
```

#### Travel Time Calculation

**Method:** `calculate_travel_time(origin: str, destination: str, arrival_time: datetime) -> Optional[Dict]`

**API:** Google Maps Distance Matrix API

**Request:**
```
GET https://maps.googleapis.com/maps/api/distancematrix/json
  ?origins=San+Jose,CA
  &destinations=Campbell,CA
  &mode=driving
  &arrival_time=1700251200
  &traffic_model=best_guess
  &key=YOUR_API_KEY
```

**Response Processing:**
```python
{
  "origin_address": "San Jose, CA, USA",
  "destination_address": "Campbell, CA, USA",
  "distance_meters": 11500,
  "distance_km": 11.5,
  "duration_minutes": 13,
  "duration_in_traffic_minutes": 25  # With real-time traffic
}
```

#### Departure Time Calculation

**Method:** `calculate_departure_time(origin: str, destination: str, arrival_time: datetime) -> Tuple[datetime, int, float]`

**Algorithm:**
```python
def calculate_departure_time(origin, destination, arrival_time):
    # 1. Get travel time with traffic at arrival_time
    result = calculate_travel_time(origin, destination, arrival_time)
    travel_minutes = result["duration_in_traffic_minutes"]

    # 2. Calculate departure time
    departure_time = arrival_time - timedelta(minutes=travel_minutes)

    # 3. Return departure, travel time, distance
    return (departure_time, travel_minutes, result["distance_km"])
```

**Example:**
```python
origin = "San Jose, CA"
destination = "Naschmarkt, Campbell, CA"
arrival_time = datetime(2025, 11, 17, 15, 0)  # 3:00 PM

departure, travel_min, distance = calculate_departure_time(origin, destination, arrival_time)

# Results:
# departure = datetime(2025, 11, 17, 14, 35)  # 2:35 PM
# travel_min = 25
# distance = 11.5
```

**Traffic Awareness:**
- Uses `arrival_time` parameter to query traffic at future time
- Traffic model: `best_guess` (recommended by Google)
- Future enhancement: Periodic re-evaluation for dynamic updates

---

## Testing Infrastructure

### Interactive Test Harness

**Module:** `tests/test_harness.py`

**Purpose:** Simulate user interactions and validate agent behavior

**Features:**
- Browser-like FastAPI request simulation
- Step-by-step execution with pauses
- LLM-based response evaluation
- Detailed pass/fail reporting
- JSON-based test case definitions

### Test Case Format

**File:** `tests/test_cases.json`

```json
{
  "test_id": "test_004_location_based_reminder",
  "description": "User asks for reminder to leave for a location by specific time",
  "user_messages": [
    "Remind me to leave for Naschmarkt in Campbell by 3pm"
  ],
  "expected_behavior": [
    "System should use Google Maps to calculate travel time from default location to Naschmarkt",
    "Should create a timer for departure time (arrival time minus travel time)",
    "Timer should include destination_address and travel_time_minutes",
    "Response should mention the calculated departure time"
  ],
  "reset_database": true
}
```

### LLM Evaluation

**Process:**
1. Run test case (send user messages to API)
2. Collect agent responses
3. Query Gemini with evaluation prompt:
   ```
   Evaluate if the system response satisfies these criteria:
   - Used Google Maps to calculate travel time
   - Created timer for departure (not arrival)
   - Stored location metadata
   - Mentioned departure time to user

   System response: "I've calculated you'll need 25 minutes to reach
   Naschmarkt. I'll remind you to leave at 2:35 PM to arrive by 3:00 PM."

   Does this response satisfy all criteria? Respond PASS or FAIL.
   ```
4. Parse LLM verdict (PASS/FAIL)
5. Generate report

### Running Tests

**Interactive mode:**
```bash
cd tests
python test_harness.py
```

**Automated mode:**
```bash
python test_harness.py --auto
```

**Specific test:**
```bash
python test_harness.py --test-id test_004_location_based_reminder
```

**Google Maps API test:**
```bash
cd ..
python test_maps_api.py
```

---

## Appendix A: Spatiotemporal State Machine Model

### Formal Definition

TimerMind models daily life as a **spatiotemporal state machine** - a discrete-time system where state represents physical location and transitions represent travel events.

### Mathematical Formulation

**State Space:**
```
S = {s₁, s₂, ..., sₙ}  where sᵢ ∈ Locations
```

**State Variable:**
```
σ(t) : Time → Location
σ(t) represents user's location at time t
```

**Events:**
```
E = Eₙₜ ∪ Eₜᵣ

Eₙₜ = Non-transitional events (tasks at current location)
Eₜᵣ = Transitional events (travel that changes location)
```

**Transition Function:**
```
δ : S × Eₜᵣ → S

For travel event e ∈ Eₜᵣ:
  δ(σ(t), e) = σ(t + Δt)  where Δt = travel_time(e)
```

**Constraints:**

1. **Temporal Constraint:**
   ```
   For event e with deadline d:
     t_start(e) + duration(e) ≤ d
   ```

2. **Spatial Constraint:**
   ```
   For event e requiring location s:
     σ(t_event) = s
   ```

3. **Transition Constraint:**
   ```
   To satisfy σ(t₂) = s₂ given σ(t₁) = s₁:
     Must execute transition at t_depart = t₂ - travel_time(s₁, s₂)
   ```

### Example: State Machine Execution

**Scenario:**
```
User input: "Meeting at 3pm at Naschmarkt in Campbell"
Current time: 1:00 PM
Current location: home (San Jose)
```

**State Machine Model:**

**States:**
```
S = {home, naschmarkt}
```

**Initial State:**
```
σ(1:00 PM) = home
```

**Goal State:**
```
σ(3:00 PM) = naschmarkt
```

**Transition:**
```
e_travel: home → naschmarkt
travel_time(home, naschmarkt) = 25 minutes (with traffic)
```

**Constraint:**
```
σ(3:00 PM) = naschmarkt  (must be at Naschmarkt by 3pm)
```

**Backward Calculation:**
```
t_departure = 3:00 PM - 25 min = 2:35 PM

Required state sequence:
  σ(1:00 PM)  = home
  σ(2:35 PM)  = home (still at home)
  σ(2:35 PM+) = in_transit (just departed)
  σ(3:00 PM)  = naschmarkt (arrived)
```

**Timer Creation:**
```
Create timer:
  label: "Leave for Naschmarkt"
  deadline: 2:35 PM (departure time)
  destination_address: "Naschmarkt, Campbell, CA"
  arrival_time: 3:00 PM
  travel_time_minutes: 25
```

**System Action:**
```
At 2:35 PM → Alert user: "Time to leave for Naschmarkt"
User executes transition: σ(2:35 PM) → σ(3:00 PM)
```

### Multi-Stop Scenario (Future)

**Input:**
```
"I need to go to the post office, then Naschmarkt, then pick up Willem at 3pm"
```

**State Sequence:**
```
σ(t₀) = home
σ(t₁) = post_office
σ(t₂) = naschmarkt
σ(t₃) = school (Willem's location)
```

**Transitions:**
```
e₁: home → post_office          (Δt₁ = 15 min)
e₂: post_office → naschmarkt    (Δt₂ = 10 min)
e₃: naschmarkt → school         (Δt₃ = 20 min)
```

**Constraints:**
```
Final constraint: σ(3:00 PM) = school

Backward calculation:
  t₃ = 3:00 PM (arrival at school)
  t₂_depart = t₃ - Δt₃ = 2:40 PM (leave Naschmarkt)
  t₁_depart = t₂_depart - Δt₂ = 2:30 PM (leave post office)
  t₀_depart = t₁_depart - Δt₁ = 2:15 PM (leave home)

Assuming 10 min at post office and 15 min at Naschmarkt:
  t₀_depart = 2:15 PM
  t₁_arrive = 2:30 PM, stay 10 min, t₁_depart = 2:40 PM
  t₂_arrive = 2:50 PM, stay 15 min, t₂_depart = 3:05 PM
  t₃_arrive = 3:25 PM
```

**Feasibility Check:**
```
Required: t₃_arrive ≤ 3:00 PM
Actual:   t₃_arrive = 3:25 PM

CONFLICT DETECTED: Timeline impossible
  - You'll be 25 minutes late picking up Willem
```

**Optimization:**
```
To satisfy constraint:
  Option 1: Reduce time at stops (5 min each)
  Option 2: Skip Naschmarkt stop
  Option 3: Reorder: Naschmarkt → post office → school
```

This is the power of the state machine model: **automatic timeline validation and conflict detection**.

### Comparison to Traditional Paradigm

**Traditional Calendar/Todo:**
```
Calendar:
  3:00 PM - Meeting at Naschmarkt

Todo List:
  [ ] Prepare for meeting
  [ ] Drive to Campbell

User Mental Model:
  "I need to calculate when to leave"
  "Check Google Maps for traffic"
  "Remember to leave by ~2:30"
```

**TimerMind State Machine:**
```
User Input:
  "Meeting at 3pm at Naschmarkt"

System State Model:
  σ(now) = home
  σ(3pm) = naschmarkt
  Transition: travel(home → naschmarkt) = 25 min
  Departure: 3pm - 25min = 2:35pm

System Action:
  Create timer at 2:35pm: "Leave for Naschmarkt"
  Monitor traffic, update if needed
  Alert user at optimal departure time
```

**Key Difference:**
- Traditional: User maintains mental model of state graph
- TimerMind: System maintains state graph, user receives actionable alerts

### Advanced Features (Future)

#### 1. Probabilistic Transitions

Model travel time as probability distribution:
```
travel_time ~ N(μ=25, σ=5)  (Normal distribution)

P(arrive_on_time | depart_at_t) = P(travel_time < 3:00 PM - t)

Choose t such that P(arrive_on_time) ≥ 0.95 (95% confidence)
```

#### 2. Conflict Detection

For state graph with multiple events:
```
Conflicts arise when:
  1. Two events require same location at different times
  2. Timeline physically impossible (insufficient travel time)
  3. Sequential events have overlapping time windows

Algorithm:
  1. Construct complete state graph for day
  2. Validate all transitions satisfy temporal constraints
  3. Identify conflicting events
  4. Propose timeline adjustments
```

#### 3. Route Optimization

For multiple stops, solve Traveling Salesman Problem (TSP):
```
Given: Set of locations L = {l₁, l₂, ..., lₙ}
Constraint: Must visit all locations, return home
Objective: Minimize total travel time

Solution: Branch-and-bound with time window constraints

Example:
  Locations: {post_office, grocery, school}
  Time windows: post_office before 5pm, school at 3pm
  Optimal order: school (3pm) → post_office (4pm) → grocery (5pm) → home
```

#### 4. Dynamic Re-Optimization

Monitor traffic continuously:
```
Every 15 minutes:
  1. Re-query travel time for pending transitions
  2. Compare to previous estimate
  3. If Δtravel_time > threshold (e.g., 10 minutes):
     - Recalculate departure time
     - Alert user: "Traffic increased, leave NOW"
     - Update timer deadline
```

### Why This Model Matters

**Cognitive Load Reduction:**
- User: "I need to be at X by time T"
- System: "Leave at time T - Δt"

**Spatial Reasoning Automation:**
- System maintains location state
- Calculates optimal transitions
- Validates timeline feasibility

**Real-World Constraint Modeling:**
- Physical presence required at locations
- Travel takes time (varies with traffic)
- Time is finite and sequential
- Conflicts are spatial AND temporal

**Novel Applications:**
- Proactive departure alerts
- Conflict detection before commitment
- Multi-stop route optimization
- Day-wide timeline validation
- Probabilistic on-time arrival guarantees

---

## Conclusion

TimerMind represents a paradigm shift from **task-centric** to **spatiotemporal state-centric** planning. By modeling location as first-class state and using AI agents to reason about state transitions, the system offloads spatial and temporal reasoning from the user to the machine.

This specification documents the current implementation (Phase 3: Location-Aware State Machine) and provides a foundation for future enhancements including timeline modeling, conflict detection, and dynamic re-optimization.

**Core Philosophy:**
> Traditional productivity tools ask: "What do you need to do?"
>
> TimerMind asks: "Where do you need to be, and when do you need to start moving?"

---

**Document Version:** 1.0
**Last Updated:** November 17, 2025
**Next Review:** December 2025 (after timeline modeling implementation)
