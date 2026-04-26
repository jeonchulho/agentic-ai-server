# agentic-ai-server

A **FastAPI** server that behaves like a Copilot Agent — it receives a user message,
autonomously calls tools in a loop (ReAct pattern), and returns a final answer.

## Architecture

```
Client  →  POST /chat  →  FastAPI  →  Agent Loop  →  LLM (OpenAI / Ollama / Claude / Gemini)
                                            ↕
                                        Tools (calculate, fetch_url, run_python, …)
```

## Project structure

```
app/
├── main.py              # FastAPI entry point
├── config.py            # Settings (reads .env)
├── models.py            # Pydantic request/response models
├── session_store.py     # In-memory conversation history
├── agent/
│   ├── loop.py          # Agentic loop (tool_call → LLM → … → final answer)
│   ├── llm_factory.py   # LangChain model factory (OpenAI / Ollama / Claude / Gemini)
│   ├── tools.py         # Tool definitions + registry
│   └── prompts.py       # System prompt
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

## Example request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the square root of 144?"}
    ]
  }'
```

```json
{
  "reply": "The square root of 144 is 12.",
  "tool_calls_made": [
    {"tool_name": "calculate", "arguments": {"expression": "sqrt(144)"}, "result": "12.0"}
  ],
  "session_id": null
}
```

## Built-in tools

| Tool | Description |
|------|-------------|
| `calculate` | Evaluate a mathematical expression |
| `get_current_time` | Return current date/time for a timezone |
| `fetch_url` | Fetch text content of a URL |
| `run_python` | Execute a Python snippet |

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
2. Add it to `TOOLS_REGISTRY`.
3. Append its OpenAI function-calling schema to `TOOLS_SCHEMA`.