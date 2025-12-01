#!/usr/bin/env python3
"""
Test script to verify memory watcher creates memories when user shares information.

This test validates that the memory watcher agent is working correctly by:
1. Sending a message with a home address
2. Checking that a memory was created in ADK InMemoryMemoryService
3. Verifying the memory content is correct
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = None  # Will be set by first API call


class Colors:
    OKGREEN = '\033[92m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    OKCYAN = '\033[96m'


def print_test_header(text):
    print(f"\n{Colors.BOLD}{'=' * 80}")
    print(f"  {text}")
    print(f"{'=' * 80}{Colors.ENDC}\n")


def send_message(msg):
    """Send a message to the API."""
    global SESSION_ID
    print(f"{Colors.OKCYAN}💬 User: {msg}{Colors.ENDC}")

    response = requests.post(
        f"{BASE_URL}/api/chat",
        json={"message": msg, "session_id": SESSION_ID}
    )

    if response.status_code != 200:
        print(f"{Colors.FAIL}❌ Error: {response.json().get('detail', 'Unknown error')}{Colors.ENDC}")
        return None

    data = response.json()
    # Update session ID from response
    if data.get('session_id'):
        SESSION_ID = data['session_id']
    print(f"{Colors.OKGREEN}🤖 TimerMind: {data.get('response', 'No response')}{Colors.ENDC}")
    return data


def get_memories():
    """Retrieve memories from the ADK memory service."""
    response = requests.post(
        f"{BASE_URL}/api/memories",
        json={"session_id": SESSION_ID}
    )

    if response.status_code != 200:
        print(f"{Colors.FAIL}❌ Error getting memories: {response.json().get('detail', 'Unknown error')}{Colors.ENDC}")
        return None

    return response.json()


def reset_data():
    """Reset all data."""
    global SESSION_ID
    print(f"{Colors.OKCYAN}🧹 Resetting all data...{Colors.ENDC}")
    response = requests.post(f"{BASE_URL}/api/reset")
    SESSION_ID = None  # Reset session ID
    return response.status_code == 200


def test_memory_creation():
    """Test that memory watcher creates memories."""
    print_test_header("Memory Watcher Test: Home Address Storage")

    # Reset data to start fresh
    if not reset_data():
        print(f"{Colors.FAIL}❌ Failed to reset data{Colors.ENDC}")
        return False

    # Wait a moment for reset to complete
    time.sleep(1)

    # Test 1: Send a message with home address
    print(f"\n{Colors.BOLD}[Test 1] Sending home address...{Colors.ENDC}")
    response = send_message("My home address is 123 Main Street, Campbell, CA 95008")

    if not response:
        print(f"{Colors.FAIL}❌ Failed to send message{Colors.ENDC}")
        return False

    # Wait a moment for memory watcher to complete (it runs in parallel)
    print(f"{Colors.OKCYAN}⏳ Waiting for memory watcher to process...{Colors.ENDC}")
    time.sleep(3)

    # Test 2: Check if memory was created
    print(f"\n{Colors.BOLD}[Test 2] Checking if memory was created...{Colors.ENDC}")
    memories_data = get_memories()

    if not memories_data:
        print(f"{Colors.FAIL}❌ Failed to retrieve memories{Colors.ENDC}")
        return False

    memories = memories_data.get('memories', [])
    count = memories_data.get('count', 0)

    print(f"{Colors.OKCYAN}📊 Found {count} memories{Colors.ENDC}")

    if count == 0:
        print(f"{Colors.FAIL}❌ No memories were created{Colors.ENDC}")
        print(f"{Colors.FAIL}   This indicates the memory watcher is not working correctly{Colors.ENDC}")
        return False

    # Test 3: Verify memory content
    print(f"\n{Colors.BOLD}[Test 3] Verifying memory content...{Colors.ENDC}")

    # Check if any memory contains the address
    address_found = False
    for memory in memories:
        content = memory.get('content', '').lower()
        print(f"{Colors.OKCYAN}   Memory: {memory.get('content', 'N/A')[:100]}...{Colors.ENDC}")

        if '123 main street' in content or 'campbell' in content:
            address_found = True
            print(f"{Colors.OKGREEN}   ✓ Memory contains address information{Colors.ENDC}")

    if not address_found:
        print(f"{Colors.FAIL}❌ No memory contains the address information{Colors.ENDC}")
        print(f"{Colors.FAIL}   Memory watcher may not be capturing home addresses correctly{Colors.ENDC}")
        return False

    # All tests passed!
    print(f"\n{Colors.OKGREEN}{'=' * 80}")
    print(f"  ✓ ALL TESTS PASSED")
    print(f"  Memory watcher is working correctly!")
    print(f"{'=' * 80}{Colors.ENDC}\n")

    return True


def test_preference_memory():
    """Test that memory watcher captures preferences."""
    print_test_header("Memory Watcher Test: Preference Storage")

    # Reset data to start fresh
    if not reset_data():
        print(f"{Colors.FAIL}❌ Failed to reset data{Colors.ENDC}")
        return False

    time.sleep(1)

    # Test 1: Send a message about a preference
    print(f"\n{Colors.BOLD}[Test 1] Sharing a preference...{Colors.ENDC}")
    response = send_message("Health is really important to me. I prioritize health-related tasks highly.")

    if not response:
        print(f"{Colors.FAIL}❌ Failed to send message{Colors.ENDC}")
        return False

    # Wait for memory watcher
    print(f"{Colors.OKCYAN}⏳ Waiting for memory watcher to process...{Colors.ENDC}")
    time.sleep(3)

    # Test 2: Check if memory was created
    print(f"\n{Colors.BOLD}[Test 2] Checking for preference memory...{Colors.ENDC}")
    memories_data = get_memories()

    if not memories_data:
        print(f"{Colors.FAIL}❌ Failed to retrieve memories{Colors.ENDC}")
        return False

    memories = memories_data.get('memories', [])
    count = memories_data.get('count', 0)

    print(f"{Colors.OKCYAN}📊 Found {count} memories{Colors.ENDC}")

    if count == 0:
        print(f"{Colors.FAIL}❌ No memories were created{Colors.ENDC}")
        return False

    # Check if any memory contains the preference
    preference_found = False
    for memory in memories:
        content = memory.get('content', '').lower()
        print(f"{Colors.OKCYAN}   Memory: {memory.get('content', 'N/A')[:100]}...{Colors.ENDC}")

        if 'health' in content and ('important' in content or 'priorit' in content):
            preference_found = True
            print(f"{Colors.OKGREEN}   ✓ Memory contains preference information{Colors.ENDC}")

    if not preference_found:
        print(f"{Colors.FAIL}❌ No memory contains the preference information{Colors.ENDC}")
        return False

    print(f"\n{Colors.OKGREEN}{'=' * 80}")
    print(f"  ✓ PREFERENCE TEST PASSED")
    print(f"{'=' * 80}{Colors.ENDC}\n")

    return True


def main():
    """Run all memory tests."""
    print_test_header("TimerMind Memory Watcher Test Suite")
    print(f"Base URL: {BASE_URL}")
    print(f"Session ID: {SESSION_ID or '(will be created)'}\n")

    results = []

    # Test 1: Home address memory
    try:
        results.append(("Home Address Memory", test_memory_creation()))
    except Exception as e:
        print(f"{Colors.FAIL}❌ Test failed with error: {e}{Colors.ENDC}")
        results.append(("Home Address Memory", False))

    # Test 2: Preference memory
    try:
        results.append(("Preference Memory", test_preference_memory()))
    except Exception as e:
        print(f"{Colors.FAIL}❌ Test failed with error: {e}{Colors.ENDC}")
        results.append(("Preference Memory", False))

    # Summary
    print_test_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = f"{Colors.OKGREEN}✓ PASS{Colors.ENDC}" if result else f"{Colors.FAIL}✗ FAIL{Colors.ENDC}"
        print(f"  {test_name:30s} {status}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print(f"\n{Colors.OKGREEN}🎉 All memory tests passed!{Colors.ENDC}\n")
        return 0
    else:
        print(f"\n{Colors.FAIL}❌ Some tests failed{Colors.ENDC}\n")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.FAIL}Tests interrupted by user{Colors.ENDC}")
        exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}Error running tests: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        exit(1)
