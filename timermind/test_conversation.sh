#!/bin/bash

# TimerMind Conversation Test Script
BASE_URL="http://127.0.0.1:8000"
SESSION_ID="test_$(date +%s)"

echo "=== Starting TimerMind Conversation Test ==="
echo "Session ID: $SESSION_ID"
echo ""

# Function to send message and display response
send_message() {
    local message="$1"
    echo "USER: $message"
    echo ""
    
    response=$(curl -s -X POST "$BASE_URL/chat" \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"$message\", \"session_id\": \"$SESSION_ID\"}")
    
    echo "ASSISTANT: $(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['response'])")"
    echo ""
    echo "---"
    echo ""
    
    # Wait a moment between messages
    sleep 2
}

# Start conversation
send_message "I need to do five things today"

# List the five things
send_message "Take willem to school, listen to the philanthropy call, go to the doctor, pick Willem up from school, and go to the comedy show."

# Now wait for questions and respond with facts
# This will require manual intervention to see what questions are asked
# Let's do a few rounds of passive responses

echo "=== Waiting for system questions... ==="
echo "The script will now wait. Please check the web interface to see what questions are being asked."
echo "Or continue with curl commands manually:"
echo ""
echo "curl -X POST $BASE_URL/chat -H 'Content-Type: application/json' -d '{\"message\": \"RESPONSE\", \"session_id\": \"$SESSION_ID\"}'"

