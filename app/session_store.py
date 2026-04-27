"""In-memory session store.

Stores conversation history keyed by session_id. In production you can swap
this out for a Redis or database-backed implementation.

Note: This store uses asyncio.Lock for safe concurrent access when running
with a single-process ASGI server. For multi-process deployments, use an
external store such as Redis.
"""
from __future__ import annotations

import asyncio

from app.models import Message

_store: dict[str, list[Message]] = {}
_lock = asyncio.Lock()


async def get_history(session_id: str) -> list[Message]:
    async with _lock:
        return list(_store.get(session_id, []))


async def append_messages(session_id: str, messages: list[Message]) -> None:
    async with _lock:
        if session_id not in _store:
            _store[session_id] = []
        _store[session_id].extend(messages)


async def clear_session(session_id: str) -> None:
    async with _lock:
        _store.pop(session_id, None)
