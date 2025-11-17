# TimerMind Development Roadmap

**Project:** AI-Powered Task Prioritization Agent
**Competition Deadline:** December 1, 2025, 11:59 AM PT
**Track:** Concierge Agents

---

## Phase 1: Minimal E2E Prototype ✅ COMPLETE
**Goal:** Agent extracts timer from text and logs it
**Status:** Done (Nov 17, 2025)
**Commit:** `28ee7a6` - "Phase 1 complete"

### Completed
- [x] Project structure setup
- [x] FastAPI skeleton with basic endpoints
- [x] SQLite database for timer storage
- [x] Structured JSON logging (observability)
- [x] **ADK Integration**: Real `Agent`, `Runner`, `InMemorySessionService`
- [x] Custom tool: `create_timer_tool`
- [x] Urgency scoring algorithm (time-based)
- [x] End-to-end test: natural language → timer creation

### Key Files
- `timermind/main.py` - Main application
- `timermind/data/timermind.db` - Timer storage
- `timermind/logs/*.log` - Structured event logs

---

## Phase 2: Multi-Agent & Preferences ✅ COMPLETE
**Goal:** Sub-agents with preference learning
**Status:** Done (Nov 17, 2025)
**Commit:** `5883409` - "Phase 2 complete"
**Estimated:** 3-4 days

### Completed
- [x] **Extraction Agent** (sub-agent)
  - Dedicated agent for parsing tasks
  - Tools: `create_timer_tool`, `update_timer_tool`, `get_current_timers_tool`
  - Tested with various input formats

- [x] **Preference Agent** (sub-agent)
  - Learns user preferences from conversation
  - Tools: `update_category_weight_tool`, `add_preference_rule_tool`, `get_user_preferences_tool`
  - Stores preferences in SQLite

- [x] **Root Agent Orchestration**
  - Delegates to extraction_agent, preference_agent, planning_agent
  - Uses InMemorySessionService for session continuity
  - Context-aware delegation logic

- [x] **Context Resolution Agent** (bonus)
  - Fuzzy-matches natural language references to existing timers
  - Sub-agent of planning_agent

- [x] **Planning Agent** (bonus)
  - Handles multi-step execution for complex requests
  - Executes plans to completion (not just describes)
  - Sub-agent: context_agent

- [x] **Interactive Dashboard** (bonus)
  - Chat interface with tabbed view (Chat / Thought Process)
  - Execution trace visibility (tool calls, delegations)
  - Logarithmic countdown timers with non-linear scale
  - Real-time timer management (complete/delete)

### Deferred
- [ ] **Upgrade to VertexAI Services** (deferred to post-MVP)
  - InMemorySessionService works fine for demo
  - Sessions persist during runtime
  - VertexAI services can be added later for production

### Success Criteria
- ✅ Multi-agent delegation working
- ✅ Preferences learned and stored
- ⚠️  Memory persists across sessions (runtime only, not restarts)

---

## Phase 3: Scoring & Dashboard
**Goal:** Visible prioritization with explanations
**Estimated:** 3-4 days

### Tasks
- [ ] **Importance Scoring**
  - Agent-based scoring using preferences
  - Store rationale/explanation per timer
  - Priority = urgency × importance (weighted)

- [ ] **Dashboard UI**
  - Single HTML page (Jinja2 template)
  - List timers sorted by priority score
  - Color-coded urgency indicators
  - "Why?" button for explanations

- [ ] **Chat Interface**
  - Text input box for natural language
  - Real-time timer list updates
  - Conversation history display

- [ ] **Timer Management**
  - Complete/snooze/delete actions
  - Edit timer details
  - Bulk operations

### Success Criteria
- Dashboard shows prioritized timers
- User can see why tasks are prioritized
- Chat interactions update dashboard in real-time

---

## Phase 4: Break Mode & Polish
**Goal:** Complete MVP feature set
**Estimated:** 2-3 days

### Tasks
- [ ] **Break Mode**
  - Toggle to suppress urgency display
  - "On break until HH:MM" indicator
  - Auto-resume after duration

- [ ] **Enhanced Logging & Metrics**
  - Agent invocation counts
  - Tool usage statistics
  - Scoring distribution analysis

- [ ] **Code Quality**
  - Comprehensive docstrings
  - Design decision comments
  - Error handling improvements

- [ ] **Testing**
  - Core flow tests
  - Edge case handling
  - Performance checks

### Success Criteria
- Break mode functional
- Code well-documented
- All core features stable

---

## Phase 5: Submission Prep
**Goal:** Competition-ready submission
**Estimated:** 2 days (before Dec 1)

### Tasks
- [ ] **README.md**
  - Problem statement
  - Solution overview
  - Architecture diagram
  - Setup instructions
  - Usage examples

- [ ] **Competition Writeup** (<1500 words)
  - Problem + Solution + Architecture
  - Value delivered
  - Project journey

- [ ] **YouTube Video** (<3 minutes)
  - Problem statement (30s)
  - Why agents? (30s)
  - Architecture overview (45s)
  - Live demo (60s)
  - Build process (15s)

- [ ] **Deployment Documentation** (+5 points)
  - Cloud Run setup instructions
  - Or evidence of deployment attempt

- [ ] **Thumbnail/Card Image**
  - Visual representation of TimerMind
  - Architecture diagram or UI screenshot

- [ ] **Final Submission**
  - GitHub repo public
  - Submit to Kaggle
  - Verify all requirements met

### Success Criteria
- All artifacts complete
- Submission accepted
- Targeting 85-100 points

---

## Competition Requirements Checklist

### Required Features (minimum 3) ✅
1. [x] **Multi-agent system** - Phase 2
2. [x] **Custom Tools** - Phase 1 ✅
3. [x] **Sessions & Memory** - VertexAI in Phase 2
4. [x] **Observability** - Phase 1 ✅

### Bonus Points
- [x] Gemini as LLM (+5) - Phase 1 ✅
- [ ] Deployment documentation (+5) - Phase 5
- [ ] YouTube video (+10) - Phase 5

### Submission Components
- [ ] Title & Subtitle
- [ ] Thumbnail image
- [ ] Code repository (GitHub)
- [ ] Writeup (<1500 words)
- [ ] Track: Concierge Agents

---

## Risk Mitigation

### Technical Risks
- **ADK API changes**: Pin version, document workarounds
- **VertexAI setup issues**: Have fallback to InMemory
- **Gemini rate limits**: Implement retry logic
- **Session persistence bugs**: Test extensively

### Timeline Risks
- **Scope creep**: Stick to MVP, defer nice-to-haves
- **Debugging delays**: Good logging from start (done ✅)
- **Video production**: Script and practice early
- **Submission issues**: Test submission process early

---

## Current Status

**Phase 1:** ✅ COMPLETE
**Next:** Phase 2 - Multi-Agent & Preferences
**Days Remaining:** 14 days until deadline

---

## Quick Start (Current State)

```bash
cd timermind
source venv/bin/activate
python main.py
```

Test:
```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I need to submit my report by Friday"}'
```

View logs:
```bash
tail -f logs/timermind_*.log
```
