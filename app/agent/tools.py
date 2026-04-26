"""Tool definitions for the agentic loop.

Each tool is:
  1. A Python async function that receives keyword arguments and returns a string.
  2. Registered in ``TOOLS_REGISTRY`` (name → callable).
  3. Described in ``TOOLS_SCHEMA`` (OpenAI function-calling JSON schema).

Add new tools by implementing the function, adding it to both mappings, and
appending its schema to TOOLS_SCHEMA.
"""
from __future__ import annotations

import asyncio
import ast
import operator
import math
from typing import Any, Callable, Awaitable


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

# Allowed operators for safe expression evaluation
_OPERATORS = {
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

_MATH_FUNCTIONS: dict[str, Any] = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}


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


async def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression and return the result."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return str(result)
    except Exception as exc:
        return f"Error evaluating expression: {exc}"


async def get_current_time(timezone: str = "UTC") -> str:
    """Return the current date and time in the requested timezone."""
    import datetime

    try:
        import zoneinfo

        tz = zoneinfo.ZoneInfo(timezone)
    except Exception:
        return f"Unknown timezone '{timezone}'. Please use a valid IANA timezone name."

    now = datetime.datetime.now(tz)
    return now.strftime("%Y-%m-%d %H:%M:%S %Z")


async def fetch_url(url: str) -> str:
    """Fetch the text content of a URL (first 4000 characters)."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text[:4000]
    except Exception as exc:
        return f"Error fetching URL: {exc}"


async def run_python(code: str) -> str:
    """Execute a Python snippet in a subprocess and return its stdout/stderr.

    WARNING: This runs arbitrary code in a subprocess. In production, replace
    with a proper sandboxed execution environment (e.g. Docker with resource
    limits or a service like Pyodide).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        output = stdout.decode() + stderr.decode()
        return output[:2000] if output else "(no output)"
    except asyncio.TimeoutError:
        return "Error: code execution timed out after 10 seconds."
    except Exception as exc:
        return f"Error running code: {exc}"


# ---------------------------------------------------------------------------
# Registry and schema
# ---------------------------------------------------------------------------

TOOLS_REGISTRY: dict[str, Callable[..., Awaitable[str]]] = {
    "calculate": calculate,
    "get_current_time": get_current_time,
    "fetch_url": fetch_url,
    "run_python": run_python,
}

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a mathematical expression (supports Python math functions).",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "A valid Python math expression, e.g. 'sqrt(2) * pi'.",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Return the current date and time for a given timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone name, e.g. 'Asia/Seoul'. Defaults to UTC.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch the text content of a web page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The fully-qualified URL to fetch.",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute a Python code snippet and return stdout/stderr output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Valid Python source code to execute.",
                    }
                },
                "required": ["code"],
            },
        },
    },
]


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch a tool call by name with the provided arguments."""
    fn = TOOLS_REGISTRY.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'."
    return await fn(**arguments)
