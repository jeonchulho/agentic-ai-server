# Agentic AI Server — 구현 상세 문서

## 프로젝트 개요

FastAPI 기반의 에이전틱 AI 서버.  
LLM을 반복 호출하며 도구(Tool)를 활용해 요청을 처리하고, 단순 요청은 단일 에이전트가, 복합 요청은 전문 서브 에이전트들이 협업하는 **자동 라우팅 멀티 에이전트 아키텍처**를 구현합니다.

---

## 디렉토리 구조

```
agentic-ai-server/
├── .env.example              # 환경 변수 템플릿
├── requirements.txt          # Python 패키지 의존성
├── README.md
├── docs/
│   ├── multi-agent-architecture.md   # 멀티 에이전트 아키텍처 상세
│   └── implementation.md             # 전체 구현 가이드 (이 문서)
└── app/
    ├── main.py               # FastAPI 앱 진입점
    ├── config.py             # 환경 변수 설정 (Pydantic Settings)
    ├── models.py             # Pydantic 데이터 모델
    ├── session_store.py      # 인메모리 세션 스토어
    ├── api/
    │   ├── chat.py           # 채팅 API 엔드포인트
    │   └── sessions.py       # 세션 관리 엔드포인트
    └── agent/
        ├── llm_factory.py        # LLM 클라이언트 팩토리 (lru_cache)
        ├── prompts.py            # 단일 에이전트 시스템 프롬프트
        ├── router.py             # 단일/멀티 에이전트 라우터
        ├── loop.py               # 비동기 에이전틱 루프 (핵심)
        ├── sync_loop.py          # 동기 에이전틱 루프 (스레드풀용)
        ├── tools.py              # 도구 구현 및 스키마
        ├── sub_agent.py          # 서브 에이전트 실행기
        └── sub_agent_registry.py # 서브 에이전트 역할 레지스트리
```

---

## 1. FastAPI 앱 (`app/main.py`)

- `FastAPI` 앱 생성, CORS 미들웨어 설정
- `/health` 헬스체크 엔드포인트
- `/chat`, `/sessions` 라우터 등록
- `CORS_ALLOW_ORIGINS` 환경 변수로 허용 출처 제어

---

## 2. 설정 관리 (`app/config.py`)

Pydantic `BaseSettings`로 환경 변수를 타입 안전하게 로드합니다.

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `LLM_PROVIDER` | `openai` | 사용할 LLM 프로바이더 |
| `OPENAI_API_KEY` | — | OpenAI API 키 |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI 모델명 |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | 로컬 Ollama 서버 주소 |
| `OLLAMA_MODEL` | `llama3.2` | Ollama 모델명 |
| `ANTHROPIC_API_KEY` | — | Claude API 키 |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` | Claude 모델명 |
| `GOOGLE_API_KEY` | — | Gemini API 키 |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini 모델명 |
| `AGENT_MAX_ITERATIONS` | `10` | 최대 에이전트 루프 횟수 |
| `CORS_ALLOW_ORIGINS` | `*` | 허용 CORS 출처 |

프로바이더 선택 시 해당 API 키가 없으면 서버 시작 시점에 즉시 `ValueError` 발생.

---

## 3. 데이터 모델 (`app/models.py`)

```
Message              role / content / tool_call_id / name / tool_calls
ToolCall             id / type / function
ToolCallFunction     name / arguments (JSON 문자열)
ChatRequest          messages / session_id / max_iterations
ToolCallRecord       tool_name / arguments / result
ChatResponse         reply / tool_calls_made / session_id
SessionHistoryResponse  session_id / messages
```

---

## 4. 세션 스토어 (`app/session_store.py`)

- 인메모리 `dict` 기반 세션 관리
- `asyncio.Lock`으로 동시 접근 보호
- `get_history()` / `append_messages()` / `clear_session()` 제공
- 멀티 프로세스 환경에서는 Redis로 교체 권장

---

## 5. LLM 팩토리 (`app/agent/llm_factory.py`)

`@lru_cache(maxsize=1)`로 LLM 클라이언트를 프로세스 생애 동안 한 번만 생성합니다.

| 프로바이더 | 구현 |
|-----------|------|
| `openai` | `langchain_openai.ChatOpenAI` |
| `ollama` | `ChatOpenAI` + 커스텀 `base_url` (OpenAI 호환) |
| `claude` / `anthropic` | `langchain_anthropic.ChatAnthropic` |
| `gemini` / `google` | `langchain_google_genai.ChatGoogleGenerativeAI` |

모든 프로바이더는 동일한 LangChain 인터페이스(`ainvoke`, `astream`, `bind_tools`)를 사용하므로 호출 측 코드 변경 없음.

---

## 6. 도구 시스템 (`app/agent/tools.py`)

### 구현된 도구 목록

| 도구명 | 설명 |
|--------|------|
| `calculate` | AST 기반 안전한 수식 계산 (Python `math` 함수 지원) |
| `get_current_time` | IANA 타임존 기반 현재 시각 반환 |
| `fetch_url` | URL 텍스트 콘텐츠 가져오기 (최대 4,000자) |
| `run_python` | Python 코드 서브프로세스 실행 (10초 타임아웃) |
| `search_stock_ticker` | Yahoo Finance로 회사명 → 종목 코드 검색 |
| `get_stock_price` | Yahoo Finance로 현재 주가 조회 |
| `delegate_to_agent` | 서브 에이전트에게 서브태스크 위임 (오케스트레이터 전용) |

### 도구 집합 분리

```
BASE_TOOLS_REGISTRY / BASE_TOOLS_SCHEMA
  → 서브 에이전트 전용 (delegate_to_agent 제외 → 재귀 위임 방지)

TOOLS_REGISTRY / TOOLS_SCHEMA
  → 오케스트레이터 전용 (BASE + delegate_to_agent)
```

---

## 7. 서브 에이전트 레지스트리 (`app/agent/sub_agent_registry.py`)

**레지스트리 기반 설계**: `SUB_AGENT_REGISTRY` dict에 역할 항목 하나를 추가하면
오케스트레이터 프롬프트, `delegate_to_agent` 스키마, 서브 에이전트 프롬프트가 **자동으로** 반영됩니다.

### 등록된 역할

| 역할 | 담당 | 사용 도구 |
|------|------|-----------|
| `researcher` | 정보 검색, 주가 조회, URL 패치 | `search_stock_ticker`, `get_stock_price`, `fetch_url` |
| `analyst` | 데이터 분석, 계산, Python 실행 | `calculate`, `run_python` |
| `writer` | 요약, 문서 작성, 번역, 포맷팅 | (없음, 순수 LLM) |

### 주요 함수

| 함수 | 설명 |
|------|------|
| `build_orchestrator_prompt()` | 역할 목록을 포함한 오케스트레이터 시스템 프롬프트 동적 생성 |
| `build_delegate_schema()` | `delegate_to_agent` 도구의 OpenAI function-calling JSON 스키마 동적 생성 |
| `get_sub_agent_prompt(role)` | 역할별 시스템 프롬프트 반환 (알 수 없는 역할은 기본 프롬프트) |

---

## 8. 자동 라우터 (`app/agent/router.py`)

사용자 메시지를 분석해 **단일 에이전트** vs **멀티 에이전트** 실행 모드를 결정합니다.

### 3단계 파이프라인

```
await route_request(text)
  │
  ├─ [1단계] 멀티스텝 연결어 존재? ("그 다음", "and then", "step 1" 등)
  │    → 즉시 "multi" (LLM 호출 없음)
  │
  ├─ [2단계] 서로 다른 도메인 키워드 2개 이상?
  │    도메인: researcher(검색/조회/주가) / analyst(분석/계산/코드) / writer(요약/작성/번역)
  │    → 즉시 "multi" (LLM 호출 없음)
  │
  ├─ [3단계] 도메인 키워드 0개?
  │    → 즉시 "single" (LLM 호출 없음)
  │
  └─ 도메인 키워드 정확히 1개 (애매함)
       → LLM 1-shot 호출 ("yes/no" 판별)
            ├─ "yes" → "multi"
            ├─ "no"  → "single"
            └─ 오류  → "single" (안전 기본값)
```

명확한 경우는 LLM 호출 없이 즉시 결정해 비용과 지연을 최소화하고, 애매한 경우에만 LLM을 폴백으로 사용합니다.

---

## 9. 에이전틱 루프 (`app/agent/loop.py`)

### 성능 최적화

```python
@lru_cache(maxsize=1)
def get_model_with_tools():
    """TOOLS_SCHEMA 바인딩된 오케스트레이터 모델 — 프로세스당 1회 생성."""
    return get_chat_model().bind_tools(TOOLS_SCHEMA)

@lru_cache(maxsize=1)
def get_single_agent_model():
    """BASE_TOOLS_SCHEMA 바인딩된 단일 에이전트 모델 — 프로세스당 1회 생성."""
    return get_chat_model().bind_tools(BASE_TOOLS_SCHEMA)
```

### `run_agent()` 동작 흐름 (비스트리밍)

```
1. route_request()로 single/multi 모드 결정
2. 시스템 프롬프트 자동 삽입 (중복 방지)
3. LLM 호출 → tool_calls 있으면 도구 실행 후 결과 추가 → 반복
4. tool_calls 없으면 최종 답변 반환
5. max_iterations 초과 시 MaxIterationsExceeded 예외
```

### `stream_agent()` SSE 이벤트 형식

| 이벤트 | 데이터 | 설명 |
|--------|--------|------|
| `token` | `"<텍스트 토큰>"` (JSON) | 어시스턴트 텍스트 스트림 |
| `tool_call` | `{"tool": "...", "arguments": {...}}` | 도구 실행 알림 |
| `done` | `[DONE]` | 스트림 종료 |
| `error` | `{"message": "..."}` | 오류 발생 |

tool call 단계는 `ainvoke`(비스트리밍), 최종 답변 단계만 `astream`(토큰 스트리밍) 사용.

---

## 10. 서브 에이전트 실행기 (`app/agent/sub_agent.py`)

오케스트레이터가 `delegate_to_agent` 도구를 호출하면 이 모듈이 실행됩니다.

- 역할별 시스템 프롬프트 주입
- `BASE_TOOLS_SCHEMA`만 바인딩 → `delegate_to_agent` 제외 → **무한 재귀 위임 방지**
- 오케스트레이터 대화와 **완전히 격리된** 독립 대화 기록 유지
- 기본 `max_iterations=5`

---

## 11. API 엔드포인트 (`app/api/chat.py`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/chat` | 비동기 에이전틱 루프 → JSON 응답 |
| `POST` | `/chat/stream` | 비동기 에이전틱 루프 → SSE 스트림 |
| `POST` | `/chat/session` | `/chat`과 동일하나 새 session_id 자동 생성 |
| `POST` | `/chat/sync` | 동기 루프를 스레드풀에서 실행 → JSON 응답 |
| `POST` | `/chat/sync/stream` | 동기 루프를 `iterate_in_threadpool`로 SSE 스트림 |

세션이 있으면 대화 기록을 불러와 이어붙인 후 에이전트 실행. 응답 완료 후 새 메시지를 세션에 저장.

---

## 전체 요청 처리 흐름

```
클라이언트 HTTP 요청
    │
    ▼
FastAPI (chat.py) — 세션 히스토리 병합
    │
    ▼
route_request(마지막 user 메시지)
    │
    ├─ "single" ──→ get_single_agent_model() + SYSTEM_PROMPT
    │
    └─ "multi"  ──→ get_model_with_tools()  + build_orchestrator_prompt()
                             │
                    에이전틱 루프 (loop.py)
                             │
                         LLM 호출
                             │
              ┌──── tool_calls? ────┐
              │ Yes                 │ No
              ▼                     ▼
       execute_tool()          최종 답변 반환
              │
     delegate_to_agent?
              │ Yes
              ▼
       run_sub_agent(role)      ← sub_agent.py
         BASE_TOOLS만 사용
         독립 대화 기록 유지
```

---

## 의존성 (`requirements.txt`)

```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
openai>=1.30.0
pydantic>=2.7.0
pydantic-settings>=2.2.0
python-dotenv>=1.0.0
httpx>=0.27.0
langchain-openai>=0.3.0
langchain-anthropic>=0.3.0
langchain-google-genai>=2.0.0
```

---

## 핵심 설계 원칙

| 원칙 | 구현 |
|------|------|
| 레지스트리 기반 확장성 | `SUB_AGENT_REGISTRY` 항목 추가만으로 프롬프트·스키마 자동 반영 |
| 재귀 위임 방지 | 서브 에이전트는 `BASE_TOOLS`만 사용 (`delegate_to_agent` 미포함) |
| 비용 최적화 라우팅 | 명확한 케이스는 LLM 호출 없이 휴리스틱으로 즉시 결정 |
| LLM 클라이언트 캐싱 | `lru_cache`로 프로세스당 1회 초기화 |
| 이중 스트리밍 지원 | 비동기(SSE) + 동기(threadpool SSE) 두 경로 지원 |
| 프로바이더 추상화 | LangChain 인터페이스로 OpenAI/Claude/Gemini/Ollama 통일 처리 |
