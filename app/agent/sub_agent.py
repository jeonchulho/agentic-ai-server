"""서브 에이전트 실행기 — 멀티 에이전트 아키텍처의 핵심 컴포넌트.

Orchestrator(메인 에이전트)가 ``delegate_to_agent`` 도구를 통해 복잡한 태스크를
전문화된 서브 에이전트에게 위임할 때 이 모듈이 사용됩니다.

각 서브 에이전트는:
  - 고유한 시스템 프롬프트(역할 특화)를 가집니다.
  - 기본 도구 세트(BASE_TOOLS_REGISTRY / BASE_TOOLS_SCHEMA)에 접근합니다.
    ``delegate_to_agent`` 도구는 의도적으로 제외하여 무한 재귀 위임을 방지합니다.
  - 독립적인 대화 기록을 유지합니다(오케스트레이터 대화와 격리).

지원 역할:
  - ``"researcher"`` : 정보 검색·수집 전문
  - ``"analyst"``    : 데이터 분석·계산 전문
  - ``"writer"``     : 문서 작성·요약 전문
"""
from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agent.llm_factory import get_chat_model
from app.agent.sub_agent_registry import get_sub_agent_prompt


class SubAgentMaxIterationsExceeded(RuntimeError):
    """서브 에이전트가 최대 이터레이션 횟수를 초과했을 때 발생."""


def _extract_text(content: Any) -> str:
    """AIMessage.content 에서 순수 텍스트를 추출한다 (loop.py 와 동일 로직)."""
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


@lru_cache(maxsize=1)
def _get_base_model_with_tools():
    """BASE_TOOLS_SCHEMA 가 바인딩된 서브 에이전트 전용 모델을 반환한다.

    ``bind_tools(BASE_TOOLS_SCHEMA)`` 는 JSON 스키마 직렬화·래퍼 객체 생성 비용이
    수백 µs 수준이지만, 서브 에이전트가 호출될 때마다 반복되는 낭비를 없애기 위해
    ``@lru_cache(maxsize=1)`` 로 프로세스 수명 동안 결과를 재사용한다.

    순환 임포트 방지를 위해 ``BASE_TOOLS_SCHEMA`` 를 함수 내부에서 지연 임포트한다.
    """
    from app.agent.tools import BASE_TOOLS_SCHEMA  # noqa: PLC0415

    return get_chat_model().bind_tools(BASE_TOOLS_SCHEMA)


async def run_sub_agent(
    task: str,
    role: str = "researcher",
    max_iterations: int = 5,
) -> str:
    """특정 역할에 특화된 서브 에이전트를 실행하고 최종 답변을 반환한다.

    동작 흐름:
      1. 역할에 맞는 시스템 프롬프트를 선택한다.
      2. 캐시된 BASE_TOOLS_SCHEMA 바인딩 모델을 가져온다.
      3. task 를 첫 번째 HumanMessage 로 주입하여 에이전틱 루프를 실행한다.
      4. 여러 tool call 이 동시에 발생할 경우 asyncio.gather() 로 병렬 실행한다.
      5. 최종 텍스트 답변을 반환한다.

    Args:
        task:           서브 에이전트가 수행할 구체적인 태스크 설명.
        role:           서브 에이전트의 역할 ('researcher', 'analyst', 'writer').
        max_iterations: 최대 LLM 호출 횟수 (무한 루프 방지).

    Returns:
        서브 에이전트의 최종 답변 문자열.

    Raises:
        SubAgentMaxIterationsExceeded: max_iterations 내에 최종 답변을 내지 못한 경우.
    """
    # 순환 임포트 방지 — 함수 호출 시점에 임포트
    from app.agent.tools import BASE_TOOLS_REGISTRY  # noqa: PLC0415

    system_prompt = get_sub_agent_prompt(role)

    # 캐시된 tool-bound 모델 재사용
    model = _get_base_model_with_tools()

    # 독립적인 대화 기록 — 오케스트레이터 컨텍스트와 완전히 격리
    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=task),
    ]

    for _ in range(max_iterations):
        response: AIMessage = await model.ainvoke(messages)
        messages.append(response)

        if response.tool_calls:
            # ── 도구 병렬 실행 ─────────────────────────────────────────────
            async def _run_one(tc: dict[str, Any]) -> str:
                fn = BASE_TOOLS_REGISTRY.get(tc["name"])
                if fn is None:
                    return f"Error: unknown tool '{tc['name']}'"
                try:
                    return await fn(**tc["args"])
                except Exception as exc:  # noqa: BLE001
                    return f"Tool execution error: {exc}"

            results: list[str] = list(
                await asyncio.gather(*[_run_one(tc) for tc in response.tool_calls])
            )

            for tc, result in zip(response.tool_calls, results):
                messages.append(
                    ToolMessage(content=result, tool_call_id=tc["id"])
                )
        else:
            # ── 최종 텍스트 답변 ───────────────────────────────────────────
            return _extract_text(response.content)

    raise SubAgentMaxIterationsExceeded(
        f"Sub-agent ({role}) exceeded {max_iterations} iterations "
        f"for task: {task[:120]}"
    )
