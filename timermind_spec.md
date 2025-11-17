# TimerMind Capstone Project Specification

## 1. Product Overview

**Working name:** TimerMind  
**Goal:** Turn all “due-ish” things in a user’s life into prioritized timers, ranked by urgency (time pressure) and importance (meaning), with a special break mode (“down timer”) that suppresses urgency temporarily.

**Core idea:**  
- Ingest items written by the user (and later from calendar/email).  
- Use Claude to extract structure, infer deadlines, durations, and categories.  
- Maintain preferences learned conversationally.  
- Display everything on a simple timer board UI.

---

## 2. User Stories

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

## 3. Architecture

### Components
- **Frontend:** Lightweight HTML (Jinja templates), minimal JS.
- **Backend:** Python (FastAPI or Flask).
- **LLM:** Claude API.
- **Storage:** SQLite.
- **Deployment:** Local development; optional deployment to Render or Cloud Run.

### Subsystems
1. **Timer Engine** – scoring, CRUD.
2. **Preference Manager** – rules + weights.
3. **Claude Layer** – extraction, scoring, chat processing.
4. **Web UI** – dashboard + chat panel.

---

## 4. Data Model

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

## 5. API Design

### Timer Endpoints

**GET `/api/timers`**  
Return all timers.

**POST `/api/timers`**  
Body: `{ "text": "<freeform user input>" }`  
Action: Call Claude to extract structured timers and save them.

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
- Sends the user's message + current timers + preferences to Claude.  
- Returns:
```json
{
  "assistant_text": "...",
  "timers": [...]
}
```

---

## 6. Claude Prompt Specs

### Extraction Prompt
Extract timers from text.

Schema:
```json
{
  "timers": [
    {
      "label": "...",
      "description": "...",
      "deadline_iso": "... or null",
      "window_start_iso": "... or null",
      "window_end_iso": "... or null",
      "estimated_duration_minutes": 60,
      "category": "work|personal|health|finance|maintenance|other",
      "tags": ["..."]
    }
  ]
}
```

### Importance Scoring Prompt
Input: timer object + preferences.  
Output:
```json
{
  "importance": 1-5,
  "rationale": "..."
}
```

### Chat Processing Prompt
Output schema:
```json
{
  "assistant_text": "...",
  "preference_updates": {
    "priority_weights": { ... },
    "time_prefs": { ... },
    "rules_add": [ ... ],
    "rules_remove_ids": [ ... ]
  }
}
```

---

## 7. UI Spec

### Main Dashboard
- List of timers sorted by priority.
- Show: label, time remaining, category, priority color.
- Actions: complete, snooze, edit.
- Break mode: large “On break until HH:MM” card.

### Chat Panel
- Textbox + submit.
- Shows assistant responses.
- Updates timer list on reply.

---

## 8. MVP vs Stretch Goals

### MVP
- Manual text input → timer extraction.
- Timer board with sorting.
- Basic urgency + importance scoring.
- Break mode.
- Chat for basic preference tweaking.

### Stretch
- External source ingestion (simple calendar).
- Pattern detection.
- Advanced rule system.
- Enhanced UI.

---

## 9. Implementation Plan

### Phase 1
- Backend skeleton + fake timers.
- Basic priority scoring.

### Phase 2
- Timer extraction via Claude.

### Phase 3
- Chat endpoint + preference updates.

### Phase 4
- Break mode.

### Phase 5 (optional)
- External sources + recurring pattern suggestions.

---
