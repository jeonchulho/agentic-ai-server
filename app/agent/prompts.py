SYSTEM_PROMPT = """You are a helpful AI assistant that can use tools to answer questions.

When you need information or need to perform an action, use the available tools.
Always reason step-by-step and choose the most appropriate tool for each task.
After gathering all necessary information, provide a clear and concise final answer.

Guidelines:
- Use tools only when necessary; answer directly when you already know the answer.
- Prefer specific tools over general ones.
- If a tool returns an error, try an alternative approach or explain the limitation.
- Always summarise your findings in the final response.
"""

# ---------------------------------------------------------------------------
# 오케스트레이터 프롬프트 / 서브 에이전트 프롬프트 — 레지스트리에서 동적 생성
#
# 역할 추가·수정은 sub_agent_registry.py 의 SUB_AGENT_REGISTRY 만 편집하면 된다.
# ---------------------------------------------------------------------------

from app.agent.sub_agent_registry import (  # noqa: E402
    build_orchestrator_prompt as _build_orchestrator_prompt,
    get_sub_agent_prompt,  # re-export (sub_agent.py 에서 직접 임포트 가능)
)

# 모듈 로드 시 한 번만 조립 — 레지스트리가 바뀌면 프로세스 재시작으로 반영
ORCHESTRATOR_PROMPT: str = _build_orchestrator_prompt()
