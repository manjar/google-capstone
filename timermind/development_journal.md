# TimerMind Development Journal

## Overview

This journal documents the design decisions, implementation challenges, and conceptual evolution of TimerMind - a spatiotemporal state machine for intelligent daily planning.

---

## Phase 1: Initial Concept & Multi-Agent Architecture

### November 2025

**Initial Problem Statement:**
Traditional task management systems require users to maintain complex mental models of:
- What needs to be done
- When things need to be done
- Where things need to be done
- How long tasks take
- When to leave for location-based appointments

This cognitive overhead is unnecessary - an AI system should handle the spatial and temporal reasoning.

### Design Decision: Multi-Agent Architecture

**Initial Design:** 4-agent system
- extraction_agent: Parse user input
- planning_agent: Schedule and prioritize
- preference_agent: Learn user patterns
- query_agent: Answer questions

**Problem Encountered:** Agent responsibility overlap and inefficiency
- Extraction and planning were tightly coupled
- Query agent just wrapped database queries
- Unnecessary context switching between agents

**Solution:** Consolidated to 2-agent system
- **extraction_agent**: Parse input, create/update/query timers, manage state
- **preference_agent**: Learn patterns, store notable facts via Google ADK memory banks

**Result:** Simpler, faster, and more maintainable while preserving all functionality.

### Technology Choice: Google ADK + Gemini 2.5 Flash

**Why Google ADK:**
- Built-in memory banks for persistent agent knowledge
- Tool/function calling support
- Multi-agent orchestration primitives
- Tight integration with Gemini models

**Why Gemini 2.5 Flash:**
- Fast inference (critical for real-time chat interface)
- Strong reasoning capabilities for task parsing
- Cost-effective for production use
- Good function calling accuracy

**Alternative Considered:** Custom LangChain implementation
- **Rejected because:** More boilerplate, memory management complexity, ADK memory banks provide superior semantic storage

---

## Phase 2: Intelligent Prioritization

### Key Insight: Buffer Ratio Urgency Scoring

**Problem:** How to quantify urgency objectively?

**Traditional Approach:** Absolute time thresholds
- "Due in < 1 hour" = urgent
- "Due in > 1 week" = not urgent

**Problem with Traditional Approach:**
- A 30-minute task due in 2 hours is MORE urgent than a 4-hour task due tomorrow
- Absolute time doesn't account for task complexity

**Our Solution: Buffer Ratio**

```
urgency_score = f(buffer_ratio)
buffer_ratio = time_remaining / estimated_duration

Examples:
- Task takes 1 hour, due in 30 minutes → buffer_ratio = 0.5 → CRITICAL
- Task takes 1 hour, due in 2 hours → buffer_ratio = 2.0 → MODERATE
- Task takes 1 hour, due in 10 hours → buffer_ratio = 10.0 → LOW
```

**Implementation:**
```python
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

This approach naturally adapts to both short and long tasks.

### Category-Based Importance Scoring

**Observation:** Users inherently value certain categories more than others.

**Implementation:**
- Default importance values: work=80, health=90, family=95, personal=50
- Preference agent learns adjustments: "I care more about exercise"
- importance_score combines default category importance with learned preferences

**Result:** Priority = urgency × 0.6 + importance × 0.4
- Time pressure (urgency) weighted more heavily for actionability
- User values (importance) still influence ranking

---

## Phase 3: Spatiotemporal State Machine (THE BIG SHIFT)

### November 17, 2025

### The Conceptual Breakthrough

**User Insight:**
> "This really is a new kind of day planning system. Instead of a calendar and to-do list where the user has to check both and build a mental model of all needed actions (including transportation), the underlying model here is truly a state machine with 'look ahead'. The 'state' is the user's location, and there are many events that may not change the location and some that do. The look ahead is presented as timers. The agent here helps by inferring lots of useful information about, and based on, the state graph."

This crystallized our core innovation: **We're not building a task manager, we're building a location-aware state machine.**

### Formal Model

**States (S):** User locations
- S = {home, office, grocery_store, school, naschmarkt, ...}

**State Variable:** s(t) = user's location at time t

**Events (E):** Two types
1. **Non-transitional events:** Tasks that don't change location
   - e.g., "cook dinner" while s(t) = home
2. **Transitional events:** Travel that changes state
   - e.g., "go to Naschmarkt" → s(t+Δt) = naschmarkt

**Transitions:** Real-world travel with constraints
- Duration: f(origin, destination, traffic, time_of_day)
- Distance: Euclidean + road network
- Feasibility: Can user reach destination by deadline?

**Timers as Look-Ahead:**
- Not just deadlines, but **departure notifications**
- System calculates: "You need to START MOVING at time T to reach state S by deadline D"

### Why This Is Novel

**Traditional Calendar/Todo Paradigm:**
```
Calendar:
  3:00 PM - Meeting at Naschmarkt

Todo List:
  [ ] Prepare for meeting

User's Mental Model:
  "It's 2:00 PM, meeting is at 3:00 PM in Campbell,
   I'm in San Jose, it takes ~25 minutes,
   I should leave around 2:30 PM"
```

**TimerMind Spatiotemporal Paradigm:**
```
User Input:
  "Meeting at 3pm at Naschmarkt in Campbell"

System State Graph:
  s(now) = home (San Jose)
  s(3:00 PM) = naschmarkt (Campbell)

System Reasoning:
  - Current state: home
  - Target state: naschmarkt
  - Transition required: home → naschmarkt
  - Travel time: 25 minutes (with current traffic)
  - Optimal departure: 2:35 PM

System Action:
  - Create timer: "Leave for Naschmarkt" at 2:35 PM
  - Monitor traffic, update departure time if needed
```

**Key Difference:** User offloads spatial reasoning to the system. The system maintains the state graph, calculates transitions, and provides actionable alerts.

### Implementation Decisions

#### Google Maps Platform Integration

**APIs Chosen:**
1. **Geocoding API** - Address → (lat, lng)
2. **Distance Matrix API** - Origin × Destination → travel time with traffic

**Why Distance Matrix over Directions API:**
- Directions API returns turn-by-turn routes (unnecessary overhead)
- Distance Matrix API returns duration_in_traffic (exactly what we need)
- Distance Matrix supports arrival_time parameter for reverse calculation

**Key Parameters:**
```python
params = {
    "origins": origin_address,
    "destinations": destination_address,
    "mode": "driving",  # Future: support walking, transit
    "departure_time": "now",  # For traffic-aware estimates
    "traffic_model": "best_guess"
}
```

#### Database Schema Extension

**Challenge:** Add location fields without breaking existing installations

**Solution:** Safe ALTER TABLE with try/except
```python
try:
    cursor.execute("ALTER TABLE timers ADD COLUMN destination_address TEXT")
except sqlite3.OperationalError:
    pass  # Column already exists
```

**New Columns:**
- `destination_address` - Where user needs to be
- `origin_address` - Where user is coming from (defaults to home)
- `departure_time` - When to leave (calculated)
- `arrival_time` - When to arrive (deadline)
- `travel_time_minutes` - Expected duration
- `distance_km` - Total distance
- `last_travel_update` - When we last checked traffic

#### Tool Design: calculate_travel_time_tool

**Function Signature:**
```python
def calculate_travel_time_tool(
    destination: str,
    arrival_time_iso: str,
    origin: str = ""
) -> dict
```

**Design Decisions:**

1. **Why arrival_time instead of departure_time?**
   - Users think in terms of deadlines: "I need to be there by 3pm"
   - System calculates backwards: arrival - travel_time = departure
   - More intuitive for user input

2. **Why optional origin?**
   - Most trips start from home
   - Preference agent stores default_location
   - Power users can override: "From the office to the store by 5pm"

3. **Why return full travel metadata?**
   - Transparency: User sees "25 min travel, leave at 2:35pm"
   - Future optimization: Can analyze distance_km for route efficiency
   - Debugging: Verify API results are sensible

**Error Handling:**
```python
if not maps_service.is_enabled():
    return {
        "success": False,
        "error": "Location features not available - GOOGLE_MAPS_API_KEY not configured"
    }
```
Graceful degradation - system works without Maps API, just no location features.

#### Agent Instruction Updates

**extraction_agent instructions (added):**
```
Location-Aware Features:
- If user mentions going to a location or arriving somewhere by a time, use the
  calculate_travel_time_tool to determine when they need to leave
- The tool will calculate travel time with current traffic conditions and return
  a recommended departure time
- Create the timer with the departure time, and store the destination address and
  travel information in the location fields
```

**Example:**
```
User: "Remind me to leave for Naschmarkt in Campbell by 3pm"

Agent Reasoning:
1. User wants to ARRIVE at Naschmarkt by 3pm
2. Need to calculate travel time
3. Call calculate_travel_time_tool(
     destination="Naschmarkt, Campbell, CA",
     arrival_time_iso="2025-11-17T15:00:00"
   )
4. Tool returns: departure_time = 2:35pm, travel_time = 25 min
5. Create timer:
   - label: "Leave for Naschmarkt"
   - deadline: 2:35pm (departure time)
   - destination_address: "Naschmarkt, Campbell, CA"
   - arrival_time: 3:00pm
   - travel_time_minutes: 25
```

### Challenges & Solutions

#### Challenge 1: Geocoding Ambiguity

**Problem:** "Campbell" could be Campbell, CA or Campbell, OH or Campbell River, BC

**Solution:**
- Encourage users to provide more context: "Campbell, CA"
- Google Maps Geocoding API returns formatted_address - store this for verification
- Future: Learn user's typical locations, default to nearest match

#### Challenge 2: Traffic Variability

**Problem:** Traffic at 2:35 PM might differ from traffic RIGHT NOW

**Solution (Current):** Use departure_time=now for best available estimate

**Solution (Future):**
- Periodic re-evaluation: Check traffic every 15 minutes
- Update departure time if traffic worsens
- Alert: "Traffic increased - leave NOW instead of 2:35pm"

#### Challenge 3: Multi-Stop Trips

**Problem:** "Go to post office, then Naschmarkt, then pick up Willem by 3pm"

**Current Limitation:** Can only handle single origin → destination

**Future Solution:**
- Model as state transition chain: home → post_office → naschmarkt → school
- Calculate cumulative travel time
- Validate timeline feasibility
- Optimize order (Traveling Salesman Problem)

### Test Infrastructure

**Testing Challenge:** How to validate AI agent behavior?

**Solution: LLM-Based Evaluation**

Traditional unit tests can't evaluate:
- "Did the agent create a sensible timer?"
- "Is the urgency score reasonable?"
- "Did it correctly interpret 'between X and Y'?"

**Our Approach:**
1. Define test cases with expected behavior (not exact outputs)
2. Run agent interaction
3. Use Gemini to evaluate: "Does this response satisfy the expected behavior?"

**Example Test Case:**
```json
{
  "test_id": "test_004_location_based_reminder",
  "description": "User asks for reminder to leave for a location by a specific time",
  "user_messages": [
    "Remind me to leave for Naschmarkt in Campbell by 3pm"
  ],
  "expected_behavior": [
    "System should use Google Maps to calculate travel time from default location to Naschmarkt",
    "Should create a timer for departure time (arrival time minus travel time)",
    "Timer should include destination_address and travel_time_minutes",
    "Response should mention the calculated departure time"
  ]
}
```

**LLM Evaluation Prompt:**
```
Evaluate if the system response satisfies:
1. Used Google Maps to calculate travel time
2. Created timer for departure (not arrival)
3. Stored location metadata
4. Mentioned departure time to user

Response: "I've calculated you'll need 25 minutes to reach Naschmarkt.
I'll remind you to leave at 2:35 PM to arrive by 3:00 PM."

Result: PASS - All criteria met
```

**Why This Works:**
- Tests behavior, not implementation details
- Resilient to agent response phrasing changes
- Can evaluate semantic understanding
- Scales to complex multi-turn conversations

---

## Phase 4: Testing & Validation

### Google Maps API Integration Testing

**Initial Error:** REQUEST_DENIED

**Root Cause:** API key configured but APIs not enabled in Google Cloud Console

**Fix:** Enable Geocoding API and Distance Matrix API

**Lesson Learned:** API key alone is insufficient - must enable specific APIs per project

**Test Results:**
```
✓ Geocoding successful for 'Campbell, CA'
  - Formatted: Campbell, CA, USA
  - Coordinates: (37.2871651, -121.9499568)

✓ Travel time calculation: San Jose → Campbell
  - Distance: 11.5 km
  - Duration without traffic: 13 minutes
  - Duration in traffic: 14.6 minutes (best guess)

✓ Departure time calculation for 2-hour-ahead arrival
  - Travel time: 14.6 minutes
  - Recommended departure: 1:45:24 before arrival
```

### Interactive Test Harness

**Design Philosophy:** Mimic browser-based user interaction

**Features:**
- Simulated FastAPI requests
- Step-by-step execution with pauses
- Console output of agent reasoning
- LLM-based pass/fail evaluation
- Detailed HTML-style reporting

**Usage:**
```bash
# Interactive mode (pause after each test)
python test_harness.py

# Automated mode (run all tests)
python test_harness.py --auto

# Single test
python test_harness.py --test-id test_004_location_based_reminder
```

---

## Architecture Evolution

### From Tasks to States: Conceptual Shift

**Traditional Task Manager Mental Model:**
```
Task = {
  title: string,
  deadline: datetime,
  priority: int,
  completed: bool
}
```

**TimerMind State Machine Model:**
```
State = Location
Timer = StateTransition | StateEvent
StateTransition = {
  from: Location,
  to: Location,
  trigger_time: datetime,  // When to depart
  arrival_time: datetime,  // When to arrive
  constraints: {
    travel_time: duration,
    distance: km,
    traffic: real_time
  }
}
```

**Implications:**
1. **Timers aren't tasks** - they're notifications of state changes
2. **Location is first-class** - not metadata, but core state
3. **Time is relative to space** - "when to leave" depends on "where to go"
4. **Agent reasons about graphs** - not lists, but state transition networks

### Why State Machines for Daily Life?

**Real world is spatiotemporal:**
- Physical presence is required at specific locations
- Movement takes time
- Time is finite and sequential
- Conflicts arise from spatial/temporal impossibility

**Example of Traditional Tool Failure:**
```
Google Calendar:
  2:00 PM - Meeting in San Francisco
  3:00 PM - Dentist in San Jose

User sees two appointments, doesn't realize:
  - SF to SJ takes 1 hour
  - Can't make 3pm dentist
  - Timeline is physically impossible
```

**TimerMind State Machine Approach (Future):**
```
State Graph:
  s(2:00 PM) = san_francisco
  s(3:00 PM) = san_jose

Constraint Analysis:
  - Transition: san_francisco → san_jose
  - Required time: 60 minutes
  - Available time: 0 minutes (back-to-back)

Conflict Detection:
  ⚠️ TIMELINE IMPOSSIBLE
  "You have a dentist appointment at 3pm in San Jose, but your
   meeting in San Francisco doesn't end until 3pm. Travel time
   is 60 minutes. You'll be 60 minutes late."

Suggestions:
  1. Move dentist to 4:30pm
  2. End SF meeting at 2:00pm (leave by 2pm)
  3. Cancel one appointment
```

This is impossible with traditional calendars without manual spatial reasoning.

---

## Future Research Directions

### Probabilistic State Modeling

**Current Limitation:** Deterministic travel times
- "25 minutes in traffic" is a point estimate
- Real travel time is a distribution: N(μ=25, σ=5)

**Future Enhancement: Bayesian State Transitions**
```
P(arrive_on_time | leave_at_T) = ∫ P(travel_time < deadline - T) dt

Choose departure time T such that:
  P(arrive_on_time) > confidence_threshold (e.g., 95%)
```

**User Preference:**
- Risk-averse user: 95% confidence → leave earlier
- Risk-tolerant user: 70% confidence → cut it closer
- Preference agent learns from user feedback: "Was I late?"

### Multi-User Coordination

**Scenario:** "Pick up Willem at 3pm"

**Current System:** Creates timer at departure time

**Future Enhancement:**
- Query Willem's state at 3pm: Is he available?
- Does Willem's timeline include being at pickup location?
- Coordinate: "Willem's soccer practice ends at 3:15pm, not 3pm"

**Technical Requirements:**
- Shared state graphs
- Multi-user conflict detection
- Privacy-preserving state sharing

### Activity Duration Learning

**Problem:** Users estimate task duration poorly
- "Grocery shopping takes 30 minutes" → Actually takes 55 minutes
- System should learn from historical data

**Solution:**
1. Track timer creation → completion time
2. Build duration model: duration(activity, user) = learned_estimate
3. Improve urgency scoring with realistic durations
4. Alert: "You estimated 30 min but this usually takes you 50 min"

**Example:**
```
Historical Data:
  - "Grocery shopping" completed 12 times
  - Average duration: 52 minutes
  - Standard deviation: 8 minutes

Future Timer:
  User: "Buy groceries before dinner at 6pm"
  Estimated duration: 30 minutes (user input)
  Learned duration: 52 ± 8 minutes (historical)

  System: "Based on your history, grocery shopping usually takes
           you about 50 minutes. I'll set a reminder for 5:00 PM
           to ensure you finish by 6pm."
```

### Route Optimization Across Multiple Stops

**Traveling Salesman Problem (TSP) for Daily Errands:**

**Input:**
```
"I need to go to:
  - Post office (closes at 5pm)
  - Grocery store (closes at 9pm)
  - Pick up Willem at soccer practice (3:15pm)
  - Return home by 6pm for dinner"
```

**Constraints:**
- Time windows: post office < 5pm, Willem = 3:15pm, home ≤ 6pm
- Minimize total travel time
- Respect temporal ordering: Willem pickup before dinner

**Solution:**
```
Optimal Route:
  12:00 PM - Start from home
  1:00 PM - Arrive at post office (30 min errand + 30 min travel)
  2:00 PM - Depart for grocery store
  2:30 PM - Arrive at grocery store (30 min shopping)
  3:00 PM - Depart for soccer field
  3:15 PM - Pick up Willem
  3:45 PM - Depart for home
  4:15 PM - Arrive home (well before 6pm dinner)

Timeline Validation: ✓ FEASIBLE
Total Travel Time: 105 minutes
Buffer Before Dinner: 105 minutes
```

**Algorithm:**
- Constraint Satisfaction Problem (CSP)
- Branch and bound with time window pruning
- Heuristic: Visit time-constrained locations first

### Weather Integration

**Observation:** Rain increases travel time 10-20%

**Future Enhancement:**
```
Weather API → Expected precipitation at departure time
If rain_probability > 70%:
  adjusted_travel_time = base_time × 1.15
  earlier_departure = arrival_time - adjusted_travel_time

Alert: "Rain forecast - leave 5 minutes early (2:30pm instead of 2:35pm)"
```

### Calendar Bidirectional Sync

**Integration with Google Calendar:**
1. Import calendar events as timers with locations
2. Export timers as calendar events
3. Detect conflicts between calendar and state graph
4. Propose timeline fixes

**Value Add:** TimerMind provides spatiotemporal validation layer over calendar

---

## Lessons Learned

### 1. Start Simple, Validate Core Concept

We didn't build timeline modeling, conflict detection, or multi-stop optimization first. We built:
- Basic location awareness
- Single origin → destination travel
- Departure time calculation

**Result:** Core concept validated, user value demonstrated, foundation for future enhancements established.

### 2. Let Users Guide the Vision

The "spatiotemporal state machine" framing came from USER feedback, not initial design docs.

**Lesson:** Build, observe, listen. Users often see your system's true potential more clearly than you do.

### 3. LLM-Based Testing for AI Systems

Traditional assertions don't work for agent systems. LLMs evaluating LLMs sounds circular, but:
- Tests define behavioral expectations
- Evaluation LLM judges semantic match
- Brittle string matching avoided
- Tests survive agent response variations

**Key:** Test behavior, not implementation.

### 4. Graceful Degradation

Location features are optional. If no Maps API key:
- System still works for non-location timers
- Clear error messages guide setup
- No cryptic failures

**Principle:** Every feature should degrade gracefully.

### 5. Real-World Constraints Drive Innovation

The breakthrough insight - state machine model - emerged from real constraint:
- "I need to BE somewhere at time T"
- "When do I need to START MOVING?"

Physical reality (space, time, travel) drove the abstraction, not academic CS theory.

---

## Reflection: What We Built

TimerMind is:
- ✅ A multi-agent AI system
- ✅ A task management tool
- ✅ A location-aware planning assistant
- ✅ An intelligent timer system

But more fundamentally, TimerMind is:

**A spatiotemporal reasoning engine that models daily life as a state machine.**

This paradigm shift - from task lists to state graphs - is the core innovation. Everything else (agents, APIs, scoring algorithms) is in service of this model.

**Traditional tools ask:** "What do you need to do?"

**TimerMind asks:** "Where do you need to be, and when do you need to start moving?"

That difference is everything.

---

**Last Updated:** November 17, 2025
**Current Status:** Phase 5 (Documentation & Polish)
**Next Major Feature:** Timeline modeling and conflict detection (Q1 2026)
