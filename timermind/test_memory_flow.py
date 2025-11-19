#!/usr/bin/env python3
"""
Test the complete memory flow with automatic storage and retrieval.
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

print("=" * 80)
print("Testing Automatic Memory Storage and Retrieval")
print("=" * 80)

# Step 1: Tell the agent your home address
print("\n[Step 1] Telling the agent my home address...")
response1 = requests.post(
    f"{BASE_URL}/api/chat",
    json={"message": "My home address is 789 Maple Drive, Cupertino, CA 95014"}
)

if response1.status_code == 200:
    data1 = response1.json()
    session_id = data1.get('session_id')
    print(f"✓ Session ID: {session_id}")
    print(f"✓ Agent response: {data1.get('response', 'No response')[:150]}...")
else:
    print(f"✗ Error: {response1.status_code}")
    exit(1)

# Wait a moment for memory callback to complete
print("\n[Step 2] Waiting 2 seconds for memory to be saved...")
time.sleep(2)

# Step 3: Ask about the address in a NEW session (tests memory retrieval)
print("\n[Step 3] Starting NEW conversation and asking about my address...")
print("(This tests if preload_memory automatically loads the previous conversation)")
response2 = requests.post(
    f"{BASE_URL}/api/chat",
    json={
        "message": "What's my home address again?",
        # Note: NOT passing session_id to create a NEW session
    }
)

if response2.status_code == 200:
    data2 = response2.json()
    new_session_id = data2.get('session_id')
    agent_response = data2.get('response', 'No response')

    print(f"✓ New Session ID: {new_session_id}")
    print(f"✓ Agent response: {agent_response}")

    # Check if the agent recalled the address
    if "789 Maple Drive" in agent_response or "Cupertino" in agent_response:
        print("\n" + "=" * 80)
        print("✅ SUCCESS! Memory retrieval working!")
        print("The agent recalled the address from a previous conversation.")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("⚠️  PARTIAL: Agent responded but may not have recalled the exact address")
        print("Response:", agent_response)
        print("=" * 80)
else:
    print(f"✗ Error: {response2.status_code}")
    print(response2.text)

print("\nTest complete!")
