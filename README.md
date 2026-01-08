# Agentic AI Server

**LangGraph + MySQL + Redis + Milvus 기반 대용량 Agentic AI 서버**

## 📋 프로젝트 개요

이 프로젝트는 LangGraph, MySQL, Redis, Milvus를 활용하여 대용량 처리가 가능한 엔터프라이즈급 AI 에이전트 서버를 구축합니다. 문서 처리, 요약, 번역, 데이터 분석 등 다양한 AI 기능을 제공합니다.

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                     │
│  - Summarize API  - Translate API  - Documents API         │
│  - Legacy Data API  - Health Check                         │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              LangGraph Orchestration Layer                  │
│  - Agent Orchestrator  - Task Routing  - Workflow          │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    Agent Layer                              │
│  - Summarize Agent  - Translate Agent                       │
│  - Document Agent   - Analysis Agent                        │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    Data Layer                               │
│  MySQL (메타데이터)  Redis (캐시)  Milvus (벡터 DB)        │
│  Legacy DB (레거시 데이터)                                  │
└─────────────────────────────────────────────────────────────┘
```

## ✨ 주요 기능

### 1. 문서 처리 (Document Processing)
- **지원 형식**: PDF, WORD (DOC/DOCX), PowerPoint (PPT/PPTX), Excel (XLS/XLSX), HWP, TEXT
- **기능**: 문서 파싱, 텍스트 추출, 청크 분할, 벡터 임베딩 생성

### 2. AI 에이전트 기능
- **요약 (Summarization)**: 텍스트 및 문서 요약
- **번역 (Translation)**: 다국어 번역 지원
- **문서 분석**: 문서 내용 분석 및 인사이트 추출
- **데이터 분석**: Legacy 데이터베이스 분석

### 3. Legacy Database 연동
- 쪽지 (Messages)
- 채팅 (Chats)
- 일정 (Schedules)
- 메일 (Emails)
- 프로젝트 (Projects)

### 4. 벡터 검색 (Vector Search)
- Milvus 기반 의미론적 문서 검색
- 문서 임베딩 및 유사도 검색

## 🛠️ 기술 스택

- **Backend**: FastAPI, Python 3.11+
- **AI/ML**: LangChain, LangGraph, OpenAI GPT-4
- **Database**: MySQL 8.0 (메타데이터)
- **Cache**: Redis 7.x
- **Vector DB**: Milvus 2.3+
- **Embedding**: Sentence Transformers
- **Document Parsing**: PyPDF2, python-docx, python-pptx, openpyxl, hwp5
- **Deployment**: Docker, Docker Compose

## 📦 설치 및 실행

### 사전 요구사항

- Docker & Docker Compose
- Python 3.11+ (로컬 개발용)
- OpenAI API Key

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/jeonchulho/agentic-ai-server.git
cd agentic-ai-server

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 OPENAI_API_KEY 설정
```

### 2. Docker Compose로 실행

```bash
# 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f app

# 서비스 중지
docker-compose down
```

### 3. 로컬 개발 환경

```bash
# 가상 환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 애플리케이션 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 🚀 API 사용법

### API 문서

서버 실행 후 다음 URL에서 Swagger UI를 통해 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 주요 엔드포인트

#### 1. 텍스트 요약

```bash
curl -X POST "http://localhost:8000/api/v1/summarize/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "요약할 긴 텍스트...",
    "max_length": 100
  }'
```

#### 2. 번역

```bash
curl -X POST "http://localhost:8000/api/v1/translate" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, world!",
    "source_language": "en",
    "target_language": "ko"
  }'
```

#### 3. 문서 업로드

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@document.pdf"
```

#### 4. 문서 파싱

```bash
curl -X POST "http://localhost:8000/api/v1/documents/parse/1"
```

#### 5. Legacy 데이터 요약

```bash
curl -X GET "http://localhost:8000/api/v1/legacy/summary/messages"
```

#### 6. 헬스 체크

```bash
curl -X GET "http://localhost:8000/health"
```

## 📁 프로젝트 구조

```
agentic-ai-server/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── summarize.py      # 요약 API
│   │       ├── translate.py      # 번역 API
│   │       ├── documents.py      # 문서 처리 API
│   │       └── legacy.py         # Legacy DB API
│   ├── agents/
│   │   ├── orchestrator.py       # 에이전트 오케스트레이터
│   │   ├── summarize_agent.py    # 요약 에이전트
│   │   ├── translate_agent.py    # 번역 에이전트
│   │   ├── document_agent.py     # 문서 처리 에이전트
│   │   └── analysis_agent.py     # 분석 에이전트
│   ├── parsers/
│   │   ├── base_parser.py        # 파서 베이스 클래스
│   │   ├── pdf_parser.py         # PDF 파서
│   │   ├── word_parser.py        # Word 파서
│   │   ├── ppt_parser.py         # PowerPoint 파서
│   │   ├── excel_parser.py       # Excel 파서
│   │   ├── hwp_parser.py         # HWP 파서
│   │   └── text_parser.py        # 텍스트 파서
│   ├── services/
│   │   ├── summarize_service.py  # 요약 서비스
│   │   ├── translate_service.py  # 번역 서비스
│   │   ├── document_service.py   # 문서 서비스
│   │   └── legacy_service.py     # Legacy DB 서비스
│   ├── database/
│   │   ├── mysql_client.py       # MySQL 클라이언트
│   │   ├── redis_client.py       # Redis 클라이언트
│   │   ├── milvus_client.py      # Milvus 클라이언트
│   │   └── legacy_db_connector.py # Legacy DB 커넥터
│   ├── models/
│   │   └── schemas.py            # Pydantic 스키마
│   ├── config/
│   │   └── settings.py           # 설정 파일
│   └── main.py                   # FastAPI 애플리케이션
├── tests/                        # 테스트 코드
├── docker/                       # Docker 설정
├── requirements.txt              # Python 의존성
├── docker-compose.yml            # Docker Compose 설정
├── Dockerfile                    # Docker 이미지 빌드
├── .env.example                  # 환경 변수 예시
├── .gitignore                    # Git 제외 파일
└── README.md                     # 프로젝트 문서
```

## 🔧 개발 가이드

### 새로운 에이전트 추가

1. `app/agents/` 디렉토리에 새 에이전트 파일 생성
2. `BaseAgent` 또는 LangChain 기반 에이전트 구현
3. `app/services/`에 해당 서비스 레이어 추가
4. `app/api/v1/`에 API 엔드포인트 추가

### 새로운 파서 추가

1. `app/parsers/` 디렉토리에 새 파서 파일 생성
2. `BaseParser` 클래스 상속
3. `parse()` 메서드 구현
4. `ParserFactory`에 파서 등록

### 캐싱 전략

Redis를 사용한 캐싱이 기본적으로 구현되어 있습니다:

- 요약 결과: 1시간 캐시
- 번역 결과: 1시간 캐시
- Legacy 데이터 요약: 30분 캐시

## 🧪 테스트

```bash
# 전체 테스트 실행
pytest

# 특정 테스트 파일 실행
pytest tests/test_parsers.py

# 커버리지와 함께 실행
pytest --cov=app tests/
```

## 📊 성능 최적화

### 1. 비동기 처리
- FastAPI의 async/await 사용
- 병렬 처리를 위한 비동기 작업

### 2. 캐싱
- Redis 기반 결과 캐싱
- 중복 요청 최소화

### 3. 벡터 검색
- Milvus를 통한 고속 벡터 검색
- 문서 청크 단위 임베딩

### 4. 데이터베이스 최적화
- 연결 풀링
- 인덱스 활용

## 🔒 보안

- API 키 환경 변수 관리
- CORS 설정
- JWT 인증 (향후 구현 예정)
- SQL Injection 방지 (SQLAlchemy ORM)

## 📝 환경 변수

주요 환경 변수는 `.env.example`을 참조하세요:

- `OPENAI_API_KEY`: OpenAI API 키 (필수)
- `MYSQL_*`: MySQL 데이터베이스 설정
- `REDIS_*`: Redis 캐시 설정
- `MILVUS_*`: Milvus 벡터 DB 설정
- `LEGACY_DB_*`: Legacy 데이터베이스 설정

## 🤝 기여

기여는 언제나 환영합니다! Pull Request를 보내주세요.

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 📧 문의

이슈나 질문이 있으시면 GitHub Issues를 이용해주세요.

---

**Built with ❤️ using LangGraph, FastAPI, and modern AI technologies**