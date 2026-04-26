from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.sessions import router as sessions_router
from app.config import settings

app = FastAPI(
    title="Agentic AI Server",
    description=(
        "A FastAPI server that runs an agentic loop powered by OpenAI GPT-4o. "
        "The agent autonomously calls tools and iterates until it produces a final answer."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(sessions_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
