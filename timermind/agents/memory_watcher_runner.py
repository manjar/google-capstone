"""
Memory Watcher Runner Setup.

Creates a dedicated runner for the memory watcher agent that runs in parallel
with the main conversation to capture notable facts.
"""

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from agents.memory_watcher_agent import memory_watcher_agent
from utils.logging import log_event


# Share the same session and memory services as the main orchestrator
# This ensures memories are stored in the same memory bank
from agents.orchestrator import session_service, memory_service


# Create runner for memory watcher
memory_watcher_runner = Runner(
    agent=memory_watcher_agent,
    app_name="timermind",
    session_service=session_service,  # Shared with main orchestrator
    memory_service=memory_service     # Shared with main orchestrator
)


log_event("memory_watcher_runner_initialized", {
    "agent": "memory_watcher",
    "model": "gemini-2.5-flash",
    "session_service": "Shared InMemorySessionService",
    "memory_service": "Shared InMemoryMemoryService"
})
