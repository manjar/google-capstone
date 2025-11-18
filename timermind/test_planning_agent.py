#!/usr/bin/env python3
"""
Quick test script to check if planning_agent is ever invoked.
Tests various scenarios that should theoretically require planning.
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = f"test-planning-{datetime.now().strftime('%H%M%S')}"

def send_message(msg):
    """Send a message and return the response with execution trace analysis."""
    response = requests.post(
        f"{BASE_URL}/api/chat",
        json={"message": msg, "session_id": SESSION_ID}
    )
    data = response.json()

    # Extract agents from execution trace
    agents_used = [event.get('agent', '?') for event in data.get('execution_trace', [])]
    has_planning = 'planning_agent' in agents_used
    has_context = 'context_agent' in agents_used

    print(f"\n{'='*80}")
    print(f"Message: {msg}")
    print(f"Response: {data['response'][:150]}...")
    print(f"Agents used: {list(set(agents_used))}")
    print(f"Planning agent invoked: {has_planning}")
    print(f"Context agent invoked: {has_context}")

    return data, has_planning, has_context

def main():
    print("Testing scenarios that SHOULD require planning_agent...")
    print("="*80)

    results = []

    # Test 1: "Between X and Y" - canonical planning scenario
    print("\n\nTEST 1: Between two tasks")
    print("-" * 80)
    send_message("I need to get the mail by 1:30 PM")
    send_message("I need to pick up Willem at 3:00 PM")
    _, has_plan, has_ctx = send_message("Between getting the mail and picking up Willem, I need to have lunch")
    results.append(("Between X and Y", has_plan or has_ctx))

    # Test 2: Fuzzy reference with "that"
    print("\n\nTEST 2: Fuzzy reference update")
    print("-" * 80)
    send_message("I need to submit the project report by Friday at 5 PM")
    _, has_plan, has_ctx = send_message("Actually, change that report deadline to Thursday at 3 PM")
    results.append(("Fuzzy 'that' reference", has_plan or has_ctx))

    # Test 3: "After X" scenario
    print("\n\nTEST 3: After another task")
    print("-" * 80)
    send_message("Team meeting at 2 PM")
    _, has_plan, has_ctx = send_message("After the meeting, I need to call the client")
    results.append(("After X task", has_plan or has_ctx))

    # Test 4: Multiple fuzzy references
    print("\n\nTEST 4: Reference with 'it'")
    print("-" * 80)
    send_message("Dentist appointment tomorrow at 10 AM")
    _, has_plan, has_ctx = send_message("Actually, make it 11 AM instead")
    results.append(("Fuzzy 'it' reference", has_plan or has_ctx))

    # Test 5: Complex multi-step
    print("\n\nTEST 5: Multi-step with calculation")
    print("-" * 80)
    _, has_plan, has_ctx = send_message("I have 3 meetings today, each 30 minutes apart, starting at 9 AM")
    results.append(("Multi-step creation", has_plan or has_ctx))

    # Summary
    print("\n\n" + "="*80)
    print("SUMMARY: Planning Agent Usage")
    print("="*80)
    for test_name, was_used in results:
        status = "✓ USED" if was_used else "✗ NOT USED"
        print(f"{test_name:30s} {status}")

    total_used = sum(1 for _, used in results if used)
    print(f"\nTotal: {total_used}/{len(results)} tests triggered planning_agent")

    if total_used == 0:
        print("\n⚠️  CONCLUSION: Planning agent is NEVER used. Consider removing it.")
    else:
        print(f"\n✓ Planning agent provides value in {total_used} scenario(s).")

if __name__ == "__main__":
    main()
