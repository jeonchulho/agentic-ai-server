"""Agentic loop — LLM 을 반복 호출하여 최종 텍스트 답변을 생성하거나
이터레이션 한도에 도달할 때까지 도구(tool)를 실행하는 비동기 루프.

프로바이더 지원 (``LLM_PROVIDER`` 환경 변수 설정):
  - ``openai``  (기본값) — OpenAI ChatGPT
  - ``ollama``            — 로컬 Ollama 모델 (OpenAI 호환 엔드포인트)
  - ``claude``            — Anthropic Claude
  - ``gemini``            — Google Gemini

성능 최적화 포인트:
    1. ``get_chat_model()`` : ``@lru_cache`` 로 LLM 클라이언트 재사용 (llm_factory.py)
    2. ``get_model_with_tools()`` : ``bind_tools`` 결과도 캐시하여
       매 요청마다 반복되는 tool schema 직렬화·바인딩 비용 제거
"""
from __future__ import annotations

import json
from functools import lru_cache  # 표준 라이브러리 메모이제이션
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
from app.agent.router import route_request
from app.agent.sub_agent_registry import build_orchestrator_prompt
from app.agent.tools import TOOLS_SCHEMA, BASE_TOOLS_SCHEMA, execute_tool
from app.config import settings
from app.models import Message, ToolCall, ToolCallFunction, ToolCallRecord


class MaxIterationsExceeded(RuntimeError):
    """에이전트가 최대 이터레이션 횟수를 초과했을 때 발생."""


# ---------------------------------------------------------------------------
# 캐시 헬퍼 — tool-bound 모델
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_model_with_tools():
    """도구(tool)가 바인딩된 LangChain 모델을 반환한다.

    ``model.bind_tools(TOOLS_SCHEMA)`` 는 내부적으로 TOOLS_SCHEMA(JSON)를
    프로바이더별 형식으로 직렬화하고 새 래퍼 객체를 생성한다.
    이 작업 자체는 빠르지만(수백 µs), run_agent / stream_agent 가 요청마다
    호출하면 불필요한 반복이 발생한다.

    ``@lru_cache(maxsize=1)`` 을 적용해 프로세스 수명 동안 결과를 한 번만
    생성하고 이후 호출에서는 즉시 반환한다.

    Returns:
        TOOLS_SCHEMA 가 바인딩된 Runnable (BaseChatModel 서브클래스).
        ``ainvoke`` 호출 시 LLM 이 자동으로 tool call 을 결정한다.
    """
    # get_chat_model() 자체도 lru_cache 로 캐시되어 있으므로
    # 매번 새 모델 객체가 생성되지 않는다.
    return get_chat_model().bind_tools(TOOLS_SCHEMA)


@lru_cache(maxsize=1)
def get_single_agent_model():
    """BASE_TOOLS_SCHEMA 만 바인딩된 단일 에이전트용 모델을 반환한다.

    ``delegate_to_agent`` 를 제외한 기본 도구 세트만 포함하므로,
    단순 요청 처리 시 오케스트레이터 프롬프트·스키마를 불필요하게
    LLM 컨텍스트에 포함시키지 않는다.
    """
    return get_chat_model().bind_tools(BASE_TOOLS_SCHEMA)


# ---------------------------------------------------------------------------
# 메시지 변환 헬퍼
# ---------------------------------------------------------------------------

def _to_langchain_messages(messages: list[Message]) -> list[BaseMessage]:
    """Pydantic Message 객체 목록을 LangChain 메시지 객체 목록으로 변환한다.

    LangChain 은 각 역할(role)에 맞는 전용 메시지 클래스를 사용한다:
      - "system"    → SystemMessage
      - "user"      → HumanMessage
      - "assistant" → AIMessage (tool_calls 포함 가능)
      - "tool"      → ToolMessage (tool 실행 결과)

    tool_calls 가 있는 assistant 메시지는 LangChain 내부 형식(dict)으로
    변환해야 다음 턴에서 올바르게 처리된다.
    """
    result: list[BaseMessage] = []
    for m in messages:
        if m.role == "system":
            result.append(SystemMessage(content=m.content or ""))
        elif m.role == "user":
            result.append(HumanMessage(content=m.content or ""))
        elif m.role == "assistant":
            if m.tool_calls:
                # tool_calls 가 있을 때는 LangChain 이 요구하는 dict 형식으로 변환
                # args 는 JSON 문자열 → dict 로 역직렬화
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
            # tool_call_id 로 어떤 tool call 에 대한 응답인지 연결
            result.append(
                ToolMessage(
                    content=m.content or "",
                    tool_call_id=m.tool_call_id or "",
                )
            )
    return result


def _extract_text(content: Any) -> str:
    """LangChain 메시지 content 값에서 순수 텍스트를 추출한다.

    일부 프로바이더(예: Claude)는 단순 문자열 대신 타입이 지정된 콘텐츠
    블록의 리스트를 반환한다.  이 헬퍼는 두 형식을 모두 단일 문자열로 통일한다.

    처리 규칙:
      - str  → 그대로 반환
      - list → 각 원소가 str 이면 직접 추가,
               dict 이고 "type": "text" 이면 "text" 키의 값을 추가
      - 기타 → 빈 문자열 반환
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
    """LangChain AIMessage 를 프로젝트 내부 Pydantic Message 모델로 변환한다.

    tool_calls 가 있을 경우 각 tool call 의 args (dict) 를 JSON 문자열로
    직렬화해 ToolCallFunction 에 저장한다.  이는 내부 Message 모델이
    arguments 를 문자열로 보관하기 때문이다.
    """
    tool_calls = None
    if response.tool_calls:
        tool_calls = [
            ToolCall(
                id=tc["id"],
                type="function",
                function=ToolCallFunction(
                    name=tc["name"],
                    arguments=json.dumps(tc["args"]),  # dict → JSON 문자열
                ),
            )
            for tc in response.tool_calls
        ]
    # content 가 리스트 블록 형식일 수 있으므로 _extract_text 로 정규화
    content = _extract_text(response.content) or None
    return Message(role="assistant", content=content, tool_calls=tool_calls)


def _get_last_user_content(messages: list[Message]) -> str:
    """대화 기록에서 마지막 user 메시지의 내용을 반환한다."""
    for m in reversed(messages):
        if m.role == "user":
            return m.content or ""
    return ""


# ---------------------------------------------------------------------------
# 에이전틱 루프 — 비스트리밍 (단일 응답 반환)
# ---------------------------------------------------------------------------

async def run_agent(
    messages: list[Message],
    max_iterations: int | None = None,
) -> tuple[str, list[ToolCallRecord]]:
    """에이전틱 루프를 실행하고 ``(최종 답변, 실행된 tool 목록)`` 을 반환한다.

    동작 흐름:
        1. 시스템 프롬프트가 없으면 대화 맨 앞에 자동 삽입한다.
        2. LLM 에 현재 대화를 전달하고 응답(AIMessage)을 받는다.
        3. 응답에 tool_calls 가 있으면 각 도구를 실행하고 결과를 대화에 추가한다.
        4. tool_calls 가 없으면(= 최종 답변) 반환한다.
        5. max_iterations 를 초과하면 MaxIterationsExceeded 를 발생시킨다.

    Args:
        messages:       사용자/어시스턴트 대화 기록.
        max_iterations: LLM 최대 호출 횟수.
                        None 이면 ``settings.agent_max_iterations`` 를 사용.

    Returns:
        (final_reply, tool_calls_made) 튜플.
    """
    # 마지막 user 메시지 기반으로 단일/멀티 에이전트 모드 결정
    mode = route_request(_get_last_user_content(messages))
    if mode == "multi":
        model_with_tools = get_model_with_tools()
        system_prompt = build_orchestrator_prompt()
    else:
        model_with_tools = get_single_agent_model()
        system_prompt = SYSTEM_PROMPT

    limit = max_iterations or settings.agent_max_iterations
    tool_calls_made: list[ToolCallRecord] = []

    # 시스템 프롬프트 자동 삽입 — 이미 있으면 중복 삽입하지 않는다
    working_messages = list(messages)
    if not working_messages or working_messages[0].role != "system":
        working_messages.insert(0, Message(role="system", content=system_prompt))

    for _ in range(limit):
        # LLM 호출: 현재 대화 전체를 LangChain 형식으로 변환해 전달
        response: AIMessage = await model_with_tools.ainvoke(
            _to_langchain_messages(working_messages)
        )

        # 어시스턴트 턴을 대화 기록에 추가 (tool_calls 정보 보존 필요)
        working_messages.append(_message_from_ai(response))

        if response.tool_calls:
            # ── tool 호출 처리 ───────────────────────────────────────────
            for tc in response.tool_calls:
                fn_name = tc["name"]
                fn_args = tc["args"]

                # 실제 도구 실행 (네트워크 요청, DB 조회 등 I/O 발생 가능)
                result = await execute_tool(fn_name, fn_args)
                tool_calls_made.append(
                    ToolCallRecord(
                        tool_name=fn_name,
                        arguments=fn_args,
                        result=result,
                    )
                )

                # tool 실행 결과를 대화 기록에 추가 → 다음 LLM 호출에 전달됨
                working_messages.append(
                    Message(
                        role="tool",
                        content=result,
                        tool_call_id=tc["id"],  # 어떤 tool call 에 대한 결과인지 연결
                        name=fn_name,
                    )
                )
        else:
            # ── 최종 텍스트 답변 ─────────────────────────────────────────
            final_reply = _extract_text(response.content)
            return final_reply, tool_calls_made

    # 최대 이터레이션 도달 — 무한 루프 방지
    raise MaxIterationsExceeded(
        f"Agent did not produce a final answer within {limit} iterations."
    )


# ---------------------------------------------------------------------------
# 에이전틱 루프 — 스트리밍 (SSE 이벤트 생성기)
# ---------------------------------------------------------------------------

async def stream_agent(
    messages: list[Message],
    max_iterations: int | None = None,
) -> AsyncIterator[str]:
    """에이전틱 루프를 Server-Sent Events(SSE) 스트림으로 실행한다.

    SSE 이벤트 형식:
      - ``event: token\\ndata: <text>\\n\\n``      — 어시스턴트 텍스트 토큰
      - ``event: tool_call\\ndata: <json>\\n\\n``  — 도구 실행 알림
      - ``event: done\\ndata: [DONE]\\n\\n``        — 스트림 종료
      - ``event: error\\ndata: <message>\\n\\n``   — 오류 발생

    동작 흐름:
        1. tool call 이 필요한 동안은 ``ainvoke`` (비스트리밍)를 사용한다.
           tool call 응답 전체를 받아야 도구를 실행할 수 있기 때문이다.
        2. 최종 텍스트 답변 단계에서만 ``astream`` 으로 토큰 단위로 스트리밍한다.
        3. 마지막 이터레이션에서 tool call 이 발생하면 강제로 스트리밍 단계로 진입.

    Args:
        messages:       사용자/어시스턴트 대화 기록.
        max_iterations: LLM 최대 호출 횟수.
    """
    # 마지막 user 메시지 기반으로 단일/멀티 에이전트 모드 결정
    mode = route_request(_get_last_user_content(messages))
    if mode == "multi":
        model_with_tools = get_model_with_tools()
        system_prompt = build_orchestrator_prompt()
    else:
        model_with_tools = get_single_agent_model()
        system_prompt = SYSTEM_PROMPT

    # get_chat_model() 은 lru_cache 로 캐시되어 있으므로 새 객체 생성 없음
    model = get_chat_model()
    limit = max_iterations or settings.agent_max_iterations

    working_messages = list(messages)
    if not working_messages or working_messages[0].role != "system":
        working_messages.insert(0, Message(role="system", content=system_prompt))

    for iteration in range(limit):
        is_last_iteration = iteration == limit - 1

        # tool call 감지를 위한 비스트리밍 호출
        # (tool call 이 있는지 먼저 확인해야 도구를 실행할 수 있다)
        response: AIMessage = await model_with_tools.ainvoke(
            _to_langchain_messages(working_messages)
        )

        working_messages.append(_message_from_ai(response))

        if response.tool_calls:
            # ── tool 호출 처리 ───────────────────────────────────────────
            for tc in response.tool_calls:
                fn_name = tc["name"]
                fn_args = tc["args"]

                # 클라이언트에 도구 실행 알림 이벤트 전송
                yield (
                    "event: tool_call\ndata: "
                    + json.dumps({"tool": fn_name, "arguments": fn_args})
                    + "\n\n"
                )

                # 실제 도구 실행
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
                # 아직 이터레이션 여유가 있으면 다음 LLM 호출로 계속
                continue
            # 마지막 이터레이션에서 tool call 이 발생 → 스트리밍 답변 생성으로 낙하

        # ── 최종 답변 스트리밍 ────────────────────────────────────────────
        # astream 은 토큰 단위로 청크를 비동기 생성한다.
        # JSON 인코딩으로 개행·특수문자가 포함된 토큰도 안전하게 SSE 에 삽입.
        async for chunk in model.astream(_to_langchain_messages(working_messages)):
            text = _extract_text(chunk.content)
            if text:
                yield f"event: token\ndata: {json.dumps(text)}\n\n"

        # 스트림 종료 신호 전송
        yield "event: done\ndata: [DONE]\n\n"
        return

    # 최대 이터레이션 초과 — 오류 이벤트 전송 후 스트림 종료
    yield (
        "event: error\ndata: "
        + json.dumps({"message": f"Max iterations ({limit}) exceeded."})
        + "\n\n"
    )
    yield "event: done\ndata: [DONE]\n\n"
