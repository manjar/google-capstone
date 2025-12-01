#!/usr/bin/env python3
"""
Direct test to verify load_memory tool is working.

This test directly invokes the LoadMemoryTool to see if it can store and retrieve memories.
"""

import asyncio
from google.adk.memory import InMemoryMemoryService
from google.adk.tools.load_memory_tool import LoadMemoryTool

async def test_direct_memory_storage():
    """Test if we can directly store and retrieve a memory."""
    print("\n" + "="*80)
    print("Direct Memory Storage Test")
    print("="*80 + "\n")

    # Create a memory service
    memory_service = InMemoryMemoryService()

    # Test storing a memory
    app_name = "timermind"
    user_id = "default_user"
    test_content = "User's home address is 123 Main Street, Campbell, CA"

    print(f"Storing memory: '{test_content}'")

    try:
        # Use the memory service's load_memory method directly
        result = await memory_service.load_memory(
            app_name=app_name,
            user_id=user_id,
            content=test_content
        )
        print(f"✓ Memory stored successfully")
        print(f"  Result: {result}\n")
    except Exception as e:
        print(f"✗ Failed to store memory: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    # Try to search for the memory
    print("Searching for stored memories...")

    try:
        # Search with empty query
        search_response = await memory_service.search_memory(
            app_name=app_name,
            user_id=user_id,
            query=""
        )

        if hasattr(search_response, 'memories') and search_response.memories:
            print(f"✓ Found {len(search_response.memories)} memories:")
            for i, memory in enumerate(search_response.memories):
                content = ""
                if hasattr(memory, 'content'):
                    if hasattr(memory.content, 'parts'):
                        for part in memory.content.parts:
                            if hasattr(part, 'text'):
                                content += part.text
                    elif hasattr(memory.content, 'text'):
                        content = memory.content.text
                    else:
                        content = str(memory.content)
                print(f"  Memory {i+1}: {content}")
        else:
            print("✗ No memories found")
            print(f"  Search response: {search_response}")
    except Exception as e:
        print(f"✗ Failed to search memories: {e}\n")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*80)
    return True

if __name__ == "__main__":
    asyncio.run(test_direct_memory_storage())
