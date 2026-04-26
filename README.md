# agentic-ai-server

A **FastAPI** server that behaves like a Copilot Agent — it receives a user message,
autonomously calls tools in a loop (ReAct pattern), and returns a final answer.

## Architecture

```
Client  →  POST /chat  →  FastAPI  →  Agent Loop  →  LLM (OpenAI GPT-4o)
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

# 2. Configure your OpenAI API key
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

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
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model to use |
| `AGENT_MAX_ITERATIONS` | `10` | Max tool-call iterations per request |

## Adding a new tool

1. Implement an `async def my_tool(...) -> str` function in `app/agent/tools.py`.
2. Add it to `TOOLS_REGISTRY`.
3. Append its OpenAI function-calling schema to `TOOLS_SCHEMA`.