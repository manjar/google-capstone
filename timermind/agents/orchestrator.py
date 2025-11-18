"""
Root Orchestrator Agent for TimerMind.

This agent coordinates between all sub-agents and manages the agent workflow.
"""

from datetime import datetime
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from agents.task_parser_agent import task_parser_agent
from agents.location_agent import location_agent
from agents.preference_agent import preference_agent
from tools.timer_tools import get_current_timers_tool
from utils.logging import log_event


# Root Agent (Orchestrator)
root_agent = Agent(
    name="timermind_orchestrator",
    model="gemini-2.5-flash",
    description="Orchestrates task extraction and preference learning for TimerMind",
    instruction="""
You are TimerMind, the main orchestrator agent for personal task prioritization.

You have two specialized sub-agents:
1. **extraction_agent**: Handles all timer operations (create, update, delete, query)
2. **preference_agent**: Learns user preferences for prioritization

Your job is to:
1. Understand what the user wants
2. Delegate to the appropriate sub-agent
3. Synthesize responses and provide a unified experience

Delegation guidelines:
- Location-based tasks ("go to", "arrive at", "leave for") → location_agent
- Simple tasks without locations → task_parser_agent
- Preferences/priorities/learning → preference_agent
- Just viewing timers → get_current_timers_tool directly

Examples:
- "Leave for dentist in Campbell by 2pm" → location_agent
- "I need to finish the report by Friday" → task_parser_agent
- "Between getting mail and picking up Willem, I need lunch" → task_parser_agent
- "Health is my top priority" → preference_agent
- "What timers do I have?" → get_current_timers_tool

Keep it simple:
- Locations → location_agent
- Tasks → task_parser_agent
- Preferences → preference_agent

Today is {today}.
""".format(today=datetime.now().strftime("%A, %B %d, %Y")),
    tools=[get_current_timers_tool],
    sub_agents=[task_parser_agent, location_agent, preference_agent]
)


# Create session and memory services (Google ADK)
# Session: conversation history (using InMemory for demo, can upgrade to persistent)
# Memory: long-term facts, preferences, learned information
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()


# Create runner for agent execution
runner = Runner(
    agent=root_agent,
    app_name="timermind",
    session_service=session_service,
    memory_service=memory_service
)


log_event("adk_multi_agent_initialized", {
    "root_agent": "timermind_orchestrator",
    "sub_agents": ["task_parser_agent", "location_agent", "preference_agent"],
    "task_parser_tools": ["create_timer_tool", "get_current_timers_tool", "update_timer_tool"],
    "location_tools": ["calculate_travel_time_tool", "create_timer_tool", "get_current_timers_tool", "update_timer_tool"],
    "preference_tools": ["get_user_preferences_tool", "add_preference_rule_tool", "set_default_location_tool", "get_current_timers_tool", "recalculate_timer_importance_tool", "load_memory", "preload_memory"],
    "session_service": "InMemorySessionService",
    "memory_service": "InMemoryMemoryService (Google ADK memory banks)",
    "model": "gemini-2.5-flash"
})
