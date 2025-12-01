#!/usr/bin/env python3
"""
Test the QA Agent validation with the problematic multi-task scenario.

This tests the regression case where the grocery store timer was forgotten
because no time was specified.
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

print("=" * 80)
print("Testing QA Agent - Multi-Task Validation")
print("=" * 80)

# Step 1: Reset database to start fresh
print("\n[Step 1] Resetting database...")
reset_response = requests.post(f"{BASE_URL}/api/reset")
if reset_response.status_code == 200:
    print("✓ Database reset successful")
else:
    print(f"✗ Reset failed: {reset_response.status_code}")
    exit(1)

time.sleep(1)

# Step 2: Send the problematic multi-task request
print("\n[Step 2] Sending multi-task request...")
print("Message: 'Tomorrow I need to go to the grocery store, appointment in Los Altos at 4PM, then movie in Fremont at 5:30PM'")

chat_response = requests.post(
    f"{BASE_URL}/api/chat",
    json={
        "message": "Tomorrow I need to go to the grocery store, appointment in Los Altos at 4PM, then movie in Fremont at 5:30PM"
    }
)

if chat_response.status_code != 200:
    print(f"✗ Chat request failed: {chat_response.status_code}")
    print(chat_response.text)
    exit(1)

chat_data = chat_response.json()
session_id = chat_data.get('session_id')
response_text = chat_data.get('response', '')
timers = chat_data.get('timers', [])
execution_trace = chat_data.get('execution_trace', [])

print(f"\n✓ Session ID: {session_id}")
print(f"\n--- Agent Response ---")
print(response_text)
print(f"\n--- Timers Created ({len(timers)}) ---")
for timer in timers:
    print(f"  - {timer.get('label')}: {timer.get('deadline_iso', 'no deadline')}")

# Step 3: Analyze execution trace for QA agent activity
print(f"\n--- Execution Trace ({len(execution_trace)} events) ---")
qa_agent_events = []
for event in execution_trace:
    event_type = event.get('type')
    agent = event.get('agent', '')

    # Track QA agent activity
    if 'qa_agent' in agent.lower():
        qa_agent_events.append(event)
        print(f"  [QA] {event_type}: {event.get('content_preview', 'N/A')[:100]}")
    elif event_type in ['OrchestrationStart', 'AgentStart']:
        print(f"  [{agent}] {event_type}")
    elif event.get('tool_name'):
        print(f"  [TOOL] {event.get('tool_name')}")

# Step 4: Check what timers were actually created
print(f"\n--- Timer Validation ---")
timers_response = requests.get(f"{BASE_URL}/api/timers")
if timers_response.status_code == 200:
    all_timers = timers_response.json().get('timers', [])
    print(f"Total timers in database: {len(all_timers)}")

    # Check for expected timers
    has_grocery = any('grocery' in t.get('label', '').lower() for t in all_timers)
    has_los_altos = any('los altos' in t.get('label', '').lower() or 'appointment' in t.get('label', '').lower() for t in all_timers)
    has_movie = any('movie' in t.get('label', '').lower() or 'fremont' in t.get('label', '').lower() for t in all_timers)

    print(f"  Grocery store timer: {'✓' if has_grocery else '✗'}")
    print(f"  Los Altos appointment timer: {'✓' if has_los_altos else '✗'}")
    print(f"  Fremont movie timer: {'✓' if has_movie else '✗'}")

# Step 5: Evaluate QA agent performance
print(f"\n--- QA Agent Evaluation ---")
print(f"QA agent was invoked: {'✓' if qa_agent_events else '✗'}")

if qa_agent_events:
    print(f"QA agent events: {len(qa_agent_events)}")
    for event in qa_agent_events:
        print(f"  - {event.get('type')}: {event.get('content_preview', 'N/A')[:150]}")

# Check if agent asked for missing information
asked_for_grocery_time = any(
    'grocery' in response_text.lower() and ('time' in response_text.lower() or 'when' in response_text.lower())
    for _ in [response_text]
)

print(f"Agent asked for grocery store time: {'✓' if asked_for_grocery_time else '✗'}")

# Step 6: Final verdict
print("\n" + "=" * 80)
if not has_grocery and asked_for_grocery_time:
    print("✅ TEST PASSED!")
    print("The QA agent correctly identified the missing grocery store timer")
    print("and the planner asked the user for the missing time.")
elif has_grocery:
    print("⚠️  UNEXPECTED: Grocery timer was created (how did it get a time?)")
elif not asked_for_grocery_time:
    print("❌ TEST FAILED!")
    print("The agent did not ask for the grocery store time.")
    print("Expected: Agent should recognize grocery store has no time and ask user.")
else:
    print("⚠️  UNCLEAR RESULT")

print("=" * 80)
