# agentic-ai-server

A **FastAPI** server that behaves like a Copilot Agent — it receives a user message,
autonomously calls tools in a loop (ReAct pattern), and returns a final answer.

## Architecture

```
Client  →  POST /chat  →  FastAPI  →  Orchestrator Agent  →  LLM (OpenAI / Ollama / Claude / Gemini)
                                              ↕
                               Tools (calculate, fetch_url, run_python, …)
                                              ↕  delegate_to_agent
                                       Sub-Agent (researcher / analyst / writer)
                                              ↕
                               BASE Tools (same tools, no delegation)
```

### Multi-Agent Architecture

Complex tasks are broken down by the **Orchestrator** and delegated to specialised **Sub-Agents**:

| Role | Specialisation | Available Tools |
|------|---------------|----------------|
| `researcher` | Information retrieval, stock lookup | calculate, fetch_url, search_stock_ticker, get_stock_price |
| `analyst` | Data analysis, calculations | calculate, run_python, fetch_url |
| `writer` | Summarising, composing text | calculate, fetch_url |

**Example workflow — "삼성전자 주가 알려줘":**
1. Orchestrator → `delegate_to_agent(task="삼성전자 종목 코드 찾아줘", role="researcher")`
2. researcher sub-agent → `search_stock_ticker("삼성전자")` → `"005930.KS"`
3. Orchestrator → `delegate_to_agent(task="005930.KS 주가 조회해줘", role="researcher")`
4. researcher sub-agent → `get_stock_price("005930.KS")` → `"₩71,000"`
5. Orchestrator synthesises final answer

## Project structure

```
app/
├── main.py              # FastAPI entry point
├── config.py            # Settings (reads .env)
├── models.py            # Pydantic request/response models
├── session_store.py     # In-memory conversation history
├── agent/
│   ├── loop.py          # Orchestrator agentic loop (async)
│   ├── sync_loop.py     # Synchronous agentic loop (OpenAI-only)
│   ├── sub_agent.py     # Sub-agent runner (multi-agent delegation)
│   ├── llm_factory.py   # LangChain model factory (OpenAI / Ollama / Claude / Gemini)
│   ├── tools.py         # Tool definitions + BASE/full registry split
│   └── prompts.py       # Orchestrator prompt + role-specific sub-agent prompts
└── api/
    ├── chat.py          # POST /chat, POST /chat/stream, POST /chat/session
    └── sessions.py      # GET/DELETE /sessions/{session_id}
```

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure your LLM provider
cp .env.example .env
# Edit .env — set LLM_PROVIDER and the matching API key (see Configuration below)

# 3. Run the server
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for the interactive API documentation.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Run agent, return JSON answer |
| `POST` | `/chat/stream` | Run agent, stream SSE tokens |
| `POST` | `/chat/session` | Create session + run agent |
| `GET`  | `/sessions/{id}` | Retrieve conversation history |
| `DELETE` | `/sessions/{id}` | Delete session |
| `GET`  | `/health` | Health check |

## Example requests

**Simple tool call:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is the square root of 144?"}]}'
```

**Multi-agent stock query:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "삼성전자 주가 알려줘"}]}'
```

```json
{
  "reply": "삼성전자(005930.KS)의 현재 주가는 71,400 KRW (KSC)입니다. 전일 대비 +400 (+0.56%)",
  "tool_calls_made": [
    {"tool_name": "delegate_to_agent", "arguments": {"task": "...", "role": "researcher"}, "result": "..."},
    {"tool_name": "delegate_to_agent", "arguments": {"task": "...", "role": "researcher"}, "result": "..."}
  ],
  "session_id": null
}
```

## Built-in tools

### Base tools (available to all agents)

| Tool | Description |
|------|-------------|
| `calculate` | Evaluate a mathematical expression |
| `get_current_time` | Return current date/time for a timezone |
| `fetch_url` | Fetch text content of a URL |
| `run_python` | Execute a Python snippet |
| `search_stock_ticker` | Search for a stock ticker symbol by company name (Yahoo Finance) |
| `get_stock_price` | Fetch current stock price by ticker symbol (Yahoo Finance) |

### Orchestrator-only tools

| Tool | Description |
|------|-------------|
| `delegate_to_agent` | Delegate a subtask to a specialised sub-agent (`researcher` / `analyst` / `writer`) |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | Provider: `openai` · `ollama` · `claude` · `gemini` |
| `OPENAI_API_KEY` | *(required for openai)* | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama endpoint (OpenAI-compatible) |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `ANTHROPIC_API_KEY` | *(required for claude)* | Anthropic API key |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` | Claude model name |
| `GOOGLE_API_KEY` | *(required for gemini)* | Google AI API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model name |
| `AGENT_MAX_ITERATIONS` | `10` | Max tool-call iterations per request |

## Adding a new tool

1. Implement an `async def my_tool(...) -> str` function in `app/agent/tools.py`.
2. Add it to `BASE_TOOLS_REGISTRY` and `BASE_TOOLS_SCHEMA`.
3. It will automatically be available to sub-agents and (via `TOOLS_REGISTRY`) to the orchestrator.

To add an orchestrator-only tool, add it only to `TOOLS_REGISTRY` / `TOOLS_SCHEMA` (not BASE).
