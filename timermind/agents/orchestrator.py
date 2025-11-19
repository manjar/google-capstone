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
from agents.planner_agent import planner_agent
from tools.timer_tools import get_current_timers_tool
from utils.logging import log_event


# Callback to automatically save sessions to memory
async def auto_save_to_memory(callback_context):
    """Automatically save session to memory after each agent turn."""
    await callback_context._invocation_context.memory_service.add_session_to_memory(
        callback_context._invocation_context.session
    )


# Root Agent (Orchestrator)
root_agent = Agent(
    name="timermind_orchestrator",
    model="gemini-2.5-flash",
    description="Orchestrates task extraction and preference learning for TimerMind",
    instruction="""
You are TimerMind, the main orchestrator agent for personal task prioritization.

You have specialized sub-agents:
1. **planner_agent**: Manages multi-task workflows and ensures no tasks are forgotten
2. **location_agent**: Handles location-based tasks with travel time calculations
3. **task_parser_agent**: Handles single timer operations (create, update, delete, query)
4. **preference_agent**: Learns user preferences for prioritization

Your job is to:
1. Understand what the user wants
2. Delegate to the appropriate sub-agent
3. Synthesize responses and provide a unified experience

Delegation guidelines:
- Multiple tasks in one message → planner_agent (CRITICAL: ensures nothing is forgotten)
- Location-based tasks ("go to", "arrive at", "leave for") → location_agent
- Single tasks without locations → task_parser_agent
- Preferences/priorities/learning → preference_agent
- Just viewing timers → get_current_timers_tool directly

Examples:
- "Tomorrow I need to go to the grocery store, appointment in Los Altos at 4PM, then movie in Fremont at 5:30PM" → planner_agent
- "Leave for dentist in Campbell by 2pm" → location_agent
- "I need to finish the report by Friday" → task_parser_agent
- "Between getting mail and picking up Willem, I need lunch" → task_parser_agent
- "Health is my top priority" → preference_agent
- "What timers do I have?" → get_current_timers_tool

Keep it simple:
- Multiple tasks → planner_agent
- Locations → location_agent
- Single tasks → task_parser_agent
- Preferences → preference_agent

Today is {today}.
""".format(today=datetime.now().strftime("%A, %B %d, %Y")),
    tools=[get_current_timers_tool],
    sub_agents=[planner_agent, task_parser_agent, location_agent, preference_agent],
    after_agent_callback=auto_save_to_memory
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
    "sub_agents": ["planner_agent", "task_parser_agent", "location_agent", "preference_agent"],
    "planner_tools": ["create_task_list_tool", "get_task_list_tool", "update_task_status_tool", "add_task_tool", "remove_task_tool", "update_task_metadata_tool", "get_projected_location_tool", "clear_task_list_tool"],
    "task_parser_tools": ["create_timer_tool", "get_current_timers_tool", "update_timer_tool"],
    "location_tools": ["calculate_travel_time_tool", "create_timer_tool", "get_current_timers_tool", "update_timer_tool"],
    "preference_tools": ["get_user_preferences_tool", "add_preference_rule_tool", "set_default_location_tool", "get_current_timers_tool", "recalculate_timer_importance_tool", "load_memory", "preload_memory"],
    "session_service": "InMemorySessionService",
    "memory_service": "InMemoryMemoryService (Google ADK memory banks)",
    "model": "gemini-2.5-flash"
})
