# TimerMind: AI-Powered Spatiotemporal Task Management

## Personal Motivation

I found myself doing the same thing every day: taking calendar appointments and to-do list reminders and mentally converting them into timers. "Meeting at 3PM in Campbell" became "I need to leave in 47 minutes." "Pick up groceries" became "If I leave by 2:15, I can be back before the call."

This constant mental arithmetic—checking Google Maps, calculating buffer time, setting phone timers—was exhausting. I wanted a **timers-first concierge**: an AI assistant that understands where I need to be and when, and simply tells me when to leave. TimerMind is that assistant.

## The Problem

Traditional productivity tools force users to maintain complex mental models of three interconnected variables: what needs to be done, where it needs to happen, and when they need to leave to arrive on time. This creates significant cognitive overhead, especially for people managing multiple locations throughout their day.

Most calendar applications show "Meeting at 3PM in Campbell" without acknowledging that the user must depart 25 minutes earlier given current traffic. To-do lists ignore the spatial dimension entirely. Neither provides intelligent prioritization accounting for both urgency and importance, nor do they learn personal preferences through conversation.

## The Solution: Location as State

TimerMind introduces a novel paradigm: **the spatiotemporal state machine**. Rather than viewing tasks as abstract list items, the system models the user's day as discrete location states connected by travel transitions. When a user says "I need to be at Naschmarkt by 3PM," TimerMind:

1. Recognizes this as a state transition constraint
2. Queries Google Maps to calculate travel time with real-time traffic
3. Backward-calculates the optimal departure time
4. Creates a departure reminder at that calculated time

This transforms the mental load from "When do I need to leave?" to simply "I got a notification—time to leave now."

## Course Concepts Demonstrated

### Multi-Agent System (Sequential & Parallel Agents)

TimerMind employs a sophisticated multi-agent architecture built on Google's Agent Development Kit (ADK):

- **Orchestrator Agent** — The root agent that understands user intent and delegates to specialized sub-agents while maintaining conversation context
- **Planner Agent** — Handles complex multi-task workflows with a continuous questioning protocol that ensures nothing is forgotten
- **Location Agent** — Detects spatial references and queries Google Maps APIs for traffic-aware travel calculations
- **Context Agent** — Examines existing timers to prevent redundant questions
- **QA Agent** — Validates task completion and identifies scheduling conflicts
- **Preference Agent** — Learns user priorities through natural conversation

Agents operate both sequentially (orchestrator → planner → location) and in parallel (context + QA validation). The planner agent also implements **loop behavior**, continuously checking for pending tasks until all user requests are fulfilled.

### Custom Tools

Each agent has access to specialized tools:

- **Google Maps Geocoding Tool** — Resolves addresses and place names to coordinates
- **Google Maps Distance Matrix Tool** — Calculates travel time with real-time traffic predictions for specific departure times
- **Timer CRUD Tools** — Create, read, update, and delete timers with full spatiotemporal metadata
- **Preference Tools** — Store and retrieve user preferences and scheduling rules

### Sessions & Memory

- **InMemorySessionService** — Maintains conversation state across turns, enabling multi-step task planning
- **Memory Bank** — Persists learned preferences (category importance weights, scheduling rules like "hide work tasks on weekends") across sessions
- **SQLite Persistence** — Stores timers and preferences durably between application restarts

### Observability: Logging

Structured logging captures the complete agent workflow:
- Agent invocation and reasoning steps
- Tool calls with parameters and return values
- Timer creation and scoring decisions
- Session state transitions

The dashboard includes a "Thought Process" tab exposing all agent interactions, making the system's reasoning transparent to users.

## Key Features

**Intelligent Travel Time Calculation** — Real-time traffic integration means a 3PM appointment might require departing at 2:35PM now, but 2:20PM during rush hour.

**Multi-Task Workflow Management** — "Go to post office, then grocery store, then pick up Willem at 3PM" calculates all intermediate travel times automatically.

**Smart Prioritization** — Timers scored on urgency (time pressure relative to duration) and importance (category-based, preference-adjusted). Combined formula: `(urgency × 0.6) + (importance × 0.4)`.

**Conversational Learning** — Saying "I care more about exercise" adjusts health task weighting. No settings menus required.

## Technical Stack

| Layer | Technology |
|-------|------------|
| AI/ML | Google Gemini 2.5 Flash, Google ADK |
| Location | Google Maps Geocoding & Distance Matrix APIs |
| Backend | FastAPI, SQLite, Jinja2 |
| Frontend | HTML5/CSS3/JavaScript with real-time updates |

## Roadmap

The spatiotemporal state machine model enables advanced features:

- **Google Calendar Integration** — Automatically import events and create departure timers for appointments with locations
- **Google Tasks Sync** — Pull to-dos from Google Tasks and enrich them with location-aware scheduling
- **Conflict Detection** — "Your 5PM meeting ends too late for your 5:30PM reservation across town"
- **Route Optimization** — Multiple stops solved via traveling salesman algorithms
- **Dynamic Re-optimization** — Traffic spike detected mid-day triggers recalculated departure times
- **Probabilistic Guarantees** — "Depart at 2:20PM for 95% arrival confidence"

## Conclusion

TimerMind demonstrates that the "agents for daily life" paradigm can address genuine pain points in personal productivity. By treating location as first-class state and coordinating multiple specialized AI agents, it offloads significant cognitive burden from users. The integration of real-world traffic data ensures recommendations reflect reality, not assumptions.

The project applies **multi-agent orchestration**, **custom tools**, **sessions and memory**, and **observability logging**—showing how these concepts combine to create practical, user-facing AI applications that make complex coordination feel effortless.
