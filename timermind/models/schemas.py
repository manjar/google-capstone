"""
Pydantic models for API request/response schemas.
"""

from typing import Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    timers: list
    session_id: Optional[str] = None
    execution_trace: list = []  # List of execution events for thought process visibility


class TimerUpdateRequest(BaseModel):
    status: Optional[str] = None
    category: Optional[str] = None
    deadline: Optional[str] = None


class MemoriesRequest(BaseModel):
    session_id: Optional[str] = None
