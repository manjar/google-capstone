#!/usr/bin/env python3
"""
Test using the exact pattern from the Kaggle notebook.

This replicates the Kaggle notebook's approach to see if our session
structure differs in a way that prevents search from working.
"""

import asyncio
import os
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.genai import types

# Load API key from environment
from dotenv import load_dotenv
load_dotenv()


async def main():
    print("\n" + "="*80)
    print("Testing Kaggle Notebook Pattern")
    print("="*80 + "\n")

    # Setup (exactly like Kaggle notebook)
    APP_NAME = "TestApp"
    USER_ID = "test_user"

    # Create services
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()

    # Create a simple agent (like Kaggle)
    agent = LlmAgent(
        model=Gemini(model="gemini-2.0-flash"),
        name="TestAgent",
        instruction="Answer user questions in simple words.",
    )

    # Create runner
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
        memory_service=memory_service
    )

    print("Step 1: Having a conversation")
    print("-" * 80)

    # Create a session and have a conversation
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id="test-session-01"
    )

    # Send a message
    user_message = "My favorite color is blue-green"
    print(f"User: {user_message}")

    query_content = types.Content(
        role="user",
        parts=[types.Part(text=user_message)]
    )

    response_text = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=query_content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            text = event.content.parts[0].text
            if text and text != "None":
                response_text = text
                print(f"Agent: {text[:100]}...")

    print("\nStep 2: Check session structure")
    print("-" * 80)

    # Get the session back
    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id="test-session-01"
    )

    print(f"Session ID: {session.id}")
    print(f"Session events count: {len(session.events)}")
    print(f"Session events:")
    for i, event in enumerate(session.events):
        print(f"  Event {i}:")
        print(f"    Role: {event.content.role if event.content else 'N/A'}")
        if event.content and event.content.parts:
            text = event.content.parts[0].text[:50] if hasattr(event.content.parts[0], 'text') else str(event.content.parts[0])[:50]
            print(f"    Text: {text}...")

    print("\nStep 3: Add session to memory")
    print("-" * 80)

    try:
        await memory_service.add_session_to_memory(session)
        print("✓ Session added to memory successfully")
    except Exception as e:
        print(f"✗ Error adding to memory: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\nStep 4: Search memory (empty query)")
    print("-" * 80)

    search_response = await memory_service.search_memory(
        app_name=APP_NAME,
        user_id=USER_ID,
        query=""
    )

    print(f"Search response type: {type(search_response)}")
    print(f"Memories found: {len(search_response.memories) if search_response.memories else 0}")

    if search_response.memories:
        print("\nMemories:")
        for i, memory in enumerate(search_response.memories):
            print(f"\n  Memory {i+1}:")
            print(f"    Type: {type(memory)}")
            print(f"    Author: {getattr(memory, 'author', 'N/A')}")
            if hasattr(memory, 'content') and memory.content:
                if hasattr(memory.content, 'parts') and memory.content.parts:
                    for part in memory.content.parts:
                        if hasattr(part, 'text'):
                            print(f"    Text: {part.text[:100]}...")
    else:
        print("  No memories found")

    print("\nStep 5: Search memory (specific query)")
    print("-" * 80)

    search_response2 = await memory_service.search_memory(
        app_name=APP_NAME,
        user_id=USER_ID,
        query="What is the user's favorite color?"
    )

    print(f"Memories found: {len(search_response2.memories) if search_response2.memories else 0}")

    if search_response2.memories:
        print("\nMemories:")
        for i, memory in enumerate(search_response2.memories):
            if hasattr(memory, 'content') and memory.content:
                if hasattr(memory.content, 'parts') and memory.content.parts:
                    for part in memory.content.parts:
                        if hasattr(part, 'text'):
                            print(f"  [{memory.author}]: {part.text[:80]}...")
    else:
        print("  No memories found")

    print("\n" + "="*80)
    print("Test Complete")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
