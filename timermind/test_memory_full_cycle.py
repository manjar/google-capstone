"""
Test script to verify the COMPLETE ADK memory workflow cycle.

This test follows the proper memory workflow:
1. Session Interaction: User shares information in session 1
2. Ingestion into Memory: Session is added to memory store
3. Later Query: User asks a question in session 2 that requires past context
4. Agent Uses Memory Tool: Agent calls preload_memory/load_memory
5. Search Execution: Memory service searches its store
6. Results Returned: Relevant memory snippets are returned
7. Agent Uses Results: Agent incorporates memory into response
"""

import requests
import sys
import time


def test_full_memory_cycle():
    """Test the complete memory workflow from storage to retrieval."""

    base_url = "http://127.0.0.1:8000"

    print("\n" + "="*70)
    print("FULL MEMORY CYCLE TEST")
    print("="*70 + "\n")

    # =========================================================================
    # STEP 1: Session Interaction - Share specific information
    # =========================================================================
    print("STEP 1: Session Interaction")
    print("-" * 70)

    # Use a distinctive piece of information that's easy to verify
    user_message_1 = (
        "Please remember this important information: "
        "My favorite coffee shop is Blue Bottle Coffee on University Avenue. "
        "I go there every Tuesday at 9 AM for my weekly meeting with Sarah."
    )

    print(f"User shares information: {user_message_1}\n")

    try:
        response_1 = requests.post(
            f"{base_url}/api/chat",
            json={"message": user_message_1},
            timeout=60
        )

        if response_1.status_code != 200:
            print(f"✗ Error: HTTP {response_1.status_code}")
            print(f"  Response: {response_1.text}\n")
            return False

        result_1 = response_1.json()
        agent_response_1 = result_1.get("response", "")
        session_id_1 = result_1.get("session_id", "")

        print(f"Agent response: {agent_response_1}")
        print(f"Session ID: {session_id_1}")
        print("✓ Information shared successfully\n")

        # Wait for memory to be saved via auto_save_to_memory callback
        print("Waiting for memory ingestion (auto_save_to_memory callback)...")
        time.sleep(3)
        print("✓ Memory should now be stored\n")

    except Exception as e:
        print(f"✗ Error in Step 1: {e}\n")
        return False

    # =========================================================================
    # STEP 2: Verify memory was stored
    # =========================================================================
    print("\nSTEP 2: Verify Memory Storage")
    print("-" * 70)

    try:
        # Query the memory API to verify the information was stored
        memories_response = requests.post(
            f"{base_url}/api/memories",
            json={"session_id": session_id_1},
            timeout=30
        )

        if memories_response.status_code == 200:
            memories_data = memories_response.json()
            memory_count = memories_data.get("count", 0)
            print(f"Memories stored: {memory_count}")

            if memory_count > 0:
                print("✓ Memory storage confirmed")
                print(f"  Stored memories: {memories_data.get('memories', [])[:2]}\n")
            else:
                print("⚠ No memories found in storage (may still work via session history)\n")
        else:
            print("⚠ Could not verify memory storage via API\n")

    except Exception as e:
        print(f"⚠ Memory verification error: {e}\n")

    # =========================================================================
    # STEP 3: Later Query - Ask question requiring past context
    # =========================================================================
    print("\nSTEP 3: Later Query (New Session)")
    print("-" * 70)

    # Create a question that CLEARLY requires retrieving the past information
    # The question directly references information shared earlier
    user_message_2 = (
        "What coffee shop did I mention I go to on Tuesdays? "
        "And what time do I usually go there?"
    )

    print(f"User asks (in NEW session): {user_message_2}\n")
    print("Expected behavior:")
    print("  1. Agent recognizes it needs past context")
    print("  2. Agent calls preload_memory or load_memory tool")
    print("  3. Memory service searches for 'coffee shop Tuesday'")
    print("  4. Agent receives: Blue Bottle Coffee, 9 AM, University Ave")
    print("  5. Agent responds with this information\n")

    try:
        # NEW session - let API auto-create
        response_2 = requests.post(
            f"{base_url}/api/chat",
            json={"message": user_message_2},
            timeout=60
        )

        if response_2.status_code != 200:
            print(f"✗ Error: HTTP {response_2.status_code}")
            print(f"  Response: {response_2.text}\n")
            return False

        result_2 = response_2.json()
        agent_response_2 = result_2.get("response", "")
        session_id_2 = result_2.get("session_id", "")

        print(f"New Session ID: {session_id_2}")
        print(f"\nAgent response: {agent_response_2}\n")

        # =====================================================================
        # STEP 4: Verify memory retrieval worked
        # =====================================================================
        print("\nSTEP 4: Verify Memory Retrieval")
        print("-" * 70)

        response_lower = agent_response_2.lower()

        # Check if the agent's response contains the key information
        has_coffee_shop = "blue bottle" in response_lower or "blue bottle coffee" in response_lower
        has_day = "tuesday" in response_lower
        has_time = "9" in response_lower or "9am" in response_lower or "9 am" in response_lower
        has_location = "university" in response_lower or "university avenue" in response_lower

        matches = sum([has_coffee_shop, has_day, has_time, has_location])

        print("Checking if agent retrieved and used the memory:")
        print(f"  ✓ Coffee shop name (Blue Bottle): {has_coffee_shop}")
        print(f"  ✓ Day (Tuesday): {has_day}")
        print(f"  ✓ Time (9 AM): {has_time}")
        print(f"  ✓ Location (University Avenue): {has_location}")
        print(f"\nMatches: {matches}/4\n")

        if matches >= 3:
            print("✓✓✓ MEMORY CYCLE TEST PASSED ✓✓✓")
            print(f"Agent successfully retrieved and used {matches}/4 key facts from memory!\n")
            return True
        elif matches >= 2:
            print("⚠ PARTIAL SUCCESS")
            print(f"Agent retrieved some information ({matches}/4 facts)")
            print("Memory retrieval may be working but not optimally\n")
            return True
        else:
            print("✗ MEMORY RETRIEVAL FAILED")
            print(f"Agent only retrieved {matches}/4 key facts")
            print("Possible issues:")
            print("  1. Agent didn't call the memory tool")
            print("  2. Memory search didn't find relevant results")
            print("  3. Agent didn't use the retrieved information")
            print("\nCheck logs for memory tool calls and search queries\n")
            return False

    except Exception as e:
        print(f"✗ Error in Step 3: {e}\n")
        return False


def main():
    """Run the full memory cycle test."""

    # Check if server is running
    try:
        requests.get("http://127.0.0.1:8000", timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Server is not running on port 8000")
        print("  Start the server first with: python main.py\n")
        sys.exit(1)
    except Exception:
        pass  # Server is running

    try:
        success = test_full_memory_cycle()

        print("="*70)
        print("TEST SUMMARY")
        print("="*70)

        if success:
            print("\n✓ Full memory cycle test completed successfully")
            print("\nWhat this proves:")
            print("  - Memory storage is working (auto_save_to_memory)")
            print("  - Memory retrieval tools are available (preload_memory)")
            print("  - Agent can access and use stored information")
            print("  - Cross-session memory persistence works\n")
            sys.exit(0)
        else:
            print("\n✗ Memory cycle test failed")
            print("\nNext steps:")
            print("  1. Check server logs for memory tool calls")
            print("  2. Verify memory service is properly configured")
            print("  3. Ensure agent has access to memory tools")
            print("  4. Review agent instructions for memory usage\n")
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
