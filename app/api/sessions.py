from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import SessionHistoryResponse
from app.session_store import clear_session, get_history

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=SessionHistoryResponse)
async def get_session(session_id: str) -> SessionHistoryResponse:
    """Return the full conversation history for a session."""
    history = await get_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail="Session not found.")
    return SessionHistoryResponse(session_id=session_id, messages=history)


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    """Delete a session and its conversation history."""
    await clear_session(session_id)
