#!/usr/bin/env python3
"""
LLM-powered automated conversation test for TimerMind
Uses an LLM to intelligently respond with minimal information
"""

import requests
import json
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
SESSION_ID = None  # Will be set after first request

# Knowledge base - facts that can be shared when asked
KNOWLEDGE_BASE = """
FACTS ABOUT TODAY'S TASKS:
- Willem's school: Bellarmine College Prep in San Jose
- School arrival time: Willem needs to be there by 8:15AM
- School pickup time: 2:45PM
- Doctor appointment time: 1:15PM
- Doctor location: 401 Old San Francisco Road, Sunnyvale CA 94086
- Doctor appointment time: 1:15PM
- Home address: 12688 Kinman Ct, 95070
- Comedy show venue: The Punch Line in SF
- Comedy show start time: 8PM
- Philanthropy call: Starts at 9AM, lasts 1 hour, can do from phone anywhere
"""

def send_message(message, verbose=True):
    """Send a message to TimerMind and return the response"""
    global SESSION_ID

    if verbose:
        print(f"\n{'='*80}")
        print(f"USER: {message}")
        print(f"{'='*80}\n")

    try:
        # Build request payload
        payload = {"message": message}
        if SESSION_ID:
            payload["session_id"] = SESSION_ID

        response = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
        assistant_message = data.get('response', '')

        # Capture session_id from first response
        if not SESSION_ID and 'session_id' in data:
            SESSION_ID = data['session_id']
            print(f"[Session created: {SESSION_ID}]")

        if verbose:
            print(f"TIMERMIND: {assistant_message}\n")

        return assistant_message
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def get_minimal_response(system_message):
    """Use OpenAI to generate a minimal response based on what's being asked"""

    # Use OpenAI API
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY not set")
        return None

    prompt = f"""You are helping test a task management system. The system just sent this message:

"{system_message}"

You have access to these facts:
{KNOWLEDGE_BASE}

Your job: Respond with ONLY the minimal information being requested. Do not volunteer additional information that hasn't been asked for yet.

Rules:
1. If asked about a location/address, provide only that location
2. If asked about a time, provide only that time
3. If asked about multiple things, provide all of them
4. Keep responses natural and conversational but minimal
5. Don't add information that wasn't requested

Examples:
- If asked "Where is the school?", respond: "Bellarmine College Prep in San Jose"
- If asked "What time does he need to be there?", respond: "8:15AM"
- If asked "What's your home address?", respond: "12688 Kinman Ct, 95070"

Now respond to the system's message with only the minimal information requested:"""

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4",
                "max_tokens": 150,
                "messages": [{
                    "role": "user",
                    "content": prompt
                }]
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        assistant_response = data['choices'][0]['message']['content'].strip()
        print(f"[LLM generated response: {assistant_response}]")
        return assistant_response

    except Exception as e:
        print(f"ERROR calling OpenAI API: {e}")
        return None

def run_automated_test():
    """Run the full automated test"""
    print(f"\n{'#'*80}")
    print(f"# TIMERMIND LLM-POWERED AUTOMATED TEST")
    print(f"# Session will be created on first request")
    print(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*80}\n")

    # Initial message
    response = send_message("I need to do five things tomorrow")
    time.sleep(2)

    # List the five things
    response = send_message(
        "Take willem to school, listen to the philanthropy call, go to the doctor, "
        "pick Willem up from school, and go to the comedy show."
    )
    time.sleep(2)

    # Now respond intelligently to questions
    max_iterations = 20
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Check if there's a question or request in the response
        if response and ('?' in response or any(word in response.lower() for word in
            ['what', 'where', 'when', 'address', 'time', 'need', 'provide', 'tell me'])):

            # Use LLM to generate minimal response
            minimal_response = get_minimal_response(response)

            if minimal_response:
                response = send_message(minimal_response)
                time.sleep(2)
            else:
                print(f"[Could not generate response]")
                break
        else:
            print(f"\n{'='*80}")
            print(f"CONVERSATION ENDED (no more questions detected)")
            print(f"Last message: {response[:200] if response else 'None'}...")
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
