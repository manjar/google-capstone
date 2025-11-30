#!/usr/bin/env python3
"""
Automated conversation test for TimerMind
Tests the continuous prompting behavior with a 5-task scenario
"""

import requests
import json
import time
import re
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = f"test_{int(time.time())}"

# Knowledge base for responding to questions
FACTS = {
    "school": "Bellarmine College Prep in San Jose",
    "school_time": "8:15AM",
    "pickup_time": "2:45",
    "doctor_time": "1:15",
    "doctor_address": "401 Old San Francisco Road, Sunnyvale CA 94086",
    "home": "12688 Kinman Ct, 95070",
    "comedy_venue": "at the punch line in sf",
    "call_time": "9AM",
    "call_duration": "an hour"
}

def send_message(message, verbose=True):
    """Send a message to TimerMind and return the response"""
    if verbose:
        print(f"\n{'='*80}")
        print(f"USER: {message}")
        print(f"{'='*80}\n")

    try:
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={"message": message, "session_id": SESSION_ID},
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
        assistant_message = data.get('response', '')

        if verbose:
            print(f"ASSISTANT: {assistant_message}\n")

        return assistant_message
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def detect_question_type(message):
    """Detect what type of question is being asked"""
    message_lower = message.lower()

    # School-related questions
    if any(word in message_lower for word in ['school', 'willem']):
        if any(word in message_lower for word in ['address', 'where', 'location']):
            return 'school'
        elif any(word in message_lower for word in ['time', 'when', 'by']):
            if 'pick' in message_lower or 'pickup' in message_lower:
                return 'pickup_time'
            else:
                return 'school_time'

    # Doctor-related questions
    if 'doctor' in message_lower:
        if any(word in message_lower for word in ['address', 'where', 'location']):
            return 'doctor_address'
        elif any(word in message_lower for word in ['time', 'when']):
            return 'doctor_time'

    # Home address questions
    if any(word in message_lower for word in ['home', 'starting', 'origin', 'from where']):
        return 'home'

    # Comedy show questions
    if any(word in message_lower for word in ['comedy', 'show', 'punch line']):
        if any(word in message_lower for word in ['where', 'location', 'address']):
            return 'comedy_venue'

    # Philanthropy call questions
    if any(word in message_lower for word in ['call', 'philanthropy']):
        if any(word in message_lower for word in ['time', 'when', 'start']):
            return 'call_time'
        elif any(word in message_lower for word in ['long', 'duration', 'last']):
            return 'call_duration'

    return None

def get_answer(question_type):
    """Get the appropriate answer based on question type"""
    answers = {
        'school': FACTS['school'],
        'school_time': f"He needs to be there by {FACTS['school_time']}",
        'pickup_time': FACTS['pickup_time'],
        'doctor_address': FACTS['doctor_address'],
        'doctor_time': FACTS['doctor_time'],
        'home': f"Home is {FACTS['home']}",
        'comedy_venue': f"The comedy show is {FACTS['comedy_venue']}",
        'call_time': f"The call starts at {FACTS['call_time']}",
        'call_duration': f"It should last {FACTS['call_duration']}"
    }
    return answers.get(question_type, None)

def run_automated_test():
    """Run the full automated test"""
    print(f"\n{'#'*80}")
    print(f"# TIMERMIND AUTOMATED CONVERSATION TEST")
    print(f"# Session ID: {SESSION_ID}")
    print(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*80}\n")

    # Initial message
    response = send_message("I need to do five things today")
    time.sleep(2)

    # List the five things
    response = send_message(
        "Take willem to school, listen to the philanthropy call, go to the doctor, "
        "pick Willem up from school, and go to the comedy show."
    )
    time.sleep(2)

    # Now respond to questions automatically
    max_iterations = 20
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Detect if there's a question in the response
        if response and '?' in response:
            question_type = detect_question_type(response)

            if question_type:
                answer = get_answer(question_type)
                if answer:
                    print(f"[Detected question type: {question_type}]")
                    response = send_message(answer)
                    time.sleep(2)
                else:
                    print(f"[No answer found for question type: {question_type}]")
                    break
            else:
                print(f"[Could not detect question type from response]")
                print(f"[Response: {response[:200]}...]")
                break
        else:
            print(f"\n{'='*80}")
            print(f"CONVERSATION ENDED (no more questions)")
            print(f"{'='*80}\n")
            break

    if iteration >= max_iterations:
        print(f"\n{'='*80}")
        print(f"TEST STOPPED: Reached maximum iterations ({max_iterations})")
        print(f"{'='*80}\n")

    print(f"\n{'#'*80}")
    print(f"# TEST COMPLETE")
    print(f"# Total iterations: {iteration}")
    print(f"{'#'*80}\n")

if __name__ == "__main__":
    run_automated_test()
