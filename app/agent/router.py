"""요청 복잡도 분류기 — 단일 에이전트 vs 멀티 에이전트 분기 결정.

``route_request(text)`` 는 사용자 메시지를 분석하여 다음 중 하나를 반환한다:
  - ``"single"`` : 단일 에이전트로 처리 가능한 단순 요청
  - ``"multi"``  : 여러 전문 서브 에이전트의 협업이 필요한 복합 요청

분류 전략 — 3단계 파이프라인:
  1. **휴리스틱 (즉시 multi)**: 멀티스텝 연결어 or 2개 이상 도메인 키워드 → ``"multi"``
  2. **휴리스틱 (즉시 single)**: 도메인 키워드가 전혀 없는 단순 메시지 → ``"single"``
  3. **LLM 폴백 (애매한 경우)**: 도메인 키워드가 정확히 1개 매칭되어 판단이 어려울 때
     경량 LLM 에 1-shot 호출하여 ``"yes/no"`` 로 최종 결정.
     - LLM 호출 실패 시 안전하게 ``"single"`` 로 기본값 처리.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 역할 도메인별 키워드 패턴
# ---------------------------------------------------------------------------

# 정보 검색·조회 도메인 (researcher)
# 참고: "수신", "받은" 은 이메일·데이터 *수신함 조회*(fetch/retrieve) 를 의미하므로
#      작성(writer) 도메인이 아닌 검색(researcher) 도메인에 분류한다.
_RESEARCH_PATTERNS: list[str] = [
    r"검색",
    r"찾아",
    r"조회",
    r"수신",
    r"받은",
    r"가져와",
    r"주가",
    r"종목",
    r"뉴스",
    r"알려줘",
    r"찾아줘",
    r"찾아봐",
    r"search",
    r"look\s*up",
    r"find",
    r"fetch",
    r"retrieve",
    r"stock\s*price",
    r"get\s+\w+\s+(data|list|info|result)",
]

# 데이터 분석·계산 도메인 (analyst)
_ANALYSIS_PATTERNS: list[str] = [
    r"분석",
    r"계산",
    r"코드",
    r"파이썬",
    r"통계",
    r"수식",
    r"analyz",
    r"analys[ei]",
    r"calculat",
    r"comput",
    r"python",
    r"\bcode\b",
]

# 문서 작성·요약 도메인 (writer)
_WRITING_PATTERNS: list[str] = [
    r"요약",
    r"작성",
    r"정리",
    r"번역",
    r"보내",
    r"메일",
    r"이메일",
    r"리포트",
    r"보고서",
    r"summariz",
    r"summaris",
    r"writ[ei]",
    r"translat",
    r"\breport\b",
    r"compose",
    r"draft",
]

# 멀티스텝 흐름 연결어 — 이것 하나만 있어도 multi 판정
_CHAIN_PATTERNS: list[str] = [
    r"그\s*다음",
    r"그리고\s*나서",
    r"이후\s*에",
    r"한\s*다음",
    r"and\s+then",
    r"after\s+that",
    r"next[,\s]",
    r"finally[,\s]",
    r"step\s+\d",
]

# 도메인 그룹 — 2개 이상 매칭 시 multi
_DOMAIN_GROUPS: list[list[str]] = [
    _RESEARCH_PATTERNS,
    _ANALYSIS_PATTERNS,
    _WRITING_PATTERNS,
]


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _match_any(patterns: list[str], text: str) -> bool:
    """패턴 목록 중 하나라도 text 에 일치하면 True."""
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _heuristic_route(text: str) -> str | None:
    """휴리스틱 분류를 시도한다.

    Returns:
        ``"multi"``  — 확실히 멀티 에이전트가 필요한 경우.
        ``"single"`` — 확실히 단일 에이전트로 충분한 경우.
        ``None``     — 판단 불가 (LLM 폴백 필요).
    """
    # 1. 멀티스텝 연결어가 있으면 즉시 multi
    if _match_any(_CHAIN_PATTERNS, text):
        return "multi"

    matched_domains = sum(
        1 for domain_patterns in _DOMAIN_GROUPS if _match_any(domain_patterns, text)
    )

    # 2. 서로 다른 역할 도메인 키워드가 2개 이상 → multi
    if matched_domains >= 2:
        return "multi"

    # 3. 도메인 키워드가 전혀 없는 단순 메시지 → single
    if matched_domains == 0:
        return "single"

    # 4. 도메인 키워드 1개 매칭 — 애매하므로 LLM 폴백에 위임
    return None


# ---------------------------------------------------------------------------
# LLM 폴백 분류기
# ---------------------------------------------------------------------------

_LLM_CLASSIFY_PROMPT = """\
다음 사용자 요청이 여러 전문 에이전트(정보 검색, 데이터 분석, 문서 작성 등)의 \
협업이 필요한 복합 작업인가요?
"yes" 또는 "no" 중 하나만 대답하세요. 다른 설명은 불필요합니다.

사용자 요청: {text}"""


async def _llm_route(text: str) -> str:
    """LLM 에 1-shot 호출하여 단일/멀티를 결정한다.

    응답에서 "yes" 가 포함되면 ``"multi"``, 그 외에는 ``"single"`` 을 반환한다.
    LLM 호출 실패 시 안전하게 ``"single"`` 로 기본값 처리한다.
    """
    try:
        from langchain_core.messages import HumanMessage  # noqa: PLC0415

        from app.agent.llm_factory import get_chat_model  # noqa: PLC0415

        model = get_chat_model()
        prompt = _LLM_CLASSIFY_PROMPT.format(text=text)
        response = await model.ainvoke([HumanMessage(content=prompt)])

        # content 가 str 또는 list 블록일 수 있으므로 안전하게 추출
        content = response.content
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        answer = str(content).strip().lower()
        logger.debug("LLM router answer for %r: %r", text[:60], answer)
        return "multi" if "yes" in answer else "single"
    except Exception:  # noqa: BLE001
        logger.warning(
            "LLM router fallback failed for request %r; defaulting to 'single'.",
            text[:80],
            exc_info=True,
        )
        return "single"


# ---------------------------------------------------------------------------
# 공개 분류기
# ---------------------------------------------------------------------------


async def route_request(text: str) -> str:
    """사용자 메시지를 분석해 에이전트 실행 모드를 결정한다.

    **3단계 파이프라인**:
      1. 휴리스틱이 확실히 ``"multi"`` 로 판정 → 즉시 반환 (LLM 호출 없음)
      2. 휴리스틱이 확실히 ``"single"`` 로 판정 → 즉시 반환 (LLM 호출 없음)
      3. 휴리스틱이 ``None`` (애매) → LLM 1-shot 폴백으로 최종 결정

    **설계 의도 — 마지막 user 메시지 기준 분류**:
    멀티턴 대화에서 이전 턴의 맥락까지 고려하면 분류 정확도가 높아지지만,
    휴리스틱 단계에서는 비용이 없고, LLM 폴백도 애매한 경우에만 호출된다.

    Args:
        text: 사용자 입력 메시지 (마지막 user 턴의 content).

    Returns:
        ``"single"`` — 단일 에이전트(SYSTEM_PROMPT + BASE_TOOLS)로 처리.
        ``"multi"``  — 멀티 에이전트 오케스트레이터(ORCHESTRATOR_PROMPT + TOOLS)로 처리.
    """
    result = _heuristic_route(text)
    if result is not None:
        return result
    # 휴리스틱 판단 불가 → LLM 폴백
    logger.debug("Heuristic inconclusive for %r; calling LLM router.", text[:60])
    return await _llm_route(text)
