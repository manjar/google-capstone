#!/usr/bin/env python3
"""
Test memory search with specific queries.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

# First, send a message with a home address
print("Sending message with home address...")
response = requests.post(
    f"{BASE_URL}/api/chat",
    json={"message": "My home address is 456 Oak Street, San Jose, CA"}
)

if response.status_code == 200:
    data = response.json()
    session_id = data.get('session_id')
    print(f"✓ Message sent. Session ID: {session_id}")
    print(f"Response: {data.get('response', 'No response')[:100]}...")
else:
    print(f"✗ Error: {response.status_code}")
    exit(1)

# Wait for memory watcher
import time
print("\nWaiting 3 seconds for memory watcher...")
time.sleep(3)

# Now test retrieving memories via the API endpoint
print("\nTesting /api/memories endpoint (empty query)...")
mem_response = requests.post(
    f"{BASE_URL}/api/memories",
    json={"session_id": session_id}
)

if mem_response.status_code == 200:
    mem_data = mem_response.json()
    print(f"Count: {mem_data.get('count', 0)}")
    print(f"Memories: {mem_data.get('memories', [])[:1]}")  # Show first memory
else:
    print(f"✗ Error: {mem_response.status_code}")

# Now test direct search with specific query
print("\n" + "="*80)
print("Testing direct memory_service.search_memory() with specific query...")
print("="*80)

from agents.orchestrator import memory_service
import asyncio

async def test_search():
    # Search for "address"
    print("\nSearching for 'address'...")
    search_response = await memory_service.search_memory(
        app_name="timermind",
        user_id="default_user",
        query="address"
    )

    print(f"Response type: {type(search_response)}")
    print(f"Response: {search_response}")

    if hasattr(search_response, 'memories'):
        print(f"Memories count: {len(search_response.memories) if search_response.memories else 0}")
        if search_response.memories:
            for i, mem in enumerate(search_response.memories):
                print(f"\nMemory {i+1}:")
                print(f"  Type: {type(mem)}")
                print(f"  Content: {mem}")

    # Try searching for "home"
    print("\n" + "-"*80)
    print("Searching for 'home'...")
    search_response2 = await memory_service.search_memory(
        app_name="timermind",
        user_id="default_user",
        query="home"
    )

    print(f"Response: {search_response2}")
    if hasattr(search_response2, 'memories') and search_response2.memories:
        print(f"Found {len(search_response2.memories)} memories")

asyncio.run(test_search())
