"""
Simple memory test that avoids triggering task detection.

Tests memory storage and retrieval with purely informational messages.
"""

import requests
import sys
import time


def test_simple_memory():
    """Test memory with simple factual information."""

    base_url = "http://127.0.0.1:8000"

    print("\n" + "="*70)
    print("SIMPLE MEMORY TEST")
    print("="*70 + "\n")

    # STEP 1: Share factual information (no task language)
    print("STEP 1: Sharing factual information")
    print("-" * 70)

    user_message_1 = (
        "Just so you know, my favorite color is blue and "
        "my pet's name is Max."
    )

    print(f"User says: {user_message_1}\n")

    try:
        response_1 = requests.post(
            f"{base_url}/api/chat",
            json={"message": user_message_1},
            timeout=30  # Reduced timeout
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
        print("✓ Information shared\n")

        # Wait for memory to be saved
        print("Waiting for memory ingestion...")
        time.sleep(2)
        print("✓ Memory should be stored\n")

    except Exception as e:
        print(f"✗ Error in Step 1: {e}\n")
        return False

    # STEP 2: New session - ask about the stored information
    print("\nSTEP 2: Querying in new session")
    print("-" * 70)

    user_message_2 = "What's my pet's name?"

    print(f"User asks (new session): {user_message_2}\n")

    try:
        response_2 = requests.post(
            f"{base_url}/api/chat",
            json={"message": user_message_2},
            timeout=30
        )

        if response_2.status_code != 200:
            print(f"✗ Error: HTTP {response_2.status_code}")
            print(f"  Response: {response_2.text}\n")
            return False

        result_2 = response_2.json()
        agent_response_2 = result_2.get("response", "")
        session_id_2 = result_2.get("session_id", "")

        print(f"New Session ID: {session_id_2}")
        print(f"Agent response: {agent_response_2}\n")

        # Check if agent remembered
        response_lower = agent_response_2.lower()
        remembered_max = "max" in response_lower

        print("STEP 3: Verify memory retrieval")
        print("-" * 70)
        print(f"  Agent mentioned 'Max': {remembered_max}\n")

        if remembered_max:
            print("✓✓✓ MEMORY TEST PASSED ✓✓✓")
            print("Agent successfully retrieved information from memory!\n")
            return True
        else:
            print("✗ Memory retrieval issue")
            print("Agent didn't recall the pet's name from previous session\n")
            return False

    except Exception as e:
        print(f"✗ Error in Step 2: {e}\n")
        return False


def main():
    """Run the simple memory test."""

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
        success = test_simple_memory()

        print("="*70)
        print("TEST SUMMARY")
        print("="*70)

        if success:
            print("\n✓ Memory test passed")
            print("  preload_memory tool is working correctly\n")
            sys.exit(0)
        else:
            print("\n✗ Memory test failed")
            print("  Check logs for memory tool calls\n")
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
