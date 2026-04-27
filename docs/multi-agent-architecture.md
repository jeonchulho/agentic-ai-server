# 멀티 에이전트 아키텍처: Orchestrator & `delegate_to_agent()`

## 목차

1. [전체 구조 개요](#1-전체-구조-개요)
2. [파일별 역할](#2-파일별-역할)
3. [Orchestrator — `app/agent/loop.py`](#3-orchestrator--appagentlooppy)
4. [`delegate_to_agent()` — `app/agent/tools.py`](#4-delegate_to_agent--appagenttools-py)
5. [Sub-Agent — `app/agent/sub_agent.py`](#5-sub-agent--appagentsub_agentpy)
6. [프롬프트 — `app/agent/prompts.py`](#6-프롬프트--appagentpromptspy)
7. [도구 레지스트리 분리 구조](#7-도구-레지스트리-분리-구조)
8. [실행 흐름 예시](#8-실행-흐름-예시)
9. [순환 임포트 해결 방법](#9-순환-임포트-해결-방법)

---

## 1. 전체 구조 개요

```
사용자 요청
    │
    ▼
┌─────────────────────────────────────────────┐
│  Orchestrator  (app/agent/loop.py)          │
│                                             │
│  시스템 프롬프트: ORCHESTRATOR_PROMPT        │
│  사용 도구: TOOLS_SCHEMA                    │
│            = BASE_TOOLS + delegate_to_agent │
└────────────────────┬────────────────────────┘
                     │ delegate_to_agent(task, role)
                     ▼
          ┌──────────────────────┐
          │  app/agent/tools.py  │
          │  delegate_to_agent() │
          └──────────┬───────────┘
                     │ run_sub_agent(task, role)
                     ▼
┌─────────────────────────────────────────────┐
│  Sub-Agent  (app/agent/sub_agent.py)        │
│                                             │
│  역할별 시스템 프롬프트 주입                 │
│  사용 도구: BASE_TOOLS_SCHEMA               │
│            (delegate_to_agent 제외)         │
│                                             │
│  ┌──────────────────────────────────┐       │
│  │  researcher  │ analyst │ writer  │       │
│  └──────────────────────────────────┘       │
└─────────────────────────────────────────────┘
```

---

## 2. 파일별 역할

| 파일 | 역할 |
|---|---|
| `app/agent/loop.py` | **Orchestrator** 루프 본체. `run_agent()` / `stream_agent()` 구현 |
| `app/agent/tools.py` | 모든 도구 함수 정의. `delegate_to_agent()` 포함. 레지스트리/스키마 관리 |
| `app/agent/sub_agent.py` | **Sub-Agent** 독립 ReAct 루프 실행기. `run_sub_agent()` 구현 |
| `app/agent/prompts.py` | `ORCHESTRATOR_PROMPT` + 역할별 서브 에이전트 프롬프트 정의 |
| `app/agent/llm_factory.py` | LLM 클라이언트 생성 (`@lru_cache` 적용) |

---

## 3. Orchestrator — `app/agent/loop.py`

Orchestrator는 별도 클래스가 아니라 **기존 에이전틱 루프(`run_agent` / `stream_agent`)** 가 그 역할을 합니다.

### 3-1. 시스템 프롬프트 교체

`run_agent()`와 `stream_agent()` 모두, 대화 기록에 시스템 프롬프트가 없으면 **`ORCHESTRATOR_PROMPT`** 를 자동으로 맨 앞에 삽입합니다.

```python
# loop.py — run_agent() 194~197번째 줄
working_messages = list(messages)
if not working_messages or working_messages[0].role != "system":
    working_messages.insert(0, Message(role="system", content=ORCHESTRATOR_PROMPT))
```

`stream_agent()`도 동일한 로직으로 처리됩니다 (276~278번째 줄).

### 3-2. Tool-Bound 모델

Orchestrator가 사용하는 LLM 모델에는 `TOOLS_SCHEMA`(= BASE 도구 + `delegate_to_agent`)가 바인딩되어 있습니다.

```python
# loop.py — 44~62번째 줄
@lru_cache(maxsize=1)
def get_model_with_tools():
    """TOOLS_SCHEMA 가 바인딩된 LLM을 반환한다. 한 번만 생성하고 캐시한다."""
    return get_chat_model().bind_tools(TOOLS_SCHEMA)
```

> **캐싱 이유**: `bind_tools()`는 JSON 스키마 직렬화 + LangChain 래퍼 생성을 수행합니다.  
> `@lru_cache(maxsize=1)` 덕분에 이 비용이 프로세스 수명 동안 단 한 번만 발생합니다.

### 3-3. 루프 동작 흐름

```
┌─────────────────────────────────────────────────┐
│  for _ in range(limit):                         │
│                                                 │
│    response = model_with_tools.ainvoke(msgs)    │
│                                                 │
│    if response.tool_calls:                      │
│        for tc in response.tool_calls:           │
│            result = execute_tool(tc.name, args) │  ← delegate_to_agent 포함
│            msgs.append(ToolMessage(result))     │
│        continue  → 다음 이터레이션              │
│                                                 │
│    else:  ← tool_calls 없음 = 최종 답변         │
│        return final_reply, tool_calls_made      │
│                                                 │
│  raise MaxIterationsExceeded                    │
└─────────────────────────────────────────────────┘
```

### 3-4. `stream_agent()`의 2단계 전략

스트리밍 모드에서는 두 가지 LLM 호출 방식을 혼합합니다:

| 단계 | 방식 | 이유 |
|---|---|---|
| Tool call 감지 | `ainvoke` (비스트리밍) | tool_calls 포함 전체 응답을 받아야 도구 실행 가능 |
| 최종 답변 출력 | `astream` (스트리밍) | 토큰 단위로 SSE 이벤트를 클라이언트에 전송 |

```python
# stream_agent() SSE 이벤트 형식
"event: tool_call\ndata: {\"tool\": \"...\", \"arguments\": {...}}\n\n"
"event: token\ndata: \"텍스트 청크\"\n\n"
"event: done\ndata: [DONE]\n\n"
"event: error\ndata: {\"message\": \"...\"}\n\n"
```

---

## 4. `delegate_to_agent()` — `app/agent/tools.py`

`delegate_to_agent()`는 **`app/agent/tools.py`** 의 236번째 줄에 구현된 `async` 함수입니다.

```python
# tools.py — 236~263번째 줄
async def delegate_to_agent(task: str, role: str = "researcher") -> str:
    """서브태스크를 전문화된 서브 에이전트에게 위임하고 그 결과를 반환한다."""
    try:
        # 순환 임포트 방지 — 런타임 지연 임포트
        from app.agent.sub_agent import run_sub_agent  # noqa: PLC0415

        return await run_sub_agent(task=task, role=role)
    except Exception as exc:
        return f"서브 에이전트 실행 오류 (role={role}): {exc}"
```

### 파라미터

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `task` | `str` | 서브 에이전트에게 위임할 구체적인 작업 설명. 이전 단계 결과가 있다면 여기에 포함시킨다. |
| `role` | `str` | 서브 에이전트의 전문 역할. 기본값: `"researcher"` |

### 지원 역할 (`role`)

| 역할 | 적합한 태스크 | 사용 도구 |
|---|---|---|
| `"researcher"` | 정보 검색, 주가 조회, URL 패치 | `search_stock_ticker`, `get_stock_price`, `fetch_url` |
| `"analyst"` | 데이터 분석, 계산, Python 실행 | `calculate`, `run_python` |
| `"writer"` | 요약, 문서 작성, 번역 | (도구 없이 LLM 직접 작성) |

### LLM 관점에서의 스키마

Orchestrator의 LLM에게는 아래 JSON 스키마로 노출됩니다:

```json
{
  "type": "function",
  "function": {
    "name": "delegate_to_agent",
    "description": "Delegate a subtask to a specialised sub-agent...",
    "parameters": {
      "type": "object",
      "properties": {
        "task": {
          "type": "string",
          "description": "Clear description of the subtask..."
        },
        "role": {
          "type": "string",
          "enum": ["researcher", "analyst", "writer"]
        }
      },
      "required": ["task"]
    }
  }
}
```

---

## 5. Sub-Agent — `app/agent/sub_agent.py`

`run_sub_agent()`는 **독립적인 ReAct 루프**를 실행하는 함수입니다. Orchestrator의 대화 기록과 완전히 격리되어 있습니다.

```python
# sub_agent.py — 52~122번째 줄
async def run_sub_agent(
    task: str,
    role: str = "researcher",
    max_iterations: int = 5,
) -> str:
```

### 동작 흐름

```
1. 역할에 맞는 시스템 프롬프트 선택  (get_sub_agent_prompt(role))
           │
           ▼
2. BASE_TOOLS_SCHEMA 바인딩
   model = get_chat_model().bind_tools(BASE_TOOLS_SCHEMA)
           │
           ▼
3. 독립적인 대화 기록 초기화
   messages = [SystemMessage(system_prompt), HumanMessage(task)]
           │
           ▼
4. ReAct 루프 (최대 max_iterations 회)
   ┌──────────────────────────────────────────┐
   │  response = model.ainvoke(messages)      │
   │                                          │
   │  if tool_calls:                          │
   │      fn = BASE_TOOLS_REGISTRY[tc.name]   │
   │      result = await fn(**tc.args)        │
   │      messages.append(ToolMessage(result))│
   │  else:                                   │
   │      return _extract_text(response)  ←──┘
   └──────────────────────────────────────────┘
           │
           ▼
   SubAgentMaxIterationsExceeded (한도 초과 시)
```

### Orchestrator 루프와의 차이점

| 항목 | Orchestrator (`loop.py`) | Sub-Agent (`sub_agent.py`) |
|---|---|---|
| 도구 세트 | `TOOLS_SCHEMA` (BASE + `delegate_to_agent`) | `BASE_TOOLS_SCHEMA` (`delegate_to_agent` 제외) |
| 스트리밍 | `astream` 지원 | `ainvoke`만 사용 |
| 대화 기록 | 사용자 메시지 히스토리 유지 | task 1개로 초기화, 격리됨 |
| 최대 이터레이션 | `settings.agent_max_iterations` | 기본값 5회 |
| 에러 예외 | `MaxIterationsExceeded` | `SubAgentMaxIterationsExceeded` |

---

## 6. 프롬프트 — `app/agent/prompts.py`

### `ORCHESTRATOR_PROMPT` (18~50번째 줄)

Orchestrator LLM에게 다음을 지시합니다:
- 복잡한 태스크는 단계별로 분해하여 `delegate_to_agent`로 위임
- 단순한 단일 요청은 직접 기본 도구 사용
- 역할별 서브 에이전트 사용 가이드
- 워크플로우 예시 제공 (주식 조회, 이메일 요약 등)

### 역할별 서브 에이전트 프롬프트 (56~99번째 줄)

```
_RESEARCHER_PROMPT  →  "researcher" 역할: 정보 검색·수집 전문
_ANALYST_PROMPT     →  "analyst"   역할: 데이터 분석·계산 전문
_WRITER_PROMPT      →  "writer"    역할: 문서 작성·요약 전문
```

`get_sub_agent_prompt(role: str) -> str` 헬퍼 함수가 역할 이름에 맞는 프롬프트를 반환하며, 알 수 없는 역할은 기본 `SYSTEM_PROMPT`로 대체합니다.

---

## 7. 도구 레지스트리 분리 구조

재귀적 위임(무한 루프)을 방지하기 위해 도구 레지스트리가 두 계층으로 분리되어 있습니다.

```python
# tools.py — 270~436번째 줄

# ── 서브 에이전트 전용 ─────────────────────────────────────────────
BASE_TOOLS_REGISTRY = {
    "calculate":           calculate,
    "get_current_time":    get_current_time,
    "fetch_url":           fetch_url,
    "run_python":          run_python,
    "search_stock_ticker": search_stock_ticker,
    "get_stock_price":     get_stock_price,
    # ❌ "delegate_to_agent" 제외 → 재귀 위임 불가
}
BASE_TOOLS_SCHEMA = [...]   # 위 6개 도구의 JSON 스키마

# ── 오케스트레이터 전용 ───────────────────────────────────────────
TOOLS_REGISTRY = {
    **BASE_TOOLS_REGISTRY,
    "delegate_to_agent": delegate_to_agent,   # ✅ 추가
}
TOOLS_SCHEMA = BASE_TOOLS_SCHEMA + [delegate_to_agent_schema]
```

---

## 8. 실행 흐름 예시

### "삼성전자 주가 알려줘"

```
사용자: "삼성전자 주가 알려줘"
    │
    ▼
[Orchestrator]
  LLM 판단: 복잡한 다단계 태스크 → delegate 필요
    │
    ├─ delegate_to_agent(
    │      task="search_stock_ticker 도구로 '삼성전자'의 종목 코드를 찾아줘",
    │      role="researcher"
    │  )
    │       │
    │       ▼
    │   [Sub-Agent: researcher]
    │     → search_stock_ticker("삼성전자")
    │     ← "005930.KS  (Samsung Electronics, KSC)"
    │
    ├─ delegate_to_agent(
    │      task="get_stock_price 도구로 '005930.KS' 현재 주가를 조회해줘",
    │      role="researcher"
    │  )
    │       │
    │       ▼
    │   [Sub-Agent: researcher]
    │     → get_stock_price("005930.KS")
    │     ← "005930.KS 현재가: 71,400 KRW  (KSC)  전일 대비: +400 (+0.56%)"
    │
    ▼
[Orchestrator]
  두 서브 에이전트의 결과를 종합하여 최종 답변 생성
    ← "삼성전자(005930.KS)의 현재 주가는 71,400원입니다. 전일 대비 400원(+0.56%) 상승했습니다."
```

---

## 9. 순환 임포트 해결 방법

`tools.py`와 `sub_agent.py`는 서로를 참조하는 구조입니다:

```
tools.py        ─ delegate_to_agent()가 sub_agent.py를 호출
sub_agent.py    ─ run_sub_agent()가 tools.py의 레지스트리를 사용
```

이를 해결하기 위해 두 곳 모두 **런타임 지연 임포트(lazy import)** 를 사용합니다:

```python
# tools.py — delegate_to_agent() 내부
async def delegate_to_agent(task: str, role: str = "researcher") -> str:
    from app.agent.sub_agent import run_sub_agent  # ← 함수 호출 시점에 임포트
    return await run_sub_agent(task=task, role=role)

# sub_agent.py — run_sub_agent() 내부
async def run_sub_agent(task, role, max_iterations):
    from app.agent.tools import BASE_TOOLS_REGISTRY, BASE_TOOLS_SCHEMA  # ← 함수 호출 시점에 임포트
    ...
```

모듈 최상단에서 서로 임포트하면 Python 인터프리터가 아직 완전히 로드되지 않은 모듈을 참조하여 `ImportError`가 발생합니다. 함수 본문 안에서 임포트하면 이 문제가 방지됩니다.
