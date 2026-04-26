"""요청 복잡도 분류기 — 단일 에이전트 vs 멀티 에이전트 분기 결정.

``route_request(text)`` 는 사용자 메시지를 분석하여 다음 중 하나를 반환한다:
  - ``"single"`` : 단일 에이전트로 처리 가능한 단순 요청
  - ``"multi"``  : 여러 전문 서브 에이전트의 협업이 필요한 복합 요청

구현 전략 — 휴리스틱 기반 (LLM 추가 호출 없음):
  1. 멀티스텝 흐름 연결어가 있으면 즉시 ``"multi"`` 반환.
  2. 서로 다른 역할 도메인(검색/분석/작성) 키워드가 2개 이상 동시에
     등장하면 ``"multi"`` 반환.
  3. 그 외에는 ``"single"`` 반환.

이 분류기는 LLM 호출 없이 수 µs 안에 결정하며, 오분류 비용이 낮다:
  - single 로 잘못 분류 → 오케스트레이터 없이 직접 처리, LLM 이 직접 판단
  - multi 로 잘못 분류  → 오케스트레이터가 delegate 없이 직접 답변 가능

운영 단계에서 정밀도가 필요하면 이 함수를 경량 LLM 1-shot 분류로 교체할 수 있다.
"""
from __future__ import annotations

import re

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


# ---------------------------------------------------------------------------
# 공개 분류기
# ---------------------------------------------------------------------------


def route_request(text: str) -> str:
    """사용자 메시지를 분석해 에이전트 실행 모드를 결정한다.

    **설계 의도 — 마지막 user 메시지 기준 분류**:
    멀티턴 대화에서 이전 턴의 맥락까지 고려하면 분류 정확도가 높아지지만,
    LLM 추가 호출 없이 휴리스틱만 사용하기 때문에 비용이 없다.
    오분류 비용이 낮다는 점도 감안했다:
      - single 로 잘못 분류 → LLM 이 도구 없이도 직접 답변 가능
      - multi 로 잘못 분류  → 오케스트레이터가 delegate 없이 직접 답변 가능
    운영 단계에서 정밀도가 필요하면 전체 대화 기록을 전달하거나
    경량 LLM 1-shot 분류기로 이 함수를 교체할 수 있다.

    Args:
        text: 사용자 입력 메시지 (마지막 user 턴의 content).

    Returns:
        ``"single"`` — 단일 에이전트(SYSTEM_PROMPT + BASE_TOOLS)로 처리.
        ``"multi"``  — 멀티 에이전트 오케스트레이터(ORCHESTRATOR_PROMPT + TOOLS)로 처리.
    """
    # 1. 멀티스텝 연결어가 있으면 즉시 multi
    if _match_any(_CHAIN_PATTERNS, text):
        return "multi"

    # 2. 서로 다른 역할 도메인 키워드가 2개 이상 → multi
    matched_domains = sum(
        1 for domain_patterns in _DOMAIN_GROUPS if _match_any(domain_patterns, text)
    )
    if matched_domains >= 2:
        return "multi"

    return "single"
