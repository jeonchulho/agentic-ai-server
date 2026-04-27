"""Tool definitions for the agentic loop.

Each tool is:
  1. A Python async function that receives keyword arguments and returns a string.
  2. Registered in ``TOOLS_REGISTRY`` (name → callable).
  3. Described in ``TOOLS_SCHEMA`` (OpenAI function-calling JSON schema).

멀티 에이전트 분리:
  - ``BASE_TOOLS_REGISTRY`` / ``BASE_TOOLS_SCHEMA``
      서브 에이전트가 사용하는 기본 도구 세트.
      ``delegate_to_agent`` 를 의도적으로 제외하여 재귀적 위임을 방지한다.
  - ``TOOLS_REGISTRY`` / ``TOOLS_SCHEMA``
      오케스트레이터(메인 에이전트)가 사용하는 전체 도구 세트.
      BASE + ``delegate_to_agent`` 로 구성된다.

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

async def search_stock_ticker(company_name: str) -> str:
    """Yahoo Finance 검색 API 를 사용해 회사명으로 주식 종목 코드를 검색한다.

    한국 기업의 경우 거래소 접미사(예: .KS = 코스피, .KQ = 코스닥)가 포함된
    Yahoo Finance 심볼을 반환한다.
    """
    try:
        import httpx

        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={company_name}&lang=ko-KR&type=equity&newsCount=0"
        )
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        quotes = data.get("quotes", [])
        if not quotes:
            return f"'{company_name}'에 대한 종목 코드를 찾을 수 없습니다."

        lines: list[str] = []
        for q in quotes[:5]:
            symbol = q.get("symbol", "")
            name = q.get("shortname") or q.get("longname") or ""
            exchange = q.get("exchange", "")
            lines.append(f"{symbol}  ({name}, {exchange})")

        return "검색 결과 (상위 5개):\n" + "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"종목 코드 검색 오류: {exc}"


async def get_stock_price(ticker: str) -> str:
    """Yahoo Finance Chart API 를 사용해 종목의 현재 주가를 조회한다.

    한국 주식은 Yahoo Finance 심볼 형식을 사용한다:
      - 코스피: ``005930.KS`` (삼성전자)
      - 코스닥: ``035720.KQ`` (카카오)
    """
    try:
        import httpx

        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            "?interval=1d&range=1d"
        )
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        chart = data.get("chart", {})
        results = chart.get("result") or []
        if not results:
            error_info = chart.get("error") or {}
            return (
                f"'{ticker}' 주가 조회 실패: "
                + (error_info.get("description") or "데이터 없음")
            )

        meta = results[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is None:
            return f"'{ticker}'의 현재 가격 정보를 가져올 수 없습니다."

        currency = meta.get("currency", "")
        exchange = meta.get("exchangeName", "")
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")

        change_str = ""
        if prev_close:
            diff = price - prev_close
            pct = (diff / prev_close) * 100
            change_str = f"  전일 대비: {diff:+,.0f} ({pct:+.2f}%)"

        return f"{ticker} 현재가: {price:,.0f} {currency}  ({exchange}){change_str}"
    except Exception as exc:  # noqa: BLE001
        return f"주가 조회 오류: {exc}"


async def summarize_large_text(text: str, chunk_size: int = 4000) -> str:
    """큰 텍스트를 청크로 분할하여 asyncio.gather()로 병렬 요약한 뒤 최종 요약을 반환한다.

    Map-Reduce 패턴:
      1. Map   : 텍스트를 ``chunk_size`` 단위로 분할 → 각 청크를 LLM으로 병렬 요약
      2. Reduce: 부분 요약들을 하나의 최종 요약으로 통합

    청크가 하나뿐이면 Map 단계만 수행하여 즉시 반환한다.

    Args:
        text:       요약할 전체 텍스트.
        chunk_size: 각 청크의 최대 문자 수. 기본값 4000 (≈ 1,000 토큰).

    Returns:
        최종 통합 요약 문자열.
    """
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

    from app.agent.llm_factory import get_chat_model  # noqa: PLC0415

    text = text.strip()
    if not text:
        return "요약할 텍스트가 없습니다."

    def _extract(content: Any) -> str:
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

    chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    model = get_chat_model()
    total = len(chunks)

    async def _summarize_chunk(chunk: str, idx: int) -> str:
        try:
            response = await model.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "You are a summarization assistant. "
                            "Summarize the given text concisely, preserving all key information."
                        )
                    ),
                    HumanMessage(
                        content=f"Summarize the following text (part {idx + 1}/{total}):\n\n{chunk}"
                    ),
                ]
            )
            return _extract(response.content)
        except Exception as exc:  # noqa: BLE001
            return f"[Part {idx + 1} summary error: {exc}]"

    if total == 1:
        return await _summarize_chunk(chunks[0], 0)

    # ── Map 단계: 모든 청크를 병렬로 요약 ────────────────────────────────────
    partial_summaries: list[str] = list(
        await asyncio.gather(*[_summarize_chunk(chunk, idx) for idx, chunk in enumerate(chunks)])
    )

    # ── Reduce 단계: 부분 요약을 하나의 최종 요약으로 통합 ────────────────────
    combined = "\n\n".join(f"[Part {i + 1}]\n{s}" for i, s in enumerate(partial_summaries))
    try:
        final_response = await model.ainvoke(
            [
                SystemMessage(content="You are a summarization assistant."),
                HumanMessage(
                    content=(
                        "The following are partial summaries of a large document. "
                        "Consolidate them into a single, coherent, and concise summary:\n\n"
                        + combined
                    )
                ),
            ]
        )
        return _extract(final_response.content)
    except Exception as exc:  # noqa: BLE001
        return f"부분 요약 (통합 실패: {exc}):\n\n" + combined


async def delegate_to_agent(task: str, role: str = "researcher") -> str:
    """서브태스크를 전문화된 서브 에이전트에게 위임하고 그 결과를 반환한다.

    멀티 에이전트 아키텍처의 핵심 도구다.  오케스트레이터(메인 에이전트)는
    복잡한 요청을 단계별로 분해하여 각 단계를 적합한 역할의 서브 에이전트에게
    위임할 수 있다.

    서브 에이전트는 ``delegate_to_agent`` 를 제외한 기본 도구 세트에 접근하므로
    재귀적·무한 위임이 발생하지 않는다.

    Args:
        task: 서브 에이전트에게 위임할 구체적인 작업 설명.
              이전 단계의 결과가 있다면 task 안에 포함시킨다.
        role: 서브 에이전트의 역할:
              - ``"researcher"`` : 정보 검색, 주가 조회, URL 패치
              - ``"analyst"``    : 데이터 분석, 계산, Python 실행
              - ``"writer"``     : 요약, 문서 작성, 번역

    Returns:
        서브 에이전트의 최종 답변 문자열.
    """
    try:
        # 순환 임포트 방지 — 런타임 지연 임포트
        from app.agent.sub_agent import run_sub_agent  # noqa: PLC0415

        return await run_sub_agent(task=task, role=role)
    except Exception as exc:  # noqa: BLE001
        return f"서브 에이전트 실행 오류 (role={role}): {exc}"


# ---------------------------------------------------------------------------
# BASE 레지스트리 / 스키마 — 서브 에이전트 전용 (delegate_to_agent 제외)
# ---------------------------------------------------------------------------

BASE_TOOLS_REGISTRY: dict[str, Callable[..., Awaitable[str]]] = {
    "calculate": calculate,
    "get_current_time": get_current_time,
    "fetch_url": fetch_url,
    "run_python": run_python,
    "search_stock_ticker": search_stock_ticker,
    "get_stock_price": get_stock_price,
    "summarize_large_text": summarize_large_text,
}

BASE_TOOLS_SCHEMA: list[dict[str, Any]] = [
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
    {
        "type": "function",
        "function": {
            "name": "search_stock_ticker",
            "description": (
                "Search for a stock ticker symbol by company name using Yahoo Finance. "
                "Returns up to 5 matching symbols with exchange info. "
                "Korean stocks use .KS (KOSPI) or .KQ (KOSDAQ) suffixes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Company name to search for, e.g. '삼성전자' or 'Samsung Electronics'.",
                    }
                },
                "required": ["company_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": (
                "Fetch the current stock price for a given Yahoo Finance ticker symbol. "
                "Examples: '005930.KS' (Samsung Electronics), 'AAPL' (Apple), '035720.KQ' (Kakao)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Yahoo Finance ticker symbol, e.g. '005930.KS' or 'AAPL'.",
                    }
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_large_text",
            "description": (
                "Split a large text into chunks and summarize each chunk in parallel using a "
                "Map-Reduce approach, then consolidate the partial summaries into a single "
                "coherent summary. Use this tool when the text is too large to summarize in one call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The full text to summarize.",
                    },
                    "chunk_size": {
                        "type": "integer",
                        "description": "Maximum number of characters per chunk. Defaults to 4000.",
                    },
                },
                "required": ["text"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# 전체 레지스트리 / 스키마 — 오케스트레이터(메인 에이전트) 전용
# (BASE + delegate_to_agent)
# ---------------------------------------------------------------------------

TOOLS_REGISTRY: dict[str, Callable[..., Awaitable[str]]] = {
    **BASE_TOOLS_REGISTRY,
    "delegate_to_agent": delegate_to_agent,
}

from app.agent.sub_agent_registry import build_delegate_schema  # noqa: E402

TOOLS_SCHEMA: list[dict[str, Any]] = BASE_TOOLS_SCHEMA + [build_delegate_schema()]


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch a tool call by name with the provided arguments."""
    fn = TOOLS_REGISTRY.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'."
    return await fn(**arguments)