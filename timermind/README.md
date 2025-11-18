# TimerMind

**A Spatiotemporal State Machine for Intelligent Task Management**

TimerMind is a novel approach to daily planning that models your day as a location-aware state machine rather than a traditional calendar or to-do list. It intelligently calculates when you need to transition between locations, accounting for real-time traffic and spatial constraints.

## What Makes TimerMind Different

Traditional productivity tools force users to maintain a mental model of:
- What tasks need to be done
- Where they need to be
- When they need to leave to arrive on time

TimerMind fundamentally changes this by treating **location as state** and using AI agents to:
- Calculate optimal state transitions (when to leave)
- Account for real-world constraints (traffic, distance, time-of-day)
- Proactively alert you before transitions are needed
- Build a spatiotemporal graph of your day

**Example:**
- **Traditional**: "Meeting at 3pm in Campbell" → You calculate when to leave
- **TimerMind**: "Meeting at 3pm in Campbell" → System creates timer at 2:35pm (25 min travel + current traffic)

## Quick Start

### Prerequisites

- Python 3.12+
- Google Gemini API key
- Google Maps API key (for location features)

### Installation

```bash
# Clone the repository
cd timermind

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env and add your API keys:
# GEMINI_API_KEY=your_key_here
# GOOGLE_MAPS_API_KEY=your_key_here
```

### Enable Google Maps APIs

In Google Cloud Console, enable:
1. **Geocoding API** - Address to coordinates conversion
2. **Distance Matrix API** - Travel time calculations with traffic

### Run the Server

```bash
python main.py
```

Access the dashboard at: `http://127.0.0.1:8000`

### Example Usage

Try these messages:

```
"I need to have dinner ready by 6:30"
→ Creates timer with urgency based on time remaining

"Remind me to leave for Naschmarkt in Campbell by 3pm"
→ Calculates travel time with traffic, creates departure reminder

"Between getting the mail and picking up Willem, I need lunch"
→ Analyzes existing timers, schedules lunch at optimal time

"My home address is 123 Main St, San Jose, CA"
→ Saves default location for future travel calculations
```

## Project Documentation

### [SPEC.md](./SPEC.md)
Complete system specification including:
- Architecture and design decisions
- Multi-agent system design
- Location-aware state machine model
- API contracts and data models
- Appendix on spatiotemporal planning

### [ROADMAP.md](./ROADMAP.md)
Development roadmap and feature planning:
- Completed features
- In-progress work
- Future enhancements (timeline modeling, conflict detection, dynamic re-optimization)

### [development_journal.md](./development_journal.md)
Detailed development log with:
- Design decisions and rationale
- Implementation challenges and solutions
- Architecture evolution
- Insights on the state machine paradigm

### [tests/README.md](./tests/README.md)
Interactive testing harness documentation:
- Test case definitions
- LLM-based evaluation
- Running tests in interactive or automated mode

## Technology Stack

### AI/ML Platform
- **Google Gemini (gemini-2.5-flash)** - Multi-agent orchestration and natural language understanding
- **Google ADK (Agent Development Kit)** - Agent framework and memory management
- **Google Vertex AI** - Cloud AI platform integration

### Location Services
- **Google Maps Geocoding API** - Address to coordinates conversion
- **Google Maps Distance Matrix API** - Travel time calculation with real-time traffic data

### Backend
- **FastAPI** - Web framework
- **SQLite** - Local database for timers and preferences
- **Uvicorn** - ASGI server

### Frontend
- **Jinja2** - Template engine for web interface
- **Native JavaScript** - Interactive chat interface

### Key Dependencies
- `google-generativeai` - Gemini API client
- `google-adk` - Agent Development Kit
- `python-dateutil` - ISO 8601 datetime parsing
- `requests` - HTTP client for Maps API
- `python-dotenv` - Environment configuration

## Architecture Overview

### Multi-Agent System

TimerMind uses a **two-agent architecture** optimized for efficiency:

1. **extraction_agent** (Gemini 2.5 Flash)
   - Parses natural language input
   - Creates, updates, and queries timers
   - Calculates travel times for location-based tasks
   - Manages task state transitions

2. **preference_agent** (Gemini 2.5 Flash)
   - Learns user preferences and patterns
   - Stores notable facts using Google ADK memory banks
   - Manages preference rules
   - Saves default locations

### Spatiotemporal State Machine

The core innovation is modeling daily life as a state machine:

**States**: User locations (home, office, store, etc.)

**Transitions**: Travel events that move between states

**Timers**: Scheduled state transitions with look-ahead

**Agent Role**: Intelligent planner that:
- Infers the state graph from user input
- Calculates optimal transition times
- Accounts for real-world constraints (traffic, distance)
- Provides proactive notifications

See [SPEC.md Appendix A](./SPEC.md#appendix-a-spatiotemporal-state-machine-model) for detailed analysis.

## Testing

TimerMind includes a comprehensive testing harness with LLM-based evaluation:

### Interactive Test Mode
```bash
cd tests
python test_harness.py
```

Features:
- Browser-like interaction simulation
- Step-by-step execution with pauses for review
- Gemini-based response evaluation
- Detailed pass/fail reporting
- JSON-based test case definitions

### Automated Test Mode
```bash
python test_harness.py --auto
```

### Run Specific Test
```bash
python test_harness.py --test-id test_001_dinner_by_630
```

### Google Maps API Test
```bash
python test_maps_api.py
```

See [tests/README.md](./tests/README.md) for comprehensive testing documentation.

## Database Schema

### timers table
Stores all timer/task data with location awareness:
- Core fields: `label`, `description`, `deadline`, `category`
- Scoring: `urgency_score`, `importance_score`, `priority_score`, `rationale`
- Location fields: `destination_address`, `origin_address`, `departure_time`, `arrival_time`, `travel_time_minutes`, `distance_km`
- Metadata: `created_at`, `updated_at`, `status`

### preferences table
Key-value store for user preferences:
- Preference rules
- Default location
- Notable facts (via Google ADK memory)

## API Endpoints

### POST /api/chat
Send message to TimerMind
```json
{
  "message": "I need to leave for Campbell by 3pm"
}
```

### GET /api/timers
Retrieve all active timers

### POST /api/reset
Clear all timers and preferences (for testing)

### GET /api/preferences
Get user preferences and weights

See [SPEC.md](./SPEC.md) for complete API documentation.

## Development

### Project Structure
```
timermind/
├── main.py                 # Main application and agent definitions
├── services/
│   └── google_maps_service.py  # Maps API integration
├── tests/
│   ├── test_harness.py     # Interactive test runner
│   ├── test_cases.json     # Test definitions
│   └── README.md           # Testing documentation
├── templates/
│   └── index.html          # Web interface
├── data/
│   └── timermind.db        # SQLite database
└── logs/                   # Application logs
```

### Running Tests
```bash
# Interactive mode (with pauses)
cd tests && python test_harness.py

# Automated mode
python test_harness.py --auto

# Specific test
python test_harness.py --test-id test_009_fuzzy_reference_update

# Google Maps API test
python ../test_maps_api.py
```

## Future Enhancements

See [ROADMAP.md](./ROADMAP.md) for detailed roadmap, including:

### Timeline Modeling
Chain multiple locations with optimal scheduling:
```
"I need to go to the post office, then Naschmarkt, then pick up Willem at 3pm"
→ Creates three optimally-timed transitions
```

### Conflict Detection
```
"You have dinner at 6:30pm at home, but a meeting in Campbell until 6:15pm"
→ "This timeline is impossible - 30 min travel time"
```

### Dynamic Re-optimization
```
Traffic increases 20 minutes
→ "Leave NOW instead of 2:35pm to make your 3pm meeting"
```

## Contributing

This project is part of a Google Capstone project exploring multi-agent AI systems for task management.

## License

[Add License Information]

## Acknowledgments

- Google Gemini and Agent Development Kit teams
- Google Maps Platform
- FastAPI community
