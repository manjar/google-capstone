"""
FastAPI route handlers for TimerMind.

This module contains all API endpoints for the TimerMind application.
"""

import sqlite3
import traceback
from datetime import datetime
from typing import Optional
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from google.genai import types
from jinja2 import Environment, FileSystemLoader

from config import DB_PATH, TEMPLATES_DIR
from models.schemas import ChatRequest, ChatResponse, TimerUpdateRequest, MemoriesRequest
from database.operations import list_timers_from_db
from tools.timer_tools import update_timer_tool
from tools.preference_tools import get_user_preferences_tool
from tools.planner_tools import _task_store  # For enforcement loop
from utils.logging import log_event


# Maximum continuation attempts to prevent infinite loops
MAX_CONTINUATION_ATTEMPTS = 10


def check_pending_tasks(session_id: str) -> tuple[bool, int, list]:
    """
    Check if there are pending tasks for a session.

    Returns:
        Tuple of (has_pending, pending_count, pending_task_labels)
    """
    if session_id not in _task_store:
        return False, 0, []

    task_data = _task_store[session_id]
    pending_tasks = [
        t for t in task_data["tasks"]
        if t["status"] in ("pending", "in_progress", "ready")
    ]
    pending_labels = [t["label"] for t in pending_tasks]
    return len(pending_tasks) > 0, len(pending_tasks), pending_labels


def response_asks_question(response_text: str) -> bool:
    """
    Check if the response ends with a question (heuristic for proper prompting).
    """
    # Strip and check for question mark
    stripped = response_text.strip()
    if stripped.endswith("?"):
        return True

    # Check last sentence for question patterns
    last_sentences = stripped.split(".")[-1].strip()
    question_starters = ["what", "when", "where", "how", "which", "would", "do", "does", "is", "are", "can", "could"]
    lower_last = last_sentences.lower()
    return any(lower_last.startswith(q) for q in question_starters) or "?" in last_sentences


# Jinja2 template environment
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def register_routes(app, runner, memory_watcher_runner):
    """
    Register all FastAPI routes with the application.

    Args:
        app: FastAPI application instance
        runner: ADK Runner instance for agent execution
        memory_watcher_runner: ADK Runner for memory watcher agent (parallel memory capture)
    """

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve the TimerMind dashboard UI."""
        template = jinja_env.get_template("dashboard.html")
        return template.render()

    @app.get("/api/health")
    async def health():
        """Health check and API info."""
        return {
            "service": "TimerMind",
            "version": "0.1.0",
            "status": "running",
            "agent": "timermind",
            "model": "gemini-2.0-flash"
        }

    @app.get("/api/timers")
    async def get_timers():
        """Get all active timers sorted by priority."""
        timers = list_timers_from_db()
        return {"timers": timers, "count": len(timers)}

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """
        Send a message to the TimerMind agent using ADK Runner.

        The agent will:
        - Parse the message for task information
        - Create timers as needed (via function calling)
        - Return a conversational response
        """
        log_event("chat_request", {"message": request.message})

        try:
            # Get or create session
            user_id = "default_user"  # TODO: Implement proper user management
            session_id = request.session_id

            # Import session_service and memory_service from orchestrator
            from agents.orchestrator import session_service, memory_service

            if not session_id:
                # Create new session
                session = await session_service.create_session(
                    app_name="timermind",
                    user_id=user_id
                )
                session_id = session.id
                log_event("session_created", {"session_id": session_id, "user_id": user_id})
            else:
                # Get existing session
                session = await session_service.get_session(
                    app_name="timermind",
                    user_id=user_id,
                    session_id=session_id
                )
                log_event("session_retrieved", {"session_id": session_id})

            # Run the agent using ADK Runner
            # The runner handles:
            # - Sending message to agent
            # - Processing tool calls
            # - Managing conversation history in session
            response_text = ""
            execution_trace = []

            # Add initial orchestrator event
            execution_trace.append({
                "type": "OrchestrationStart",
                "timestamp": datetime.now().isoformat(),
                "event_category": "delegation",
                "agent": "timermind_orchestrator",
                "content_preview": f"Processing: {request.message[:80]}..."
            })

            # Inject current time and session context into the message
            current_datetime = datetime.now()
            time_context = f"[Current time: {current_datetime.strftime('%A, %B %d, %Y at %H:%M')}]\n"
            session_context = f"[Session ID: {session_id}]\n\n"
            message_with_context = time_context + session_context + request.message

            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=message_with_context)]
                )
            ):
                event_type = type(event).__name__

                # Log each event for observability with full details
                event_details = {
                    "event_type": event_type,
                    "session_id": session_id,
                    "has_agent": hasattr(event, "agent"),
                    "has_tool_call": hasattr(event, "tool_call"),
                    "has_content": hasattr(event, "content")
                }
                if hasattr(event, "agent") and event.agent:
                    event_details["agent_name"] = event.agent.name
                log_event("runner_event", event_details)

                # Build execution trace for frontend
                trace_event = {
                    "type": event_type,
                    "timestamp": datetime.now().isoformat()
                }

                # Capture relevant details based on event type
                if hasattr(event, "agent") and event.agent:
                    trace_event["agent"] = event.agent.name
                    trace_event["event_category"] = "delegation"
                    # Add explicit delegation message
                    trace_event["content_preview"] = f"Delegating to {event.agent.name}"

                if hasattr(event, "tool_call") and event.tool_call:
                    trace_event["event_category"] = "tool-call"
                    trace_event["tool_name"] = getattr(event.tool_call, "name", "unknown")

                if hasattr(event, "content") and event.content:
                    # Check for function calls in parts
                    has_function_call = False
                    if hasattr(event.content, "parts") and event.content.parts:
                        for part in event.content.parts:
                            # Extract function call information
                            if hasattr(part, "function_call") and part.function_call:
                                has_function_call = True
                                trace_event["event_category"] = "tool-call"
                                trace_event["tool_name"] = part.function_call.name
                                if hasattr(part.function_call, "args") and part.function_call.args:
                                    trace_event["tool_args"] = str(part.function_call.args)[:200]

                            # Extract text from response
                            if hasattr(part, "text") and part.text:
                                response_text += part.text
                                if not has_function_call:  # Only show text preview if not a function call
                                    if len(part.text) > 100:
                                        trace_event["content_preview"] = part.text[:100] + "..."
                                    else:
                                        trace_event["content_preview"] = part.text

                # Only add events that have meaningful information
                if ("event_category" in trace_event or
                    "content_preview" in trace_event or
                    "agent" in trace_event):
                    execution_trace.append(trace_event)

            if not response_text:
                response_text = "I processed your request."

            # ENFORCEMENT LOOP: Ensure all pending tasks are addressed
            # This catches cases where the planner stops prompting prematurely
            continuation_attempts = 0

            while continuation_attempts < MAX_CONTINUATION_ATTEMPTS:
                has_pending, pending_count, pending_labels = check_pending_tasks(session_id)

                if not has_pending:
                    # No pending tasks - we're done
                    log_event("enforcement_loop_complete", {
                        "session_id": session_id,
                        "reason": "no_pending_tasks",
                        "attempts": continuation_attempts
                    })
                    break

                if response_asks_question(response_text):
                    # Response ends with a question - agent is properly prompting
                    log_event("enforcement_loop_complete", {
                        "session_id": session_id,
                        "reason": "response_has_question",
                        "pending_count": pending_count,
                        "attempts": continuation_attempts
                    })
                    break

                # CRITICAL: Agent stopped prompting with pending tasks!
                # Force continuation by sending a system message
                log_event("enforcement_loop_forcing_continuation", {
                    "session_id": session_id,
                    "pending_count": pending_count,
                    "pending_tasks": pending_labels,
                    "attempt": continuation_attempts + 1
                })

                continuation_message = (
                    f"[SYSTEM: There are still {pending_count} pending task(s): {', '.join(pending_labels)}. "
                    f"You MUST ask the user about the next pending task. Do not stop until all tasks are complete.]"
                )

                # Add enforcement trace event
                execution_trace.append({
                    "type": "EnforcementLoop",
                    "timestamp": datetime.now().isoformat(),
                    "event_category": "enforcement",
                    "content_preview": f"Forcing continuation: {pending_count} pending tasks",
                    "pending_tasks": pending_labels
                })

                # Run agent again with continuation prompt
                continuation_response = ""
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part(text=continuation_message)]
                    )
                ):
                    # Capture response text from continuation
                    if hasattr(event, "content") and event.content:
                        if hasattr(event.content, "parts") and event.content.parts:
                            for part in event.content.parts:
                                if hasattr(part, "text") and part.text:
                                    continuation_response += part.text

                # Append continuation response (with separator for clarity)
                if continuation_response:
                    response_text = response_text.rstrip() + "\n\n" + continuation_response

                continuation_attempts += 1

            if continuation_attempts >= MAX_CONTINUATION_ATTEMPTS:
                log_event("enforcement_loop_max_attempts", {
                    "session_id": session_id,
                    "attempts": continuation_attempts,
                    "warning": "Max continuation attempts reached"
                })

            # Run memory watcher in parallel to capture notable facts
            # This runs silently and doesn't affect the user response
            log_event("memory_watcher_start", {"session_id": session_id})
            memory_watcher_events = []
            try:
                async for event in memory_watcher_runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part(text=request.message)]  # Use original message without time context
                    )
                ):
                    # Track all events from memory watcher for debugging
                    event_type = type(event).__name__
                    memory_watcher_events.append(event_type)

                    # Check for tool calls (function calls)
                    if hasattr(event, "content") and event.content:
                        if hasattr(event.content, "parts") and event.content.parts:
                            for part in event.content.parts:
                                if hasattr(part, "function_call") and part.function_call:
                                    tool_name = part.function_call.name
                                    log_event("memory_watcher_tool_call", {
                                        "tool": tool_name,
                                        "session_id": session_id
                                    })
                                if hasattr(part, "text") and part.text:
                                    # Log any text output from memory watcher
                                    log_event("memory_watcher_output", {
                                        "text": part.text[:200],
                                        "session_id": session_id
                                    })

                log_event("memory_watcher_complete", {
                    "session_id": session_id,
                    "events_count": len(memory_watcher_events),
                    "event_types": list(set(memory_watcher_events))
                })

                # NOTE: Session is automatically saved to memory via the orchestrator's
                # after_agent_callback - no manual save needed here!

            except Exception as e:
                # Don't let memory watcher errors break the main response
                log_event("memory_watcher_error", {"error": str(e)})

            # Get updated timers
            updated_timers = list_timers_from_db()

            log_event("chat_response", {
                "response_length": len(response_text),
                "timers_count": len(updated_timers),
                "session_id": session_id,
                "trace_events": len(execution_trace)
            })

            return ChatResponse(
                response=response_text,
                timers=updated_timers,
                session_id=session_id,
                execution_trace=execution_trace
            )

        except Exception as e:
            log_event("chat_error", {
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise HTTPException(status_code=500, detail=str(e))

    @app.patch("/api/timers/{timer_id}")
    async def update_timer(timer_id: int, request: TimerUpdateRequest):
        """Update a timer's properties."""
        result = update_timer_tool(
            timer_id=timer_id,
            status=request.status or "",
            category=request.category or "",
            deadline_iso=request.deadline or ""
        )
        return result

    @app.delete("/api/timers/{timer_id}")
    async def delete_timer(timer_id: int):
        """Delete a timer by ID."""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE timers SET status = 'deleted' WHERE id = ?", (timer_id,))
        log_event("timer_deleted", {"timer_id": timer_id})
        return {"status": "deleted", "timer_id": timer_id}

    @app.get("/api/preferences")
    async def get_preferences():
        """Get current user preferences."""
        prefs = get_user_preferences_tool()
        return prefs

    @app.post("/api/reset")
    async def reset_data():
        """
        Reset all data - clear timers and preferences.
        Useful for testing and starting fresh.
        """
        log_event("data_reset_requested", {})

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM timers")
            conn.execute("DELETE FROM preferences")

        log_event("data_reset_completed", {"timers_cleared": True, "preferences_cleared": True})
        return {"status": "reset", "message": "All timers and preferences cleared"}

    @app.post("/api/memories")
    async def get_memories(request: MemoriesRequest):
        """
        Retrieve memories from the Google ADK memory service for the current session.

        Returns:
            dict with list of memory objects
        """
        try:
            user_id = "default_user"
            session_id = request.session_id

            # Import memory_service from orchestrator
            from agents.orchestrator import memory_service

            if not session_id:
                return {"memories": [], "count": 0, "message": "No session ID provided"}

            # Query memories from the memory service using search_memory
            # We'll search for all memories by using a broad query
            memories_list = []

            try:
                # Use the memory service's search_memory method
                # NOTE: InMemoryMemoryService uses keyword matching - empty queries return nothing!
                # Use a broad query that will match common words in stored conversations
                search_response = await memory_service.search_memory(
                    app_name="timermind",
                    user_id=user_id,
                    query="user preferences address schedule tasks timers"  # Broad query to match stored content
                )

                # Extract memories from the search response
                if hasattr(search_response, 'memories') and search_response.memories:
                    for memory_chunk in search_response.memories:
                        # Each memory chunk has content
                        content = ""
                        if hasattr(memory_chunk, 'content'):
                            if hasattr(memory_chunk.content, 'parts'):
                                # Extract text from parts
                                for part in memory_chunk.content.parts:
                                    if hasattr(part, 'text'):
                                        content += part.text
                            elif hasattr(memory_chunk.content, 'text'):
                                content = memory_chunk.content.text
                            else:
                                content = str(memory_chunk.content)

                        # Get timestamp if available
                        created_at = datetime.now().isoformat()
                        if hasattr(memory_chunk, 'create_time'):
                            created_at = memory_chunk.create_time
                        elif hasattr(memory_chunk, 'timestamp'):
                            created_at = memory_chunk.timestamp

                        if content:
                            memories_list.append({
                                "content": content,
                                "created_at": created_at,
                                "type": "memory"
                            })

            except Exception as e:
                log_event("memory_retrieval_error", {"error": str(e), "type": type(e).__name__})
                # Return empty list with info message if search fails
                return {
                    "memories": [],
                    "count": 0,
                    "message": f"Could not retrieve memories: {str(e)}",
                    "info": "Memories are stored when you share preferences with the agent."
                }

            log_event("memories_retrieved", {
                "session_id": session_id,
                "user_id": user_id,
                "count": len(memories_list)
            })

            return {
                "memories": memories_list,
                "count": len(memories_list),
                "session_id": session_id
            }

        except Exception as e:
            log_event("memories_error", {
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
            raise HTTPException(status_code=500, detail=str(e))
