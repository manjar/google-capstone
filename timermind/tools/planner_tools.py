"""
Planner tools for managing multi-task workflows.

Handles task extraction, tracking, and coordination across
the multi-agent system.
"""

import json
from datetime import datetime, timezone
from typing import Optional
from utils.logging import log_event


# In-memory task store (in production, this would use ADK memory banks)
_task_store = {}


def create_task_list_tool(
    session_id: str,
    user_message: str,
    initial_tasks: str  # JSON string of task list
) -> dict:
    """
    Create a new task list from user's multi-task request.
    
    Args:
        session_id: Unique session identifier
        user_message: Original user message
        initial_tasks: JSON string containing list of task objects
        
    Returns:
        Status and created task list
    """
    try:
        tasks = json.loads(initial_tasks)

        # Ensure all tasks have an ID field
        for i, task in enumerate(tasks):
            if "id" not in task:
                task["id"] = i + 1
            if "created_at" not in task:
                task["created_at"] = datetime.now(timezone.utc).isoformat()
            if "updated_at" not in task:
                task["updated_at"] = datetime.now(timezone.utc).isoformat()

        _task_store[session_id] = {
            "tasks": tasks,
            "user_message": user_message,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        log_event("task_list_created", {
            "session_id": session_id,
            "task_count": len(tasks),
            "tasks": tasks
        })
        
        return {
            "success": True,
            "task_count": len(tasks),
            "tasks": tasks,
            "message": f"Created task list with {len(tasks)} tasks"
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON format: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error creating task list: {str(e)}"
        }


def get_task_list_tool(session_id: str) -> dict:
    """Get the current task list for a session."""
    if session_id not in _task_store:
        return {
            "success": True,
            "tasks": [],
            "message": "No active task list"
        }
    
    task_data = _task_store[session_id]
    pending_tasks = [t for t in task_data["tasks"] if t["status"] == "pending"]
    in_progress_tasks = [t for t in task_data["tasks"] if t["status"] == "in_progress"]
    completed_tasks = [t for t in task_data["tasks"] if t["status"] == "completed"]
    
    return {
        "success": True,
        "tasks": task_data["tasks"],
        "pending_count": len(pending_tasks),
        "in_progress_count": len(in_progress_tasks),
        "completed_count": len(completed_tasks),
        "total_count": len(task_data["tasks"])
    }


def update_task_status_tool(
    session_id: str,
    task_id: int,
    new_status: str,  # pending, in_progress, completed, cancelled
    notes: Optional[str] = None
) -> dict:
    """Update the status of a specific task."""
    if session_id not in _task_store:
        return {"success": False, "error": "No task list found for session"}
    
    task_data = _task_store[session_id]
    task = next((t for t in task_data["tasks"] if t["id"] == task_id), None)
    
    if not task:
        return {"success": False, "error": f"Task {task_id} not found"}
    
    old_status = task["status"]
    task["status"] = new_status
    task["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    if notes:
        if "notes" not in task:
            task["notes"] = []
        task["notes"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "text": notes
        })
    
    task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    log_event("task_status_updated", {
        "session_id": session_id,
        "task_id": task_id,
        "old_status": old_status,
        "new_status": new_status,
        "task_label": task["label"]
    })

    # Calculate remaining tasks by status
    pending_tasks = [t for t in task_data["tasks"] if t["status"] == "pending"]
    ready_tasks = [t for t in task_data["tasks"] if t["status"] == "ready"]
    completed_tasks = [t for t in task_data["tasks"] if t["status"] == "completed"]
    abandoned_tasks = [t for t in task_data["tasks"] if t["status"] == "abandoned"]

    return {
        "success": True,
        "task_id": task_id,
        "old_status": old_status,
        "new_status": new_status,
        "task": task,
        "remaining_summary": {
            "pending_count": len(pending_tasks),
            "ready_count": len(ready_tasks),
            "completed_count": len(completed_tasks),
            "abandoned_count": len(abandoned_tasks),
            "total_count": len(task_data["tasks"]),
            "next_pending_task": pending_tasks[0] if pending_tasks else None,
            "next_ready_task": ready_tasks[0] if ready_tasks else None
        }
    }


def add_task_tool(
    session_id: str,
    task_data: str,  # JSON string of new task
    insert_after_id: Optional[int] = None
) -> dict:
    """
    Add a new task to the list.
    
    Args:
        session_id: Session identifier
        task_data: JSON string of task object
        insert_after_id: Optional task ID to insert after (for ordering)
    """
    if session_id not in _task_store:
        return {"success": False, "error": "No task list found for session"}
    
    try:
        new_task = json.loads(task_data)
        task_list_data = _task_store[session_id]
        
        # Assign new ID
        existing_ids = [t["id"] for t in task_list_data["tasks"]]
        new_task["id"] = max(existing_ids) + 1 if existing_ids else 1
        new_task["created_at"] = datetime.now(timezone.utc).isoformat()
        new_task["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Insert at the right position
        if insert_after_id:
            insert_index = next(
                (i + 1 for i, t in enumerate(task_list_data["tasks"]) if t["id"] == insert_after_id),
                len(task_list_data["tasks"])
            )
            task_list_data["tasks"].insert(insert_index, new_task)
        else:
            task_list_data["tasks"].append(new_task)
        
        task_list_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        log_event("task_added", {
            "session_id": session_id,
            "task_id": new_task["id"],
            "task_label": new_task["label"]
        })
        
        return {
            "success": True,
            "task": new_task,
            "message": f"Added task: {new_task['label']}"
        }
    except Exception as e:
        return {"success": False, "error": f"Error adding task: {str(e)}"}


def remove_task_tool(
    session_id: str,
    task_id: int,
    reason: Optional[str] = None
) -> dict:
    """Remove a task from the list."""
    if session_id not in _task_store:
        return {"success": False, "error": "No task list found for session"}
    
    task_data = _task_store[session_id]
    task = next((t for t in task_data["tasks"] if t["id"] == task_id), None)
    
    if not task:
        return {"success": False, "error": f"Task {task_id} not found"}
    
    task_data["tasks"] = [t for t in task_data["tasks"] if t["id"] != task_id]
    task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    log_event("task_removed", {
        "session_id": session_id,
        "task_id": task_id,
        "task_label": task["label"],
        "reason": reason
    })
    
    return {
        "success": True,
        "removed_task": task,
        "message": f"Removed task: {task['label']}"
    }


def update_task_metadata_tool(
    session_id: str,
    task_id: int,
    metadata_updates: str  # JSON string of metadata fields to update
) -> dict:
    """Update task metadata (deadline, location, etc.)."""
    if session_id not in _task_store:
        return {"success": False, "error": "No task list found for session"}
    
    try:
        updates = json.loads(metadata_updates)
        task_data = _task_store[session_id]
        task = next((t for t in task_data["tasks"] if t["id"] == task_id), None)
        
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}
        
        # Update metadata
        if "metadata" not in task:
            task["metadata"] = {}
        
        task["metadata"].update(updates)
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        task_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        log_event("task_metadata_updated", {
            "session_id": session_id,
            "task_id": task_id,
            "updates": updates
        })
        
        return {
            "success": True,
            "task": task,
            "message": "Task metadata updated"
        }
    except Exception as e:
        return {"success": False, "error": f"Error updating metadata: {str(e)}"}


def clear_task_list_tool(session_id: str) -> dict:
    """Clear/complete the task list for a session."""
    if session_id in _task_store:
        task_data = _task_store[session_id]
        completed_count = len([t for t in task_data["tasks"] if t["status"] == "completed"])
        total_count = len(task_data["tasks"])

        del _task_store[session_id]

        log_event("task_list_cleared", {
            "session_id": session_id,
            "completed_count": completed_count,
            "total_count": total_count
        })

        return {
            "success": True,
            "message": f"Task list cleared. Completed {completed_count}/{total_count} tasks."
        }

    return {"success": True, "message": "No task list to clear"}


def get_projected_location_tool(session_id: str, task_id: int) -> dict:
    """
    Get the projected location of the user after completing a specific task.

    This helps determine where the user will be for subsequent tasks.

    Args:
        session_id: Session identifier
        task_id: ID of the task to check

    Returns:
        The destination/location where user will be after this task
    """
    if session_id not in _task_store:
        return {"success": False, "error": "No task list found for session"}

    task_data = _task_store[session_id]
    task = next((t for t in task_data["tasks"] if t["id"] == task_id), None)

    if not task:
        return {"success": False, "error": f"Task {task_id} not found"}

    # Check if task has location metadata
    if "metadata" in task and "destination" in task["metadata"]:
        return {
            "success": True,
            "location": task["metadata"]["destination"],
            "task_id": task_id,
            "task_label": task["label"]
        }

    # If no destination, user stays at origin or home
    if "metadata" in task and "origin" in task["metadata"]:
        return {
            "success": True,
            "location": task["metadata"]["origin"],
            "task_id": task_id,
            "task_label": task["label"],
            "note": "Task has no destination, user remains at origin"
        }

    return {
        "success": True,
        "location": None,
        "task_id": task_id,
        "task_label": task["label"],
        "note": "Task has no location information"
    }
