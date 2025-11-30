"""
Root Orchestrator Agent for TimerMind.

This agent coordinates between all sub-agents and manages the agent workflow.
"""

from datetime import datetime
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.tools import preload_memory
from agents.task_tracker_agent import task_tracker_agent
from tools.timer_tools import get_current_timers_tool
from utils.logging import log_event


# Callback to automatically save sessions to memory
async def auto_save_to_memory(callback_context):
    """Automatically save session to memory after each agent turn."""
    await callback_context._invocation_context.memory_service.add_session_to_memory(
        callback_context._invocation_context.session
    )


# Root Agent (Orchestrator) - Simple routing to task tracker
root_agent = Agent(
    name="timermind_orchestrator",
    model="gemini-2.5-flash",
    description="Routes requests to task tracker for TimerMind",
    instruction="""
You are TimerMind. Your job is simple: help users manage tasks.

When users mention tasks, delegate to task_tracker_agent.
For viewing timers, use get_current_timers_tool directly.

Examples:
- "I need to do five things tomorrow" → task_tracker_agent
- "Remind me about the dentist appointment" → task_tracker_agent
- "What timers do I have?" → get_current_timers_tool

Today is {today}.
""".format(today=datetime.now().strftime("%A, %B %d, %Y")),
    tools=[get_current_timers_tool, preload_memory],
    sub_agents=[task_tracker_agent],
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
    "architecture": "simplified",
    "agents": {
        "orchestrator": "Routes to task_tracker",
        "task_tracker": "Detects tasks, tracks state, asks questions (141 lines)",
        "timer_creator": "Creates timers from ready tasks (76 lines)",
        "context_agent": "Checks existing timers to avoid redundant questions",
        "location_agent": "Handles location-based timers with travel calculations"
    },
    "session_service": "InMemorySessionService",
    "memory_service": "InMemoryMemoryService (Google ADK memory banks)",
    "model": "gemini-2.5-flash"
})
