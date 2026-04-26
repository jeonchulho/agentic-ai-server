"""Agentic loop — repeatedly calls the LLM and executes tools until a final
text answer is produced or the iteration limit is reached."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS_SCHEMA, execute_tool
from app.config import settings
from app.models import Message, ToolCallRecord


class MaxIterationsExceeded(RuntimeError):
    """Raised when the agent exceeds its maximum iteration count."""


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert Pydantic Message objects to the dict format expected by OpenAI."""
    result: list[dict[str, Any]] = []
    for m in messages:
        entry: dict[str, Any] = {"role": m.role}
        if m.content is not None:
            entry["content"] = m.content
        if m.tool_call_id is not None:
            entry["tool_call_id"] = m.tool_call_id
        if m.name is not None:
            entry["name"] = m.name
        result.append(entry)
    return result


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
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    limit = max_iterations or settings.agent_max_iterations
    tool_calls_made: list[ToolCallRecord] = []

    # Prepend system prompt if not already present
    working_messages = list(messages)
    if not working_messages or working_messages[0].role != "system":
        working_messages.insert(0, Message(role="system", content=SYSTEM_PROMPT))

    for _ in range(limit):
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=_to_openai_messages(working_messages),
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
        )

        choice = response.choices[0]
        assistant_message = choice.message

        # Record the assistant turn (may contain tool_calls)
        working_messages.append(
            Message(
                role="assistant",
                content=assistant_message.content,
            )
        )

        if choice.finish_reason == "tool_calls" and assistant_message.tool_calls:
            # Execute every requested tool call
            for tc in assistant_message.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

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
                        tool_call_id=tc.id,
                        name=fn_name,
                    )
                )
        else:
            # Final text answer
            final_reply = assistant_message.content or ""
            return final_reply, tool_calls_made

    raise MaxIterationsExceeded(
        f"Agent did not produce a final answer within {limit} iterations."
    )


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
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    limit = max_iterations or settings.agent_max_iterations

    working_messages = list(messages)
    if not working_messages or working_messages[0].role != "system":
        working_messages.insert(0, Message(role="system", content=SYSTEM_PROMPT))

    for iteration in range(limit):
        is_last_iteration = iteration == limit - 1

        # Non-streaming call to detect whether this turn has tool_calls
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=_to_openai_messages(working_messages),
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
        )

        choice = response.choices[0]
        assistant_message = choice.message

        working_messages.append(
            Message(role="assistant", content=assistant_message.content)
        )

        if choice.finish_reason == "tool_calls" and assistant_message.tool_calls:
            for tc in assistant_message.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                yield (
                    f"event: tool_call\ndata: "
                    + json.dumps({"tool": fn_name, "arguments": fn_args})
                    + "\n\n"
                )

                result = await execute_tool(fn_name, fn_args)
                working_messages.append(
                    Message(
                        role="tool",
                        content=result,
                        tool_call_id=tc.id,
                        name=fn_name,
                    )
                )

            if not is_last_iteration:
                continue
            # If we hit the last iteration after tool calls, fall through to
            # a final streaming call below.

        # Stream the final answer token-by-token using the OpenAI streaming API
        async with client.chat.completions.stream(
            model=settings.openai_model,
            messages=_to_openai_messages(working_messages),
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield f"event: token\ndata: {text}\n\n"

        yield "event: done\ndata: [DONE]\n\n"
        return

    yield (
        "event: error\ndata: "
        + json.dumps({"message": f"Max iterations ({limit}) exceeded."})
        + "\n\n"
    )
    yield "event: done\ndata: [DONE]\n\n"
