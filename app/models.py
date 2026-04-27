from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChatRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1)
    session_id: str | None = Field(
        default=None,
        description="Optional session ID. When provided, the server stores and "
        "reuses the conversation history for that session.",
    )
    max_iterations: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Override the default maximum number of agent iterations.",
    )


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result: str


class ChatResponse(BaseModel):
    reply: str
    tool_calls_made: list[ToolCallRecord] = []
    session_id: str | None = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[Message]
