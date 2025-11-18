# TimerMind Development Roadmap

## Overview

TimerMind is evolving from a traditional task management system into a **spatiotemporal state machine** - a fundamentally new paradigm for modeling daily life that accounts for location, time, and real-world constraints.

## Completed Features

### Phase 1: Core Multi-Agent Architecture ✅
**Status:** Complete
**Completion Date:** November 2025

- [x] Multi-agent system with Google ADK
- [x] Extraction agent for task parsing
- [x] Preference agent for learning user patterns
- [x] Google ADK memory banks integration
- [x] SQLite database for persistence
- [x] FastAPI web server with chat interface
- [x] Automatic urgency/importance scoring

**Key Achievement:** Reduced from 4 agents to 2 agents while maintaining full functionality through better responsibility distribution.

### Phase 2: Intelligent Prioritization ✅
**Status:** Complete
**Completion Date:** November 2025

- [x] Buffer ratio-based urgency scoring
- [x] Category-based importance scoring
- [x] Combined priority calculation (urgency × 0.6 + importance × 0.4)
- [x] Rationale generation for all scores
- [x] User preference learning (rules and patterns)
- [x] Context-aware task parsing ("between X and Y")

**Key Achievement:** System can reason about task priorities using time buffer ratios and learned user preferences.

### Phase 3: Location-Aware State Machine ✅
**Status:** Complete
**Completion Date:** November 17, 2025

- [x] Google Maps Geocoding API integration
- [x] Google Maps Distance Matrix API integration
- [x] Real-time traffic-aware travel time calculations
- [x] Departure time calculation for arrival deadlines
- [x] Default location (home address) management
- [x] Extended database schema with location fields:
  - `destination_address`
  - `origin_address`
  - `departure_time`
  - `arrival_time`
  - `travel_time_minutes`
  - `distance_km`
  - `last_travel_update`
- [x] `calculate_travel_time_tool` for extraction agent
- [x] `set_default_location_tool` for preference agent
- [x] Agent instructions updated for location awareness

**Key Achievement:** First implementation of spatiotemporal state machine - system now models user location as state and travel as state transitions.

**Example:**
```
User: "Remind me to leave for Naschmarkt in Campbell by 3pm"
System: Creates timer at 2:35pm (25 min travel time with current traffic)
```

### Phase 4: Testing Infrastructure ✅
**Status:** Complete

- [x] Interactive test harness with browser-like simulation
- [x] LLM-based test evaluation using Gemini
- [x] JSON-based test case definitions
- [x] Detailed pass/fail reporting with timestamps
- [x] Automated and interactive test modes
- [x] Google Maps API validation tests

## In Progress

### Phase 5: Documentation & Polish
**Status:** In Progress
**Target:** November 2025

- [x] Comprehensive README with quick start
- [x] API documentation
- [x] Testing documentation
- [x] Development roadmap
- [ ] Development journal with design decisions
- [ ] System specification document
- [ ] Architecture diagrams
- [ ] Code comments and docstrings review

## Near-Term Enhancements (Q1 2026)

### Enhanced Location Features
**Priority:** High
**Complexity:** Medium

- [ ] **Multi-stop Route Optimization**
  - "Go to post office, then Naschmarkt, then pick up Willem at 3pm"
  - Calculate optimal departure times for chained locations
  - Validate timeline feasibility

- [ ] **Location Timeline Visualization**
  - Show spatiotemporal state graph visually
  - Display user location over time
  - Highlight state transitions (travel events)

- [ ] **Travel Mode Selection**
  - Support driving, walking, transit, bicycling
  - Mode-specific travel time calculations
  - User preference for default travel mode

### Proactive Monitoring
**Priority:** High
**Complexity:** Medium

- [ ] **Periodic Travel Time Updates**
  - Re-check traffic conditions every 15-30 minutes
  - Update `last_travel_update` timestamp
  - Trigger alerts if departure time needs adjustment

- [ ] **Dynamic Departure Alerts**
  - "Traffic increased - leave NOW instead of 2:35pm"
  - Push notifications (requires mobile app or webhook)

## Medium-Term Vision (Q2-Q3 2026)

### Timeline Modeling & Conflict Detection
**Priority:** High
**Complexity:** High

**Concept:** Build complete spatiotemporal graph of user's day.

Features:
- [ ] **State Graph Construction**
  - Infer user location at any point in time
  - Chain multiple state transitions
  - Example: Home → Post Office → Naschmarkt → School → Home

- [ ] **Conflict Detection**
  - "You have dinner at 6:30pm at home, but meeting ends in Campbell at 6:15pm"
  - Calculate: 6:15pm + 30min travel = 6:45pm arrival
  - Alert: "Timeline impossible - you'll be 15 minutes late to dinner"

- [ ] **Automatic Rescheduling Suggestions**
  - "Move dinner to 7pm?"
  - "End meeting 15 minutes early?"
  - "Skip post office stop?"

- [ ] **Feasibility Analysis**
  - Validate entire day's schedule before committing
  - Identify impossible timelines early
  - Suggest optimal reordering

### Intelligent Optimization
**Priority:** Medium
**Complexity:** High

- [ ] **Route Optimization Across Multiple Stops**
  - Traveling Salesman Problem (TSP) solving
  - Minimize total travel time
  - Respect time windows for each location

- [ ] **Buffer Time Management**
  - Automatically add buffer between appointments
  - Learn user preferences (10 min buffer vs. back-to-back)
  - Adjust buffer based on uncertainty (traffic variability)

- [ ] **Proactive Recommendations**
  - "You're going to Campbell twice today - combine trips?"
  - "Post office closes at 5pm - go there first?"

### Context Awareness
**Priority:** Medium
**Complexity:** Medium

- [ ] **Time-of-Day Context**
  - Rush hour vs. off-peak travel times
  - Business hours for locations
  - Typical user patterns by day/time

- [ ] **Weather Integration**
  - Adjust travel time for rain/snow
  - Suggest earlier departure in bad weather
  - Alert: "Heavy rain forecast - add 10 minutes"

- [ ] **Calendar Integration**
  - Import Google Calendar events
  - Sync deadlines bidirectionally
  - Use calendar as ground truth for locations

## Long-Term Vision (2026+)

### Ambient Intelligence
**Concept:** System becomes proactive daily planning assistant.

- [ ] **Morning Briefing**
  - "Today you have 3 location transitions"
  - "Leave at 9:15am for first appointment"
  - "Post office closes at 5pm - plan accordingly"

- [ ] **Real-Time Replanning**
  - Continuous monitoring of timeline
  - Automatic adjustment to traffic/delays
  - Proactive problem-solving

- [ ] **Learning from History**
  - "You usually take 35 minutes to get ready"
  - "Traffic to Campbell is typically heavy at 8am"
  - Personalized travel time predictions

### Advanced State Machine Features

- [ ] **Probabilistic State Modeling**
  - Account for uncertainty in transitions
  - Bayesian estimates of travel time
  - Risk-aware scheduling

- [ ] **Multi-User Coordination**
  - "Pick up Willem at 3pm" → Check if Willem's schedule conflicts
  - Family-wide timeline optimization
  - Shared location tracking

- [ ] **Activity Duration Learning**
  - Learn how long tasks actually take
  - "Grocery shopping usually takes you 45 minutes"
  - Improve future estimates

### Mobile & Integration

- [ ] **Mobile App**
  - iOS/Android native apps
  - Push notifications for departures
  - GPS-based location tracking
  - Automatic check-in at locations

- [ ] **Smart Home Integration**
  - "Leaving for work in 10 minutes" → Lock doors, adjust thermostat
  - Voice assistant integration (Alexa, Google Home)

- [ ] **Wearable Support**
  - Apple Watch/Android Wear notifications
  - Haptic alerts for departures
  - Quick voice commands

## Research & Exploration

### Novel Applications of State Machine Model

- [ ] **Energy Optimization**
  - Minimize total distance traveled
  - Cluster errands by location
  - Carbon footprint tracking

- [ ] **Social Coordination**
  - Find optimal meeting locations
  - "Meet halfway" calculations
  - Group timeline optimization

- [ ] **Accessibility Features**
  - Wheelchair-accessible routes
  - Public transit for those without cars
  - Visual/audio accommodation

### Academic Contributions

- [ ] **Publish Research Paper**
  - "Spatiotemporal State Machines for Daily Planning"
  - Compare to traditional calendar/todo paradigm
  - User study on cognitive load reduction

- [ ] **Open Dataset**
  - Anonymized timeline data
  - Benchmark for planning algorithms
  - Academic community resource

## Technical Debt & Maintenance

### Code Quality
- [ ] Type hints throughout codebase
- [ ] Comprehensive unit tests (>80% coverage)
- [ ] Integration tests for multi-agent flows
- [ ] Performance profiling and optimization
- [ ] Error handling improvements

### Infrastructure
- [ ] Proper logging framework
- [ ] Monitoring and alerting
- [ ] Database migrations system
- [ ] CI/CD pipeline
- [ ] Docker containerization

### Security
- [ ] API key rotation
- [ ] Rate limiting
- [ ] Input sanitization
- [ ] HTTPS enforcement
- [ ] User authentication (if multi-user)

## Success Metrics

### User Experience
- Average time saved per day (estimated vs. traditional tools)
- Reduction in late arrivals
- User satisfaction scores
- Cognitive load reduction (via survey)

### Technical Metrics
- Agent response time (<2s for 95th percentile)
- Travel time prediction accuracy (MAPE < 15%)
- Timeline feasibility accuracy
- System uptime (>99.5%)

## Community & Adoption

- [ ] Demo video and screenshots
- [ ] Blog posts explaining spatiotemporal state machine concept
- [ ] Presentation at AI/productivity conferences
- [ ] Open source community building
- [ ] Plugin ecosystem for extensibility

---

## Philosophy

Traditional productivity tools ask: **"What do you need to do?"**

TimerMind asks: **"Where do you need to be, and when do you need to start moving?"**

This shift from task-centric to **spatiotemporal state-centric** planning represents a fundamental rethinking of how we model daily life. The roadmap above reflects our commitment to exploring this new paradigm fully.

---

**Last Updated:** November 17, 2025
**Current Phase:** Phase 5 (Documentation & Polish)
**Next Milestone:** Complete spatiotemporal specification document
