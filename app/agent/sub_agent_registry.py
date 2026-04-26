"""서브 에이전트 레지스트리 — 역할 정의와 동적 프롬프트·스키마 빌더.

새 서브 에이전트 역할을 추가할 때는 ``SUB_AGENT_REGISTRY`` 에 항목 하나만
추가하면 된다.  오케스트레이터 프롬프트, ``delegate_to_agent`` 스키마,
서브 에이전트 시스템 프롬프트가 모두 자동으로 반영된다.

공개 API:
    SUB_AGENT_REGISTRY     — 역할 → 메타데이터 매핑 dict
    build_orchestrator_prompt() → str  — 레지스트리 기반 오케스트레이터 프롬프트
    build_delegate_schema() → dict     — 레지스트리 기반 delegate_to_agent 스키마
    get_sub_agent_prompt(role) → str   — 역할별 서브 에이전트 시스템 프롬프트
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 역할 레지스트리 — 새 역할은 여기에만 추가하면 된다
#
# 각 항목 키:
#   description : 오케스트레이터가 역할을 선택할 때 참고하는 한 줄 설명
#   tools       : 이 역할이 활용하는 BASE 도구 이름 목록 (문서용, 런타임 필터 아님)
#   prompt      : 서브 에이전트에게 주입되는 시스템 프롬프트 문자열
# ---------------------------------------------------------------------------

SUB_AGENT_REGISTRY: dict[str, dict[str, Any]] = {
    "researcher": {
        "description": "정보 검색, 주가 조회, URL 패치",
        "tools": ["search_stock_ticker", "get_stock_price", "fetch_url"],
        "prompt": (
            "You are a researcher sub-agent. Your only job is to retrieve "
            "information accurately using available tools and return the raw result.\n\n"
            "Guidelines:\n"
            "- Use search_stock_ticker to find stock ticker symbols by company name.\n"
            "- Use get_stock_price to fetch the current price for a known ticker.\n"
            "- Use fetch_url to retrieve web page content when needed.\n"
            "- Return factual data only — do not embellish or interpret.\n"
            "- If a tool fails, report the error clearly so the orchestrator can decide next steps."
        ),
    },
    "analyst": {
        "description": "데이터 분석, 수식 계산, Python 실행",
        "tools": ["calculate", "run_python"],
        "prompt": (
            "You are an analyst sub-agent. Your job is to process and analyse "
            "data using available tools and return precise, well-reasoned results.\n\n"
            "Guidelines:\n"
            "- Use calculate for mathematical expressions.\n"
            "- Use run_python for complex data processing or statistical analysis.\n"
            "- Show your reasoning and intermediate steps when relevant.\n"
            "- Return results with appropriate units and precision."
        ),
    },
    "writer": {
        "description": "요약, 문서 작성, 번역, 포맷팅",
        "tools": [],
        "prompt": (
            "You are a writer sub-agent. Your job is to produce clear, "
            "well-structured text based on the information provided to you.\n\n"
            "Guidelines:\n"
            "- Summarise concisely; avoid unnecessary repetition.\n"
            "- Match the tone and language of the original content.\n"
            "- Format output as requested (bullet points, paragraphs, etc.).\n"
            "- Do not fabricate facts — only work with what you are given."
        ),
    },
}

# ---------------------------------------------------------------------------
# 오케스트레이터 프롬프트 동적 조립
# ---------------------------------------------------------------------------

_ORCHESTRATOR_TEMPLATE = """\
You are an intelligent orchestrator agent. You can handle tasks directly \
using tools, or break complex multi-step tasks into subtasks and delegate each subtask to a \
specialized sub-agent via the delegate_to_agent tool.

Available sub-agent roles:
{roles}

When to delegate:
- Delegate when a task naturally splits into independent steps that benefit from specialisation.
- Pass the result of one sub-agent as context in the next sub-agent's task description.
- For simple, single-step requests, use the built-in tools directly without delegating.

General guidelines:
- Reason step-by-step before calling any tool.
- Prefer specific tools over general ones.
- If a tool returns an error, try an alternative approach or explain the limitation.
- Always provide the final answer in the same language as the user's question.
- Synthesise all sub-agent results into a single, coherent final response.\
"""


def build_orchestrator_prompt() -> str:
    """레지스트리에서 역할 목록을 읽어 오케스트레이터 시스템 프롬프트를 동적으로 조립한다.

    새 역할이 ``SUB_AGENT_REGISTRY`` 에 추가되면 이 함수의 출력에 자동 반영된다.
    프롬프트 길이는 역할 설명 한 줄씩만 포함하므로, 역할이 늘어나도 크게 증가하지 않는다.
    """
    roles_lines = "\n".join(
        f'- "{role}": {defn["description"]}'
        for role, defn in SUB_AGENT_REGISTRY.items()
    )
    return _ORCHESTRATOR_TEMPLATE.format(roles=roles_lines)


# ---------------------------------------------------------------------------
# delegate_to_agent 도구 스키마 동적 생성
# ---------------------------------------------------------------------------


def build_delegate_schema() -> dict[str, Any]:
    """레지스트리에서 역할 목록을 읽어 ``delegate_to_agent`` 도구 JSON 스키마를 생성한다.

    ``role`` enum 값이 레지스트리에서 자동 생성되므로 새 역할 추가 시 스키마도
    자동으로 업데이트된다.

    Returns:
        OpenAI function-calling 형식의 도구 스키마 dict.
    """
    roles = list(SUB_AGENT_REGISTRY.keys())
    role_desc = ", ".join(
        f"'{r}': {SUB_AGENT_REGISTRY[r]['description']}" for r in roles
    )
    return {
        "type": "function",
        "function": {
            "name": "delegate_to_agent",
            "description": (
                "Delegate a subtask to a specialised sub-agent and return its result. "
                "Use this to break a complex task into steps: each step can be handled "
                "by a sub-agent with the appropriate role. "
                "Pass any relevant context (e.g. results from previous steps) inside the task string. "
                f"Roles: {role_desc}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": (
                            "Clear description of the subtask the sub-agent should perform. "
                            "Include all necessary context so the sub-agent can work independently."
                        ),
                    },
                    "role": {
                        "type": "string",
                        "enum": roles,
                        "description": role_desc,
                    },
                },
                "required": ["task"],
            },
        },
    }


# ---------------------------------------------------------------------------
# 서브 에이전트 프롬프트 조회
# ---------------------------------------------------------------------------

_FALLBACK_PROMPT = (
    "You are a helpful AI assistant that can use tools to answer questions. "
    "Always reason step-by-step and choose the most appropriate tool for each task."
)


def get_sub_agent_prompt(role: str) -> str:
    """역할 이름에 해당하는 서브 에이전트 시스템 프롬프트를 반환한다.

    알 수 없는 역할은 기본 프롬프트로 대체된다.
    """
    entry = SUB_AGENT_REGISTRY.get(role)
    return entry["prompt"] if entry else _FALLBACK_PROMPT
