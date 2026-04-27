"""LangChain 채팅 모델 인스턴스를 생성하는 팩토리 모듈.

지원 프로바이더 (``LLM_PROVIDER`` 환경 변수로 선택):
- ``openai``  (기본값) — OpenAI ChatGPT  (``langchain_openai.ChatOpenAI``)
- ``ollama``           — 로컬 Ollama 서버, OpenAI 호환 엔드포인트 사용
- ``claude``           — Anthropic Claude (``langchain_anthropic.ChatAnthropic``)
- ``gemini``           — Google Gemini   (``langchain_google_genai.ChatGoogleGenerativeAI``)

성능 최적화:
    ``get_chat_model()`` 함수에 ``@lru_cache(maxsize=1)`` 데코레이터를 적용한다.
    LLM 클라이언트 객체는 내부적으로 HTTP 커넥션 풀, 인증 헤더 빌더 등 무거운
    리소스를 초기화하기 때문에, 요청마다 새로 생성하면 수 ms의 불필요한
    오버헤드가 발생할 수 있다.  캐싱을 통해 프로세스 수명 동안 단 한 번만
    생성하고 이후 호출에서는 즉시 동일 인스턴스를 반환한다.

    maxsize=1 의미:
        인자가 없는 함수이므로 캐시 슬롯은 항상 1개면 충분하다.
        설정이 바뀌지 않는 한(= 프로세스가 살아있는 동안) 재사용이 안전하다.
"""
from __future__ import annotations

from functools import lru_cache  # 표준 라이브러리의 메모이제이션 데코레이터

from langchain_core.language_models import BaseChatModel

from app.config import settings


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """설정된 프로바이더에 맞는 LangChain ``BaseChatModel`` 을 반환한다.

    첫 번째 호출 시에만 실제 객체를 생성하고 이후 호출은 캐시된 인스턴스를
    즉시 반환한다.  따라서 ``run_agent`` / ``stream_agent`` 가 요청마다
    이 함수를 호출하더라도 LLM 클라이언트 초기화 비용이 중복 발생하지 않는다.

    Returns:
        LangChain BaseChatModel 서브클래스 인스턴스.
        모든 프로바이더가 동일한 인터페이스(``ainvoke``, ``astream``,
        ``bind_tools``)를 구현하므로 호출 측에서는 프로바이더 종류를 알 필요가 없다.

    Raises:
        ValueError:  ``LLM_PROVIDER`` 가 지원하지 않는 값으로 설정된 경우.
        ImportError: 해당 프로바이더의 LangChain 통합 패키지가 설치되지 않은 경우.
    """
    # 환경 변수에서 읽어온 프로바이더 이름을 소문자로 정규화
    provider = settings.llm_provider.lower()

    # ── OpenAI ──────────────────────────────────────────────────────────────
    if provider == "openai":
        # langchain-openai 패키지를 지연 임포트(lazy import)한다.
        # 프로바이더별로 필요한 패키지만 임포트함으로써, 해당 패키지가
        # 설치되지 않은 환경에서도 다른 프로바이더는 정상 동작하도록 한다.
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        return ChatOpenAI(
            api_key=settings.openai_api_key,  # OPENAI_API_KEY 환경 변수
            model=settings.openai_model,      # 기본값: "gpt-4o-mini"
        )

    # ── Ollama (로컬 LLM) ───────────────────────────────────────────────────
    if provider == "ollama":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        # Ollama는 OpenAI 호환 REST API를 노출하므로 ChatOpenAI 를 재사용한다.
        # base_url 만 로컬 Ollama 서버 주소로 변경하고 api_key 는 더미 값을 전달한다
        # (Ollama 는 인증키 없이도 동작하지만, 라이브러리가 빈 문자열을 거부하므로
        #  임의의 문자열 "ollama" 를 사용한다).
        return ChatOpenAI(
            api_key="ollama",                     # 인증 불필요 — 더미 값
            base_url=settings.ollama_base_url,    # 예: "http://localhost:11434/v1"
            model=settings.ollama_model,          # 예: "llama3.2"
        )

    # ── Anthropic Claude ────────────────────────────────────────────────────
    if provider in ("claude", "anthropic"):
        # langchain-anthropic 패키지 필요
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

        return ChatAnthropic(
            api_key=settings.anthropic_api_key,  # ANTHROPIC_API_KEY 환경 변수
            model=settings.claude_model,          # 예: "claude-3-5-sonnet-20241022"
        )

    # ── Google Gemini ───────────────────────────────────────────────────────
    if provider in ("gemini", "google"):
        # langchain-google-genai 패키지 필요
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

        return ChatGoogleGenerativeAI(
            google_api_key=settings.google_api_key,  # GOOGLE_API_KEY 환경 변수
            model=settings.gemini_model,              # 예: "gemini-1.5-flash"
        )

    # 알 수 없는 프로바이더명 — 명확한 에러 메시지와 함께 즉시 실패
    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Valid options: openai, ollama, claude, gemini"
    )
