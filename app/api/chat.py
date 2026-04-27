from __future__ import annotations

import asyncio
import functools
import json
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from app.agent.loop import MaxIterationsExceeded, run_agent, stream_agent
from app.agent.sync_loop import (
    MaxIterationsExceeded as SyncMaxIterationsExceeded,
    run_agent_sync,
    stream_agent_sync,
)
from app.models import ChatRequest, ChatResponse, Message
from app.session_store import append_messages, get_history

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Run the agentic loop and return the final answer as JSON."""
    session_id = request.session_id

    # Build full message list (history + new messages)
    if session_id:
        history = await get_history(session_id)
        messages = history + request.messages
    else:
        messages = list(request.messages)

    try:
        reply, tool_calls_made = await run_agent(
            messages=messages,
            max_iterations=request.max_iterations,
        )
    except MaxIterationsExceeded as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Persist conversation if a session is active
    if session_id:
        new_messages = list(request.messages) + [
            Message(role="assistant", content=reply)
        ]
        await append_messages(session_id, new_messages)

    return ChatResponse(
        reply=reply,
        tool_calls_made=tool_calls_made,
        session_id=session_id,
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Run the agentic loop and stream the response as Server-Sent Events."""
    session_id = request.session_id

    if session_id:
        history = await get_history(session_id)
        messages = history + request.messages
    else:
        messages = list(request.messages)

    async def event_generator():
        full_reply_parts: list[str] = []
        async for chunk in stream_agent(
            messages=messages,
            max_iterations=request.max_iterations,
        ):
            if chunk.startswith("event: token"):
                # Token data is JSON-encoded; decode to get the raw text.
                data_json = chunk.split("data: ", 1)[1].rstrip("\n")
                full_reply_parts.append(json.loads(data_json))
            yield chunk

        # Persist after streaming is complete
        if session_id:
            reply = "".join(full_reply_parts)
            new_messages = list(request.messages) + [
                Message(role="assistant", content=reply)
            ]
            await append_messages(session_id, new_messages)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/session", response_model=ChatResponse)
async def chat_with_new_session(request: ChatRequest) -> ChatResponse:
    """Like POST /chat but automatically creates and returns a new session_id."""
    new_id = str(uuid.uuid4())
    request_with_session = request.model_copy(update={"session_id": new_id})
    return await chat(request_with_session)


@router.post("/sync", response_model=ChatResponse)
async def chat_sync(request: ChatRequest) -> ChatResponse:
    """Run the synchronous agentic loop in a thread pool and return the final answer.

    Offloads ``run_agent_sync`` to the default ``ThreadPoolExecutor`` so the
    asyncio event-loop is never blocked.
    """
    session_id = request.session_id

    if session_id:
        history = await get_history(session_id)
        messages = history + request.messages
    else:
        messages = list(request.messages)

    loop = asyncio.get_event_loop()
    fn = functools.partial(
        run_agent_sync,
        messages=messages,
        max_iterations=request.max_iterations,
    )
    try:
        reply, tool_calls_made = await loop.run_in_executor(None, fn)
    except SyncMaxIterationsExceeded as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if session_id:
        new_messages = list(request.messages) + [
            Message(role="assistant", content=reply)
        ]
        await append_messages(session_id, new_messages)

    return ChatResponse(
        reply=reply,
        tool_calls_made=tool_calls_made,
        session_id=session_id,
    )


@router.post("/sync/stream")
async def chat_sync_stream(request: ChatRequest) -> StreamingResponse:
    """Stream the synchronous agentic loop as Server-Sent Events.

    ``stream_agent_sync`` is a blocking generator; it is adapted to an async
    context via Starlette's ``iterate_in_threadpool``, which runs each
    ``next()`` call in the default thread pool so the event-loop stays free.
    """
    session_id = request.session_id

    if session_id:
        history = await get_history(session_id)
        messages = history + request.messages
    else:
        messages = list(request.messages)

    full_reply_parts: list[str] = []

    async def event_generator():
        async for chunk in iterate_in_threadpool(
            stream_agent_sync(
                messages=messages,
                max_iterations=request.max_iterations,
            )
        ):
            if chunk.startswith("event: token"):
                data_json = chunk.split("data: ", 1)[1].rstrip("\n")
                full_reply_parts.append(json.loads(data_json))
            yield chunk

        if session_id:
            reply = "".join(full_reply_parts)
            new_messages = list(request.messages) + [
                Message(role="assistant", content=reply)
            ]
            await append_messages(session_id, new_messages)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
