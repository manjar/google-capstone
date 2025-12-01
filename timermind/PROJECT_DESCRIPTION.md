# TimerMind: Spatiotemporal State Machine for Intelligent Daily Planning

**Project Status:** Alpha
**Competition:** Google Agents Intensive - Capstone Project
**Competition URL:** https://www.kaggle.com/competitions/agents-intensive-capstone-project/overview
**Last Updated:** December 1, 2025

---

## Personal Motivation

I found myself doing the same thing every day: taking calendar appointments and to-do list reminders and mentally converting them into timers. "Meeting at 3PM in Campbell" became "I need to leave in 47 minutes." "Pick up groceries" became "If I leave by 2:15, I can be back before the call."

This constant mental arithmetic—checking Google Maps, calculating buffer time, setting phone timers—was exhausting. I wanted a **timers-first concierge**: an AI assistant that understands where I need to be and when, and simply tells me when to leave. TimerMind is that assistant.

## The Problem

Traditional productivity tools force users to maintain complex mental models of three interconnected variables: what needs to be done, where it needs to happen, and when they need to leave to arrive on time. This creates significant cognitive overhead, especially for people managing multiple locations throughout their day.

Most calendar applications show "Meeting at 3PM in Campbell" without acknowledging that the user must depart 25 minutes earlier given current traffic. To-do lists ignore the spatial dimension entirely. Neither provides intelligent prioritization accounting for both urgency and importance, nor do they learn personal preferences through conversation.

---

## Overview

TimerMind is an AI-powered daily planning system that fundamentally reimagines how people manage their time and location. Rather than treating tasks as isolated to-do items, TimerMind models daily life as a **spatiotemporal state machine** where your location is the state and your schedule determines the transitions between states.

### The Core Innovation

**Traditional tools ask:** "What do you need to do?"
**TimerMind asks:** "Where do you need to be, and when do you need to start moving?"

This paradigm shift - from task lists to state graphs - enables the system to handle the spatial and temporal reasoning that users typically do manually, reducing cognitive load and preventing scheduling impossibilities.

---

## Key Features

### 1. Multi-Agent Architecture

TimerMind uses a streamlined 2-agent system powered by Google ADK:

- **Extraction Agent**: Parses user input, creates/updates/queries timers, manages task state, and coordinates with other tools
- **Preference Agent**: Learns user patterns and priorities, stores notable facts using Google ADK memory banks for cross-session persistence

This consolidated architecture replaced an initial 4-agent design, improving performance and maintainability while preserving all functionality.

### 2. Location-Aware State Modeling

The system treats your daily schedule as a state machine:

- **States (S)**: Physical locations (home, office, grocery store, etc.)
- **Transitions**: Travel between locations with real-time traffic considerations
- **Events**: Activities that either maintain or change your current state

**Example:**

```
User Input: "Meeting at 3pm at Naschmarkt in Campbell"

System Reasoning:
- Current state: home (San Jose)
- Target state: naschmarkt (Campbell)
- Required transition: home → naschmarkt
- Travel time: 25 minutes (with current traffic via Google Maps API)
- Optimal departure: 2:35 PM

System Action:
- Create timer: "Leave for Naschmarkt" at 2:35 PM
- Store travel metadata (distance, duration, destination)
- Monitor for traffic changes
```

### 3. Intelligent Prioritization

TimerMind uses a novel **buffer ratio urgency scoring** system that adapts to task complexity:

```
urgency_score = f(buffer_ratio)
buffer_ratio = time_remaining / estimated_duration

Examples:
- 1-hour task due in 30 minutes → buffer_ratio = 0.5 → CRITICAL
- 1-hour task due in 2 hours → buffer_ratio = 2.0 → MODERATE
- 1-hour task due in 10 hours → buffer_ratio = 10.0 → LOW
```

This approach naturally adapts to both short and long tasks, unlike traditional absolute-time thresholds.

**Final Priority** = urgency × 0.6 + importance × 0.4

- Time pressure (urgency) weighted more heavily for actionability
- User values (importance) influence ranking based on learned preferences

### 4. Real-Time Travel Calculations

Integration with Google Maps Platform APIs:

- **Geocoding API**: Converts addresses to coordinates
- **Distance Matrix API**: Calculates travel time with current traffic conditions
- Automatic departure time calculation based on desired arrival
- Traffic-aware route planning

### 5. Interactive Dashboard

Web-based interface featuring:

- **Chat View**: Conversational interaction with TimerMind agents
- **Thought Process View**: Transparent agent reasoning and tool calls
- **Timers List**: Priority-sorted tasks with urgency indicators and visual countdown bars
- **Timeline View**: Day-by-day schedule visualization with sticky headers (like a calendar, but smarter)

### 6. Cross-Session Memory

Powered by Google ADK memory banks:

- Stores user preferences and patterns
- Remembers default locations, category importance, and scheduling habits
- Provides contextual awareness across sessions
- Enables personalized responses and proactive suggestions

---

## Technical Stack

### Backend

- **Framework**: FastAPI (Python)
- **AI Platform**: Google ADK (Agent Development Kit)
- **LLM**: Gemini 2.5 Flash
  - Fast inference for real-time chat
  - Strong reasoning for task parsing
  - Accurate function calling
  - Cost-effective for production
- **Database**: SQLite
- **External APIs**:
  - Google Maps Geocoding API
  - Google Maps Distance Matrix API

### Frontend

- **Interface**: Web-based dashboard
- **Technology**: HTML/CSS/JavaScript
- **Design**: Responsive, two-panel layout
- **Updates**: Real-time via AJAX

### Testing

- **Approach**: LLM-based behavioral testing
- **Evaluator**: Gemini (tests behavior, not implementation)
- **Test Cases**: Expected behavior descriptions validated semantically
- **Benefits**: Resilient to response variations, tests semantic understanding

---

## Real-World Problem Solved

### The Problem

Traditional task management requires users to:

1. Maintain complex mental models of what, when, where, and how long
2. Manually calculate when to leave for appointments
3. Juggle multiple tools (calendar, to-do list, maps)
4. Constantly re-plan when situations change
5. Risk scheduling impossibilities (conflicting locations/times)

### The Solution

TimerMind:

1. **Offloads spatial reasoning** - System calculates optimal departure times
2. **Provides unified interface** - One tool for scheduling, tasks, and navigation
3. **Adapts to changes** - Updates departure times based on traffic
4. **Prevents conflicts** - (Future) Detects physically impossible schedules
5. **Learns preferences** - Adapts to user priorities and patterns

### Use Case Example

**Scenario**: "I need to pick up Willem at soccer practice at 3:15pm, then get home for dinner by 6pm"

**Traditional Approach**:

- Check calendar for 3:15pm
- Open maps to find soccer field
- Calculate drive time
- Set alarm with buffer
- Hope traffic cooperates
- Repeat for next appointment

**TimerMind Approach**:

```
User: "Pick up Willem at soccer practice at 3:15, home by 6 for dinner"

Agent:
1. Geocodes soccer field location
2. Calculates travel time from current location (22 min)
3. Creates departure timer for 2:50pm
4. Stores destination and arrival time
5. Creates second timer for dinner prep
6. Monitors traffic, updates if needed
```

---

## Project Achievements

1. **Effective Multi-Agent Design**: Streamlined architecture that balances simplicity and functionality
2. **Novel Urgency Model**: Buffer ratio scoring adapts to task complexity better than traditional methods
3. **Real-World Utility**: Solves genuine cognitive overhead in daily planning
4. **Robust Testing**: LLM-based evaluation ensures behavioral correctness
5. **Scalable Foundation**: Architecture supports future enhancements (timeline conflict detection, multi-stop optimization, etc.)

---

## Future Roadmap

### Near-Term (Q1 2026)

- **Calendar Integration**: Bidirectional sync with Google Calendar
- **Persistent Memory**: Switch to VertexAiMemoryBankService
- **Enhanced UI**: Mobile-responsive design improvements
- **User Profiles**: Multi-user support with individual preferences

### Medium-Term

- **Timeline Conflict Detection**: Identify physically impossible schedules
- **Multi-Stop Optimization**: Route planning for errands (Traveling Salesman Problem)
- **Weather Integration**: Adjust travel times for weather conditions
- **Activity Duration Learning**: Learn actual vs. estimated task durations

### Long-Term (Research)

- **Probabilistic State Modeling**: Bayesian travel time estimates with confidence intervals
- **Multi-User Coordination**: Shared calendars and family scheduling
- **Proactive Suggestions**: "You have 45 minutes free - perfect for grocery shopping"

---

## Installation & Setup

### Prerequisites

- Python 3.9+
- Google Cloud account with Maps API enabled
- Google AI Studio API key for Gemini

### Quick Start

```bash
# Clone repository
cd timermind

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
#   GOOGLE_API_KEY (Gemini)
#   GOOGLE_MAPS_API_KEY (Maps Platform)

# Run server
python main.py

# Open browser
http://localhost:8000
```

---

## Documentation

- **Development Journal**: `development_journal.md` - Detailed design decisions and evolution
- **Kaggle Competition Summary**: `kaggle_competition_summary.md` - Competition context and submission details
- **Code Documentation**: Inline comments throughout codebase
- **Test Suite**: `tests/test_harness.py` - Interactive test runner

---

## Design Philosophy

### 1. Start Simple, Validate Core Concept

We built basic location awareness first, not timeline modeling or multi-stop optimization. This validated the core concept before expanding.

### 2. Let Users Guide the Vision

The "spatiotemporal state machine" framing emerged from user feedback, not initial design docs.

### 3. Graceful Degradation

Location features are optional. Without Maps API, the system still functions for non-location timers with clear setup guidance.

### 4. Test Behavior, Not Implementation

LLM-based testing evaluates semantic correctness, making tests resilient to agent response variations.

### 5. Real-World Constraints Drive Innovation

Physical reality (space, time, travel) drove the abstraction, not academic theory.

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

- **Google ADK Team**: For the Agent Development Kit framework
- **Kaggle**: For hosting the Agents Intensive Capstone competition

---

## Contact & Contributions

For questions, suggestions, or contributions:

- GitHub: https://github.com/manjar/google-capstone
- Kaggle Competition: https://www.kaggle.com/competitions/agents-intensive-capstone-project

---

**Built with**: Google ADK, Gemini 2.5 Flash, FastAPI, Google Maps Platform

**Core Innovation**: Modeling daily life as a spatiotemporal state machine

**Mission**: Reduce cognitive overhead in daily planning by offloading spatial and temporal reasoning to AI
