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

from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agent.llm_factory import get_chat_model
from app.agent.prompts import get_sub_agent_prompt


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


async def run_sub_agent(
    task: str,
    role: str = "researcher",
    max_iterations: int = 5,
) -> str:
    """특정 역할에 특화된 서브 에이전트를 실행하고 최종 답변을 반환한다.

    동작 흐름:
      1. 역할에 맞는 시스템 프롬프트를 선택한다.
      2. BASE_TOOLS_SCHEMA 가 바인딩된 LLM 인스턴스를 생성한다.
         (``delegate_to_agent`` 제외로 재귀 위임 방지)
      3. task 를 첫 번째 HumanMessage 로 주입하여 에이전틱 루프를 실행한다.
      4. 최종 텍스트 답변을 반환한다.

    순환 임포트 방지:
        ``BASE_TOOLS_REGISTRY`` 와 ``BASE_TOOLS_SCHEMA`` 는
        tools.py 에서 지연 임포트(lazy import)한다.
        (tools.py 가 sub_agent.py 를 임포트하는 것을 피하기 위함)

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
    from app.agent.tools import BASE_TOOLS_REGISTRY, BASE_TOOLS_SCHEMA  # noqa: PLC0415

    system_prompt = get_sub_agent_prompt(role)

    # 서브 에이전트 전용 tool-bound 모델
    # (오케스트레이터와 별도 bind_tools 호출 — BASE_TOOLS_SCHEMA 사용)
    model = get_chat_model().bind_tools(BASE_TOOLS_SCHEMA)

    # 독립적인 대화 기록 — 오케스트레이터 컨텍스트와 완전히 격리
    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=task),
    ]

    for _ in range(max_iterations):
        response: AIMessage = await model.ainvoke(messages)
        messages.append(response)

        if response.tool_calls:
            # ── 도구 실행 ──────────────────────────────────────────────────
            for tc in response.tool_calls:
                fn = BASE_TOOLS_REGISTRY.get(tc["name"])
                if fn is None:
                    result = f"Error: unknown tool '{tc['name']}'"
                else:
                    try:
                        result = await fn(**tc["args"])
                    except Exception as exc:  # noqa: BLE001
                        result = f"Tool execution error: {exc}"
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
