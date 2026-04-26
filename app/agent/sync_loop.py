"""Synchronous agentic loop — same logic as loop.py but uses the blocking
``openai.OpenAI`` client instead of ``AsyncOpenAI``.

Use this module when you cannot run an asyncio event-loop (e.g. in a plain
script, a thread, or a synchronous web framework like Flask/Django).

Public API
----------
- ``run_agent_sync(messages, max_iterations)`` → ``(final_reply, tool_calls_made)``
- ``stream_agent_sync(messages, max_iterations)`` → ``Iterator[str]`` (SSE strings)
"""
from __future__ import annotations

import ast
import datetime
import json
import math
import operator
import subprocess
import typing
from typing import Any, Iterator

from openai import OpenAI

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import TOOLS_SCHEMA
from app.config import settings
from app.models import Message, ToolCall, ToolCallFunction, ToolCallRecord


# ---------------------------------------------------------------------------
# Helpers shared with loop.py (no async required)
# ---------------------------------------------------------------------------

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
        if m.tool_calls is not None:
            entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in m.tool_calls
            ]
        result.append(entry)
    return result


def _message_from_assistant(assistant_message: Any) -> Message:
    """Build a Message from an OpenAI assistant ChatCompletionMessage."""
    tool_calls = None
    if assistant_message.tool_calls:
        tool_calls = [
            ToolCall(
                id=tc.id,
                type=tc.type,
                function=ToolCallFunction(
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                ),
            )
            for tc in assistant_message.tool_calls
        ]
    return Message(
        role="assistant",
        content=assistant_message.content,
        tool_calls=tool_calls,
    )


# ---------------------------------------------------------------------------
# Synchronous tool implementations
# ---------------------------------------------------------------------------

# Allowed operators for safe expression evaluation (mirrors tools.py)
_OPERATORS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

_MATH_FUNCTIONS: dict[str, Any] = {
    k: getattr(math, k) for k in dir(math) if not k.startswith("_")
}


def _safe_eval(node: ast.expr) -> float:
    """Recursively evaluate an AST node using only safe operations."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError(f"Unsupported constant type: {type(node.value)}")
    if isinstance(node, ast.BinOp):
        op_fn = _OPERATORS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_fn(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_fn = _OPERATORS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        return op_fn(_safe_eval(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple math function calls are allowed.")
        fn = _MATH_FUNCTIONS.get(node.func.id)
        if fn is None:
            raise ValueError(f"Unknown math function: {node.func.id}")
        args = [_safe_eval(a) for a in node.args]
        return fn(*args)
    if isinstance(node, ast.Name):
        value = _MATH_FUNCTIONS.get(node.id)
        if value is None or not isinstance(value, (int, float)):
            raise ValueError(f"Unknown constant: {node.id}")
        return float(value)
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def calculate_sync(expression: str) -> str:
    """Safely evaluate a mathematical expression and return the result."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return str(result)
    except Exception as exc:
        return f"Error evaluating expression: {exc}"


def get_current_time_sync(timezone: str = "UTC") -> str:
    """Return the current date and time in the requested timezone."""
    try:
        import zoneinfo

        tz = zoneinfo.ZoneInfo(timezone)
    except Exception:
        return f"Unknown timezone '{timezone}'. Please use a valid IANA timezone name."

    now = datetime.datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")


def fetch_url_sync(url: str) -> str:
    """Fetch the text content of a URL (first 4000 characters) — blocking."""
    try:
        import httpx

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text[:4000]
    except Exception as exc:
        return f"Error fetching URL: {exc}"


def run_python_sync(code: str) -> str:
    """Execute a Python snippet in a subprocess and return its stdout/stderr.

    WARNING: This runs arbitrary code in a subprocess. In production, replace
    with a proper sandboxed execution environment.
    """
    try:
        proc = subprocess.run(
            ["python3", "-c", code],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        output = proc.stdout + proc.stderr
        return output[:2000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: code execution timed out after 10 seconds."
    except Exception as exc:
        return f"Error running code: {exc}"


# ---------------------------------------------------------------------------
# Synchronous tool registry and dispatcher
# ---------------------------------------------------------------------------

_SYNC_TOOLS_REGISTRY: dict[str, typing.Callable[..., str]] = {
    "calculate": calculate_sync,
    "get_current_time": get_current_time_sync,
    "fetch_url": fetch_url_sync,
    "run_python": run_python_sync,
}


def execute_tool_sync(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch a tool call by name with the provided arguments (blocking)."""
    fn = _SYNC_TOOLS_REGISTRY.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'."
    return fn(**arguments)


# ---------------------------------------------------------------------------
# Synchronous agentic loop
# ---------------------------------------------------------------------------

class MaxIterationsExceeded(RuntimeError):
    """Raised when the agent exceeds its maximum iteration count."""


def run_agent_sync(
    messages: list[Message],
    max_iterations: int | None = None,
) -> tuple[str, list[ToolCallRecord]]:
    """Run the agentic loop synchronously and return ``(final_reply, tool_calls_made)``.

    This is the blocking counterpart of ``loop.run_agent``. It uses the
    standard ``openai.OpenAI`` client, so it can be called from any context
    that does not have (or must not have) an asyncio event-loop.

    Args:
        messages: Conversation history (user/assistant turns).
        max_iterations: Maximum number of LLM calls. Defaults to
            ``settings.agent_max_iterations``.

    Returns:
        A tuple of ``(final_reply, tool_calls_made)`` where ``final_reply``
        is the assistant's final text answer and ``tool_calls_made`` is the
        ordered list of tool calls that were executed during the loop.

    Raises:
        MaxIterationsExceeded: If the agent does not produce a final text
            answer within the allowed number of iterations.
    """
    client = OpenAI(api_key=settings.openai_api_key)
    limit = max_iterations or settings.agent_max_iterations
    tool_calls_made: list[ToolCallRecord] = []

    # Prepend system prompt if not already present
    working_messages = list(messages)
    if not working_messages or working_messages[0].role != "system":
        working_messages.insert(0, Message(role="system", content=SYSTEM_PROMPT))

    for _ in range(limit):
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=_to_openai_messages(working_messages),
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
        )

        choice = response.choices[0]
        assistant_message = choice.message

        # Record the assistant turn
        working_messages.append(_message_from_assistant(assistant_message))

        if choice.finish_reason == "tool_calls" and assistant_message.tool_calls:
            # Execute every requested tool call
            for tc in assistant_message.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                result = execute_tool_sync(fn_name, fn_args)
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


def stream_agent_sync(
    messages: list[Message],
    max_iterations: int | None = None,
) -> Iterator[str]:
    """Stream the agentic loop as Server-Sent Events (SSE) — blocking generator.

    This is the synchronous counterpart of ``loop.stream_agent``. It yields
    SSE-formatted strings one at a time, making it suitable for use with
    synchronous frameworks such as Flask (``Response(stream_with_context(...))``)
    or plain scripts that consume the generator directly.

    Yields SSE-formatted strings. Each event is one of:
    - ``event: token\\ndata: <text>\\n\\n``       — assistant text token
    - ``event: tool_call\\ndata: <json>\\n\\n``   — tool being executed
    - ``event: done\\ndata: [DONE]\\n\\n``          — end of stream
    - ``event: error\\ndata: <message>\\n\\n``    — error

    Args:
        messages: Conversation history (user/assistant turns).
        max_iterations: Maximum number of LLM calls. Defaults to
            ``settings.agent_max_iterations``.
    """
    client = OpenAI(api_key=settings.openai_api_key)
    limit = max_iterations or settings.agent_max_iterations

    working_messages = list(messages)
    if not working_messages or working_messages[0].role != "system":
        working_messages.insert(0, Message(role="system", content=SYSTEM_PROMPT))

    for iteration in range(limit):
        is_last_iteration = iteration == limit - 1

        # Non-streaming call to detect whether this turn has tool_calls
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=_to_openai_messages(working_messages),
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
        )

        choice = response.choices[0]
        assistant_message = choice.message

        working_messages.append(_message_from_assistant(assistant_message))

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

                result = execute_tool_sync(fn_name, fn_args)
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
        with client.chat.completions.stream(
            model=settings.openai_model,
            messages=_to_openai_messages(working_messages),
        ) as stream:
            for text in stream.text_stream:
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
