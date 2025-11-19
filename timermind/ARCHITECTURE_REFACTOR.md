# TimerMind Architecture Refactor Design Document

**Date:** 2025-11-18
**Status:** DRAFT - For Review
**Author:** System Design

---

## Executive Summary

This document proposes a significant architectural refactor to improve reliability, consistency, and quality validation in TimerMind's multi-agent system.

**Key Changes:**
1. Route all timer operations through planner (consistent task tracking)
2. Standardize task specialist response format (structured feedback)
3. Add QA agent for completion validation (quality assurance)

**Expected Benefits:**
- Catch missed tasks automatically (e.g., "grocery store timer" issue)
- Consistent user experience (all requests follow same flow)
- Better error handling and feedback loops
- Quality validation before marking work complete

---

## Current Architecture

```
┌─────────────┐
│    User     │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│  Orchestrator    │ (Routes based on message type)
└────┬─────┬───────┘
     │     │
     │     ├─────────────┐
     │     │             │
     ▼     ▼             ▼
┌─────────────┐  ┌──────────────┐  ┌────────────┐
│   Planner   │  │ Task Parser  │  │  Location  │
│ (Multi-task)│  │ (Single task)│  │  (Places)  │
└─────┬───────┘  └──────────────┘  └────────────┘
      │
      ├──────────────┬───────────────┐
      ▼              ▼               ▼
┌──────────────┐  ┌────────────┐  ┌────────────┐
│ Task Parser  │  │  Location  │  │ Preference │
└──────────────┘  └────────────┘  └────────────┘
```

**Issues:**
- Inconsistent paths (multi-task vs single-task)
- No validation that all tasks were completed
- Specialists don't report back structured status
- Missing tasks can slip through (grocery store issue)

---

## Proposed Architecture

```
┌─────────────┐
│    User     │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│  Orchestrator    │ (Lightweight router)
└────┬─────────────┘
     │
     │  ┌─────────────────────────────────┐
     │  │ Always route timer operations   │
     │  │ to planner (even single tasks)  │
     │  └─────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────┐
│              Planner Agent                   │
│  - Creates task list (even for 1 task)      │
│  - Iteratively processes each task          │
│  - Receives structured responses            │
│  - Updates task status based on feedback    │
└────┬─────────────────────────────┬───────────┘
     │                             │
     │  Delegates to specialists   │
     │  (one at a time)            │
     │                             │
     ▼                             ▼
┌──────────────┐  ┌────────────┐  ┌────────────┐
│ Task Parser  │  │  Location  │  │ Preference │
│              │  │            │  │            │
│ Returns:     │  │ Returns:   │  │ Returns:   │
│ - success    │  │ - success  │  │ - success  │
│ - needs_info │  │ - timer_id │  │ - updated  │
│ - actions    │  │ - needs_   │  │ - needs_   │
│              │  │   info     │  │   info     │
└──────┬───────┘  └─────┬──────┘  └─────┬──────┘
       │                │               │
       └────────────────┴───────────────┘
                        │
                        │ All tasks marked complete
                        ▼
              ┌──────────────────┐
              │    QA Agent      │
              │                  │
              │ Validates:       │
              │ - Original input │
              │ - Actions taken  │
              │ - Completeness   │
              └────────┬─────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Final Response │
              └─────────────────┘
```

---

## Component Changes

### 1. Orchestrator (orchestrator.py)

**Current Role:** Complex routing logic based on message analysis

**New Role:** Lightweight router with simplified logic

```python
# Simplified delegation logic
def should_route_to_planner(message):
    """
    Route to planner if message involves:
    - Creating/updating/deleting timers
    - Multiple tasks
    - Task management

    Route directly for:
    - Pure queries ("What are my timers?")
    - Health checks
    - Status requests
    """
    pass
```

**Changes:**
- Simplify delegation logic (remove multi-task vs single-task distinction)
- Default: timer operations → planner
- Exceptions: pure queries → handle directly with get_current_timers_tool

**Benefits:**
- Less complex routing logic
- Consistent user experience
- Easier to maintain

---

### 2. Planner Agent (planner_agent.py)

**Current Role:** Handle multi-task workflows only

**New Role:** Handle ALL timer operations (even single tasks)

**New Capabilities:**

```python
# Example: Single task flow
User: "Remind me to call Mom at 3pm"

Planner:
1. Creates task list with 1 item:
   [{"id": 1, "label": "Call Mom", "deadline": "3pm", "status": "pending"}]

2. Evaluates task 1:
   - Has all info (time = 3pm) → READY

3. Delegates to task_parser_agent:
   message = "Create timer: Call Mom at 3pm"

4. Receives response:
   {
     "success": True,
     "completed": True,
     "actions_taken": [
       {"type": "timer_created", "id": 123, "label": "Call Mom", ...}
     ],
     "message": "Created timer for Call Mom at 3PM"
   }

5. Updates task status: completed

6. All tasks complete → delegate to QA agent
```

**Changes:**
- Accept single-task requests (create task list with 1 item)
- Process structured responses from specialists
- Update task status based on specialist feedback
- After all tasks complete → call QA agent for validation

---

### 3. Task Specialists (task_parser, location, preference)

**Current Response:** Conversational text response

**New Response:** Structured JSON + user message

```python
# Standard response format for ALL specialists
{
  "success": bool,           # Did operation succeed technically?
  "completed": bool,         # Is user's task fully complete?
  "needs_info": {            # If needs more information
    "missing_fields": [...], # What's missing
    "question": str          # What to ask user
  },
  "actions_taken": [         # What was created/updated
    {
      "type": "timer_created|timer_updated|preference_set",
      "id": int,
      "details": {...}
    }
  ],
  "message": str             # User-facing response
}

# Field Definitions:
# - success: Technical execution (did agent run without errors?)
#   - True: Agent executed successfully, no exceptions/errors
#   - False: Technical failure (database error, API failure, parse error)
#
# - completed: Task fulfillment (is user's request satisfied?)
#   - True: Task is done (timer created, all requirements met)
#   - False: Task not done (needs more info, waiting for user)
#
# Possible combinations:
# 1. success=True, completed=True: Perfect - agent ran, task done
# 2. success=True, completed=False: Needs info - agent ran, but missing data
# 3. success=False, completed=False: Error - agent failed to execute
# 4. success=False, completed=True: Impossible - can't complete if failed
```

**Examples:**

**Success case:**
```python
# Task Parser creates timer successfully
{
  "success": True,
  "completed": True,
  "actions_taken": [
    {
      "type": "timer_created",
      "id": 123,
      "label": "Call Mom",
      "deadline": "2025-11-19T15:00:00"
    }
  ],
  "message": "I've set a reminder to call Mom at 3 PM tomorrow."
}
```

**Needs info case:**
```python
# Task Parser can't create timer without time
{
  "success": False,
  "completed": False,
  "needs_info": {
    "missing_fields": ["deadline"],
    "question": "What time would you like to go to the grocery store?"
  },
  "message": "I need to know what time you want to go to the grocery store."
}
```

**Changes Required:**
- Update each specialist to return structured format
- Include detailed actions_taken for QA validation
- Clear indication of completion status
- Specific fields for missing information

---

### 4. QA Agent (NEW - qa_agent.py)

**Purpose:** Validate that planner completed all user requests correctly throughout the project

**What is a "Project"?**
A project is the full conversation thread associated with a task list:
- Starts when task list is created
- Includes all user messages and clarifications (e.g., "museum tomorrow" → "science museum, afternoon")
- Continues through task completion and follow-up questions
- Ends when all tasks are completed or user explicitly cancels

**When invoked:**
- **Incrementally:** After each task completion (catch issues early)
- **On-demand:** When planner wants to check progress mid-project
- **Final validation:** Before marking entire project complete

**Access to:**
- **Full conversation history** for this project (all user messages + agent responses)
- Task list with all tasks and their statuses
- List of all actions taken (timers created/updated)
- Current state of timers

**Validation Logic:**

```python
class QAAgent:
    def validate_completion(self, context):
        """
        Validate that work is complete and correct.

        Args:
            context: {
                "conversation_history": [
                    {"role": "user", "message": "I want to go to the museum tomorrow"},
                    {"role": "assistant", "message": "Which museum?"},
                    {"role": "user", "message": "The science museum, in the afternoon"},
                    ...
                ],
                "task_list": [...],
                "actions_taken": [...],
                "current_timers": [...],
                "validation_mode": "incremental|final"  # New: type of validation
            }

        Returns:
            {
                "validated": bool,
                "issues": [...],
                "recommendations": [...],
                "should_continue": bool  # Can we proceed or need to stop?
            }
        """

        # 1. Extract tasks from FULL conversation history (not just first message)
        # User requirements may evolve through clarifications
        expected_tasks = self.extract_tasks_from_conversation(
            context["conversation_history"]
        )

        # 2. Check task list completeness
        task_list = context["task_list"]

        # Are all expected tasks in the list?
        for expected in expected_tasks:
            if not self.find_matching_task(expected, task_list):
                issues.append(f"Missing task: {expected}")

        # 3. Validate all tasks marked complete (for final validation)
        if context["validation_mode"] == "final":
            incomplete = [t for t in task_list if t["status"] != "completed"]
            if incomplete:
                issues.append(f"Incomplete tasks: {incomplete}")

        # 4. Validate actions taken
        actions = context["actions_taken"]

        # Do we have the right number of timers?
        timer_actions = [a for a in actions if a["type"] == "timer_created"]

        # For final validation, count should match
        if context["validation_mode"] == "final":
            if len(timer_actions) != len(expected_tasks):
                issues.append(
                    f"Expected {len(expected_tasks)} timers, "
                    f"but created {len(timer_actions)}"
                )

        # 5. Cross-reference with actual timers
        current_timers = context["current_timers"]
        for expected in expected_tasks:
            if not self.find_matching_timer(expected, current_timers):
                issues.append(f"No timer found for: {expected}")

        # 6. Check for inconsistencies or drift from requirements
        # Compare latest user clarifications with actions taken
        drift_issues = self.check_for_requirement_drift(
            context["conversation_history"],
            context["actions_taken"]
        )
        issues.extend(drift_issues)

        return {
            "validated": len(issues) == 0,
            "issues": issues,
            "recommendations": self.generate_recommendations(issues),
            "should_continue": len(issues) == 0 or context["validation_mode"] == "incremental"
        }
```

**Agent Definition:**

```python
from google.adk.agents import Agent

qa_agent = Agent(
    name="qa_agent",
    model="gemini-2.5-flash",
    description="Validates task completion and identifies missed requirements throughout the project",
    instruction="""
    You are the Quality Assurance Agent. Your job is to verify that all user
    requests have been fulfilled correctly throughout the entire project conversation.

    You will receive:
    1. **Full conversation history** (all user messages and agent responses for this project)
    2. Task list with completion status
    3. List of actions taken (timers created/updated)
    4. Current state of all timers
    5. Validation mode (incremental or final)

    Your responsibilities:
    1. Extract all tasks/requests from the ENTIRE conversation (not just first message)
       - User requirements may evolve: "museum tomorrow" → "science museum, afternoon"
       - Track clarifications and updates throughout the conversation
    2. Verify each request has a corresponding task in the task list
    3. Verify each completed task has corresponding action
    4. Cross-check actions against actual timer state
    5. Check for requirement drift (actions don't match latest user clarifications)
    6. Identify any discrepancies or missing items

    **Incremental Validation** (during project):
    - Check if we're on the right track
    - Catch issues early (missing tasks, wrong details)
    - Allow continuation if minor issues (report and move on)

    **Final Validation** (before completion):
    - Strict check: ALL tasks must be completed
    - ALL requirements from conversation must be met
    - Block completion if any issues found

    If validation passes: approve to continue/complete
    If validation fails: report specific issues and what's missing

    Example issues to catch:
    - "User asked for 3 tasks but only 1 timer was created"
    - "User mentioned 'grocery store' but no grocery timer exists"
    - "Task marked complete but no action was taken"
    - "Timer created for 3pm but user later said 5pm"
    - "User said 'science museum' but timer says 'museum' (missing specificity)"
    """,
    tools=[get_current_timers_tool]
)
```

---

## Migration Strategy

### Phase 1: Add QA Agent (No Breaking Changes)

1. Create `qa_agent.py` with QA agent definition
2. Add QA agent as sub-agent to planner
3. Planner calls QA agent AFTER marking all tasks complete
4. QA agent reports validation results
5. If validation fails, planner asks follow-up questions

**Testing:** QA agent catches existing issues

### Phase 2: Standardize Specialist Responses

1. Update task_parser_agent to return structured responses
2. Update location_agent to return structured responses
3. Update preference_agent to return structured responses
4. Planner parses structured responses
5. Backwards compatibility: handle both old and new formats

**Testing:** Verify specialists return correct format

### Phase 3: Route All Timer Operations Through Planner

1. Update orchestrator delegation logic
2. Planner handles single-task requests
3. Create task list with 1 item for single tasks
4. Process normally through specialist → QA flow

**Testing:** Single-task and multi-task requests work identically

### Phase 4: Cleanup

1. Remove old response parsing logic
2. Remove orchestrator multi-task detection
3. Simplify planner instructions
4. Update documentation

---

## Testing Strategy

### Test Cases

**1. Single Task - Complete Info**
```
Input: "Remind me to call Mom at 3pm tomorrow"
Expected:
- Task list: 1 item
- Timer created: "Call Mom" at 3pm
- QA validates: ✓
- Response: Confirmation message
```

**2. Single Task - Missing Info**
```
Input: "Remind me to buy groceries"
Expected:
- Task list: 1 item (pending)
- No timer created yet
- QA detects: needs time
- Response: "What time do you want to go?"
```

**3. Multi-Task - All Complete Info**
```
Input: "Tomorrow: groceries at 10am, dentist at 2pm, gym at 5pm"
Expected:
- Task list: 3 items
- Timers created: 3
- QA validates: ✓
- Response: Confirmation of all 3
```

**4. Multi-Task - Partial Info (REGRESSION TEST)**
```
Input: "Tomorrow: groceries, appointment in Los Altos, movie at 5:30pm"
Expected:
- Task list: 3 items
- Timer created: movie (ready)
- Tasks pending: groceries, appointment (need time)
- QA detects: 2 tasks incomplete
- Response: "Created movie timer. What time for groceries?"
```

**5. Multi-Task - QA Catches Missing Task**
```
Scenario: Planner marks all tasks complete but missed one
Expected:
- QA compares original message to actions
- QA detects: "grocery store mentioned but no timer"
- QA reports: validation failed
- Planner asks: "What time for grocery store?"
```

---

## Trade-offs and Considerations

### Pros

**Reliability:**
- QA agent catches missed tasks automatically
- Consistent validation before completion

**Consistency:**
- All requests follow same flow
- Predictable user experience

**Maintainability:**
- Structured responses easier to debug
- Clear separation of concerns
- Each agent has one responsibility

**Quality:**
- Automated validation catches errors
- Better error messages
- Clearer feedback loops

### Cons

**Performance:**
- Extra overhead for simple tasks
- Additional LLM call for QA validation
- Slightly slower response times

**Mitigation:**
- Use faster model (gemini-2.0-flash) for QA
- QA validation is quick (comparison task)
- Overall time impact: ~0.5-1 second

**Complexity:**
- More code to maintain
- Structured response format must be consistent
- More moving parts

**Mitigation:**
- Clear documentation
- Comprehensive tests
- Gradual migration (4 phases)

**Cost:**
- Additional LLM call per request (QA agent)

**Mitigation:**
- Use cheapest/fastest model for QA
- QA validation is simple task
- Cost increase: minimal

---

## Implementation Checklist

### Phase 1: QA Agent
- [ ] Create `agents/qa_agent.py`
- [ ] Define QA agent with validation logic
- [ ] Add as sub-agent to planner
- [ ] Planner calls QA after completion
- [ ] Test: QA catches missing grocery store timer
- [ ] Test: QA approves complete work

### Phase 2: Structured Responses
- [ ] Update `task_parser_agent.py` response format
- [ ] Update `location_agent.py` response format
- [ ] Update `preference_agent.py` response format
- [ ] Planner parses structured responses
- [ ] Test: Each specialist returns correct format
- [ ] Test: Planner handles needs_info correctly

### Phase 3: Route Through Planner
- [ ] Update orchestrator delegation logic
- [ ] Planner accepts single-task requests
- [ ] Create task list with 1 item for single tasks
- [ ] Test: "Call Mom at 3pm" works
- [ ] Test: "Show my timers" still works (direct)

### Phase 4: Cleanup & Polish
- [ ] Remove old response parsing
- [ ] Simplify orchestrator
- [ ] Update documentation
- [ ] Final integration tests
- [ ] Performance benchmarks

---

## Success Metrics

**Quality:**
- QA agent catches 100% of missing tasks in test suite
- Zero "forgotten task" bugs after deployment

**Consistency:**
- Single-task and multi-task requests have same flow
- Structured responses from all specialists

**Reliability:**
- All test cases pass
- No regressions in existing functionality

**Performance:**
- Response time increase < 1 second
- Cost increase < 10%

---

## Open Questions

1. **Should QA agent have write access to fix issues?**
   - Pro: Can auto-fix simple issues
   - Con: More complex, harder to debug
   - **Recommendation:** No - QA should only validate, planner fixes

2. **Should we validate in real-time or at end?**
   - Incremental: Validate after each task completion (catch issues early)
   - Final: Validate only after all tasks complete (simpler but misses mid-project drift)
   - **Recommendation:** Both - incremental validation during project + final validation before completion
   - Incremental catches issues early (prevents going off track)
   - Final ensures complete project validation before marking done

3. **How should QA agent extract expected tasks from conversation?**
   - NLP parsing of full conversation history (not just original message)
   - Track evolving requirements through clarifications
   - Compare to task list
   - **Recommendation:** Use LLM's language understanding + conversation analysis + count matching

4. **Should preference updates go through planner?**
   - Current: Direct to preference_agent
   - Proposed: Through planner for consistency
   - **Recommendation:** Yes - consistency trumps slight overhead

---

## Appendix: Example Flow

**User Input:**
```
"Tomorrow I need to go to the grocery store. I also have to go to a
1 hr appointment in Los altos. Then I'm meeting a friend in Fremont
for a movie at 5:30PM."
```

**Step 1: Orchestrator Routes to Planner**
```
Orchestrator detects: timer operations
Routes to: planner_agent
```

**Step 2: Planner Creates Task List**
```python
task_list = [
  {"id": 1, "label": "Grocery store", "status": "pending"},
  {"id": 2, "label": "Los Altos appointment", "duration": "1hr", "status": "pending"},
  {"id": 3, "label": "Fremont movie", "deadline": "5:30PM", "status": "pending"}
]
```

**Step 3: Planner Evaluates Tasks**
```
Task 1: Missing time → mark pending
Task 2: Missing time → mark pending
Task 3: Has time (5:30PM) → READY
```

**Step 4: Planner Processes Ready Tasks**
```
Delegate Task 3 to location_agent:
  "Create timer for movie in Fremont at 5:30PM tomorrow"

Receive response:
{
  "success": True,
  "completed": True,
  "actions_taken": [
    {"type": "timer_created", "id": 123, "label": "Leave for movie", ...}
  ],
  "message": "I've created a timer to leave for the movie in Fremont..."
}

Update task 3: status = "completed"
```

**Step 5: QA Agent Validates (Incremental)**
```python
QA receives context:
{
  "conversation_history": [
    {"role": "user", "message": "Tomorrow I need to go to the grocery store. I also have to go to a 1 hr appointment in Los altos. Then I'm meeting a friend in Fremont for a movie at 5:30PM."},
    {"role": "assistant", "message": "I've created 3 tasks. Let me process each one..."}
  ],
  "task_list": [...3 tasks...],
  "actions_taken": [{"type": "timer_created", "id": 123}],
  "current_timers": [{"id": 123, "label": "Leave for movie"}],
  "validation_mode": "incremental"
}

QA analysis:
- Expected tasks from conversation: ["grocery store", "Los Altos appointment", "Fremont movie"]
- Completed tasks: ["Fremont movie"]
- INCOMPLETE: ["grocery store", "Los Altos appointment"]
- Note: This is incremental validation, allow continuation

QA returns:
{
  "validated": False,
  "issues": [
    "Task 'grocery store' is pending - needs time",
    "Task 'Los Altos appointment' is pending - needs time"
  ],
  "recommendations": [
    "Ask user for grocery store time",
    "Ask user for appointment time"
  ],
  "should_continue": True  # Incremental mode - can continue with issues
}
```

**Step 6: Planner Asks Follow-up**
```
Planner sees validation failed
Picks first pending task: grocery store
Asks: "I've created a timer for your movie. What time do you want
       to go to the grocery store tomorrow?"
```

**User provides time → Cycle continues**

---

## Appendix B: Multi-Turn Conversation Example

This example shows how QA agent handles evolving requirements across multiple user messages.

**Turn 1:**
```
User: "I want to go to the museum tomorrow"

Planner: Creates task list
- Task 1: "Museum" (pending - no time, no specific museum)

Planner: Delegates to QA (incremental validation)
QA receives:
{
  "conversation_history": [
    {"role": "user", "message": "I want to go to the museum tomorrow"}
  ],
  "task_list": [{"id": 1, "label": "Museum", "status": "pending"}],
  "actions_taken": [],
  "validation_mode": "incremental"
}

QA: Detects missing information
- Expected: Museum visit
- Missing: Which museum? What time?
- Should continue: Yes (incremental)

Planner asks: "Which museum would you like to visit, and what time?"
```

**Turn 2:**
```
User: "The science museum, in the afternoon"

Planner: Updates task metadata
- Task 1: "Science Museum" (still pending - "afternoon" not specific enough)

QA receives (incremental):
{
  "conversation_history": [
    {"role": "user", "message": "I want to go to the museum tomorrow"},
    {"role": "assistant", "message": "Which museum would you like to visit, and what time?"},
    {"role": "user", "message": "The science museum, in the afternoon"}
  ],
  "task_list": [{"id": 1, "label": "Science Museum", "time": "afternoon", "status": "pending"}],
  "actions_taken": [],
  "validation_mode": "incremental"
}

QA analysis:
- From conversation: User wants "science museum" (specified), "afternoon" (vague)
- Check: Can we create timer with "afternoon"? Probably need specific time
- Recommendation: Ask for specific time

Planner asks: "What time in the afternoon? (e.g., 2pm, 3pm)"
```

**Turn 3:**
```
User: "3pm works"

Planner: Marks task ready, delegates to location_agent
Location agent: Creates timer for Science Museum at 3pm

QA receives (final validation):
{
  "conversation_history": [
    {"role": "user", "message": "I want to go to the museum tomorrow"},
    {"role": "assistant", "message": "Which museum would you like to visit, and what time?"},
    {"role": "user", "message": "The science museum, in the afternoon"},
    {"role": "assistant", "message": "What time in the afternoon?"},
    {"role": "user", "message": "3pm works"}
  ],
  "task_list": [{"id": 1, "label": "Science Museum", "deadline": "3pm", "status": "completed"}],
  "actions_taken": [
    {"type": "timer_created", "id": 456, "label": "Leave for Science Museum", "arrival_time": "3pm"}
  ],
  "current_timers": [{"id": 456, "label": "Leave for Science Museum"}],
  "validation_mode": "final"
}

QA analysis:
- Expected from FULL conversation: Science Museum at 3pm tomorrow
- Task list: ✓ Science Museum task completed
- Actions: ✓ Timer created for Science Museum
- Current timers: ✓ Timer exists with ID 456
- Validation: PASS

QA returns: validated=True, project complete
```

**Key Takeaways:**
- QA sees the FULL conversation thread, not just first message
- Requirements evolved: "museum" → "science museum" → "science museum at 3pm"
- Incremental validation caught missing info early
- Final validation confirmed complete project against full conversation history

---

## Review Notes

Please review and provide feedback on:

1. **Architecture:** Does the proposed flow make sense?
2. **QA Agent:** Is the validation logic comprehensive enough?
3. **Structured Responses:** Is the format appropriate?
4. **Migration:** Is the 4-phase approach reasonable?
5. **Trade-offs:** Are there concerns about performance/complexity?
6. **Missing pieces:** Anything not addressed?

Once approved, we can proceed with implementation.

---

**End of Design Document**
