"""Agentic loop — repeatedly calls the LLM and executes tools until a final
text answer is produced or the iteration limit is reached.

Supports multiple LLM providers via LangChain (set ``LLM_PROVIDER`` in .env):
  - ``openai``  (default) — OpenAI ChatGPT
  - ``ollama``            — local Ollama models (OpenAI-compatible endpoint)
  - ``claude``            — Anthropic Claude
  - ``gemini``            — Google Gemini
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agent.llm_factory import get_chat_model
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS_SCHEMA, execute_tool
from app.config import settings
from app.models import Message, ToolCall, ToolCallFunction, ToolCallRecord


class MaxIterationsExceeded(RuntimeError):
    """Raised when the agent exceeds its maximum iteration count."""


# ---------------------------------------------------------------------------
# Message conversion helpers
# ---------------------------------------------------------------------------

def _to_langchain_messages(messages: list[Message]) -> list[BaseMessage]:
    """Convert Pydantic Message objects to LangChain message objects."""
    result: list[BaseMessage] = []
    for m in messages:
        if m.role == "system":
            result.append(SystemMessage(content=m.content or ""))
        elif m.role == "user":
            result.append(HumanMessage(content=m.content or ""))
        elif m.role == "assistant":
            if m.tool_calls:
                tc_list = [
                    {
                        "name": tc.function.name,
                        "args": json.loads(tc.function.arguments),
                        "id": tc.id,
                        "type": "tool_call",
                    }
                    for tc in m.tool_calls
                ]
                result.append(AIMessage(content=m.content or "", tool_calls=tc_list))
            else:
                result.append(AIMessage(content=m.content or ""))
        elif m.role == "tool":
            result.append(
                ToolMessage(
                    content=m.content or "",
                    tool_call_id=m.tool_call_id or "",
                )
            )
    return result


def _extract_text(content: Any) -> str:
    """Extract plain text from a LangChain message content value.

    Some providers (e.g. Claude) return a list of typed content blocks instead
    of a plain string.  This helper normalises both forms to a single string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


def _message_from_ai(response: AIMessage) -> Message:
    """Convert a LangChain AIMessage to our Pydantic Message model."""
    tool_calls = None
    if response.tool_calls:
        tool_calls = [
            ToolCall(
                id=tc["id"],
                type="function",
                function=ToolCallFunction(
                    name=tc["name"],
                    arguments=json.dumps(tc["args"]),
                ),
            )
            for tc in response.tool_calls
        ]
    content = _extract_text(response.content) or None
    return Message(role="assistant", content=content, tool_calls=tool_calls)


# ---------------------------------------------------------------------------
# Agentic loop — non-streaming
# ---------------------------------------------------------------------------

async def run_agent(
    messages: list[Message],
    max_iterations: int | None = None,
) -> tuple[str, list[ToolCallRecord]]:
    """Run the agentic loop and return ``(final_reply, tool_calls_made)``.

    Args:
        messages: Conversation history (user/assistant turns).
        max_iterations: Maximum number of LLM calls. Defaults to
            ``settings.agent_max_iterations``.
    """
    model = get_chat_model()
    model_with_tools = model.bind_tools(TOOLS_SCHEMA)
    limit = max_iterations or settings.agent_max_iterations
    tool_calls_made: list[ToolCallRecord] = []

    # Prepend system prompt if not already present
    working_messages = list(messages)
    if not working_messages or working_messages[0].role != "system":
        working_messages.insert(0, Message(role="system", content=SYSTEM_PROMPT))

    for _ in range(limit):
        response: AIMessage = await model_with_tools.ainvoke(
            _to_langchain_messages(working_messages)
        )

        # Record the assistant turn (preserves tool_calls so subsequent tool
        # role messages are valid when resent to the API)
        working_messages.append(_message_from_ai(response))

        if response.tool_calls:
            # Execute every requested tool call
            for tc in response.tool_calls:
                fn_name = tc["name"]
                fn_args = tc["args"]

                result = await execute_tool(fn_name, fn_args)
                tool_calls_made.append(
                    ToolCallRecord(
                        tool_name=fn_name,
                        arguments=fn_args,
                        result=result,
                    )
                )

                # Feed tool result back into the conversation
                working_messages.append(
                    Message(
                        role="tool",
                        content=result,
                        tool_call_id=tc["id"],
                        name=fn_name,
                    )
                )
        else:
            # Final text answer
            final_reply = _extract_text(response.content)
            return final_reply, tool_calls_made

    raise MaxIterationsExceeded(
        f"Agent did not produce a final answer within {limit} iterations."
    )


# ---------------------------------------------------------------------------
# Agentic loop — streaming
# ---------------------------------------------------------------------------

async def stream_agent(
    messages: list[Message],
    max_iterations: int | None = None,
) -> AsyncIterator[str]:
    """Stream the agentic loop as Server-Sent Events (SSE).

    Yields SSE-formatted strings. Each event is one of:
    - ``event: token\\ndata: <text>\\n\\n``  — assistant text token
    - ``event: tool_call\\ndata: <json>\\n\\n`` — tool being executed
    - ``event: done\\ndata: [DONE]\\n\\n``       — end of stream
    - ``event: error\\ndata: <message>\\n\\n``   — error
    """
    model = get_chat_model()
    model_with_tools = model.bind_tools(TOOLS_SCHEMA)
    limit = max_iterations or settings.agent_max_iterations

    working_messages = list(messages)
    if not working_messages or working_messages[0].role != "system":
        working_messages.insert(0, Message(role="system", content=SYSTEM_PROMPT))

    for iteration in range(limit):
        is_last_iteration = iteration == limit - 1

        # Non-streaming call to detect whether this turn requires tool calls
        response: AIMessage = await model_with_tools.ainvoke(
            _to_langchain_messages(working_messages)
        )

        working_messages.append(_message_from_ai(response))

        if response.tool_calls:
            for tc in response.tool_calls:
                fn_name = tc["name"]
                fn_args = tc["args"]

                yield (
                    "event: tool_call\ndata: "
                    + json.dumps({"tool": fn_name, "arguments": fn_args})
                    + "\n\n"
                )

                result = await execute_tool(fn_name, fn_args)
                working_messages.append(
                    Message(
                        role="tool",
                        content=result,
                        tool_call_id=tc["id"],
                        name=fn_name,
                    )
                )

            if not is_last_iteration:
                continue
            # If we hit the last iteration after tool calls, fall through to
            # a final streaming call below.

        # Stream the final answer token-by-token
        async for chunk in model.astream(_to_langchain_messages(working_messages)):
            text = _extract_text(chunk.content)
            if text:
                # JSON-encode so that tokens containing newlines or special
                # characters are safe to embed in a single SSE data line.
                yield f"event: token\ndata: {json.dumps(text)}\n\n"

        yield "event: done\ndata: [DONE]\n\n"
        return

    yield (
        "event: error\ndata: "
        + json.dumps({"message": f"Max iterations ({limit}) exceeded."})
        + "\n\n"
    )
    yield "event: done\ndata: [DONE]\n\n"
