# TimerMind Test Suite

Interactive test harness for TimerMind that simulates browser interaction with the chat interface.

## Features

- **Interactive Mode**: Pauses between steps for manual review
- **LLM-Based Evaluation**: Uses Gemini to evaluate whether responses meet expectations
- **Structured Test Cases**: JSON-based test case definitions
- **Detailed Reporting**: Saves test results with timestamps
- **Browser-Like Interaction**: Simulates typing messages and waiting for responses

## Quick Start

### 1. Ensure TimerMind is Running

```bash
cd /path/to/timermind
source venv/bin/activate
python main.py
```

The server should be running on `http://127.0.0.1:8000`

### 2. Run Tests in Interactive Mode

```bash
cd tests
python test_harness.py
```

This will:
- Load all test cases from `test_cases.json`
- Execute each test step-by-step
- Pause between steps for you to review
- Use LLM to evaluate results
- Display colored output showing pass/fail status

### 3. Run a Specific Test

```bash
python test_harness.py --test-id test_001_dinner_by_630
```

### 4. Run in Automated Mode (No Pauses)

```bash
python test_harness.py --auto
```

## Test Case Format

Test cases are defined in `test_cases.json`:

```json
{
  "id": "test_001_example",
  "name": "Human-readable test name",
  "description": "What this test verifies",
  "steps": [
    {
      "action": "send_message",
      "message": "I need to have dinner ready by 6:30",
      "expected_behavior": {
        "creates_timer": true,
        "timer_label_contains": "dinner",
        "has_deadline": true,
        "urgency_score_range": [0.5, 1.0],
        "rationale_mentions": ["buffer", "time"]
      }
    }
  ],
  "cleanup": {
    "reset_data": true
  }
}
```

## Expected Behavior Options

### Timer Creation
- `creates_timer`: Boolean - whether a timer should be created
- `timer_label_contains`: String or Array - keywords that should appear in timer label
- `has_deadline`: Boolean - whether timer should have a deadline
- `timer_count`: Number - expected total number of timers
- `category`: String - expected timer category

### Scoring Ranges
- `urgency_score_range`: [min, max] - expected urgency score range (0.0-1.0)
- `importance_score_range`: [min, max] - expected importance score range (0.0-1.0)
- `priority_score_range`: [min, max] - expected priority score range (0.0-1.0)

### Rationale Verification
- `rationale_mentions`: Array - keywords that should appear in the rationale
- `has_rationale`: Boolean - whether timer should have a rationale (not None)
- `rationale_is_string`: Boolean - whether rationale is a string type
- `rationale_not_empty`: Boolean - whether rationale contains non-whitespace text

### Preferences
- `updates_preferences`: Boolean - whether preferences should be updated
- `preference_category`: String - category that should be affected
- `preference_weight_gt`: Number - weight should be greater than this value

## Command Line Options

```bash
python test_harness.py [options]

Options:
  --test-file FILE    Path to test cases JSON file (default: test_cases.json)
  --base-url URL      TimerMind API base URL (default: http://127.0.0.1:8000)
  --auto              Run in automated mode (no pauses)
  --test-id ID        Run only a specific test case by ID
```

## Interactive Mode

When running in interactive mode (default), the harness:

1. Displays the test name and description
2. Shows each step as it executes
3. Prints the message being sent (like typing in the browser)
4. Waits for the API response
5. Displays the response (like seeing it in chat)
6. Shows the current state (timers, preferences)
7. Runs verification checks
8. Uses LLM to evaluate the response
9. **Pauses and waits for you to press Enter** before continuing
10. Moves to the next step

This simulates the experience of manually testing the UI while providing automated verification.

## Test Results

Results are saved in `test_results_YYYYMMDD_HHMMSS.json`:

```json
{
  "summary": {
    "total": 6,
    "passed": 5,
    "failed": 1,
    "timestamp": "2025-11-17T14:30:00"
  },
  "results": [
    {
      "test_id": "test_001_dinner_by_630",
      "test_name": "Dinner deadline with effort estimation",
      "pass": true,
      "step_results": [...],
      "timestamp": "2025-11-17T14:25:00"
    }
  ]
}
```

## Adding New Tests

1. Add a new test case to `test_cases.json`
2. Define the steps and expected behavior
3. Run the test harness
4. Review the results and refine expectations

## Example Test Run

```
================================================================================
  TimerMind Test Suite
================================================================================

Running 1 test case(s)
Mode: Interactive
Base URL: http://127.0.0.1:8000


================================================================================
  Test: Dinner deadline with effort estimation (test_001_dinner_by_630)
================================================================================

Description: Tests urgency scoring with buffer ratio logic for a cooking task

[Step 1/1] send_message
💬 User: I need to have dinner ready by 6:30
🤖 TimerMind: I've created a timer for your dinner preparation...
   Execution trace: 12 events

📊 Current State:
   Timers: 1
      - Dinner preparation (Priority: 0.72)

Verification Results:
   ✓ Timer created
   ✓ Label contains ['dinner']
   ✓ Has deadline
   ✓ Urgency score 0.75 in [0.5, 1.0]
   ✓ Importance score 0.60 in [0.3, 0.7]
   ✓ Rationale mentions 'buffer'
   ✓ Rationale mentions 'time'

LLM Evaluation:
   PASS
   Reason: All expectations met. Timer created with appropriate scores...

================================================================================
  Test Result: PASS ✓
================================================================================
```

## Tips

- Run tests in interactive mode when debugging or adding new tests
- Use `--auto` for CI/CD pipelines
- Review the LLM evaluation reasoning to understand why tests pass/fail
- Adjust score ranges based on actual agent behavior
- Use `--test-id` to quickly iterate on a single test
