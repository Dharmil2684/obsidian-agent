from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from backend.agent.core import process_message
from backend.agent.tools.status_tools import get_today_status
from backend.vault.writer import ensure_vault_structure
from backend import config


# ---------------------------------------------------------------------------
# Lifespan — bootstrap vault on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_vault_structure()
    yield


app = FastAPI(
    title="Obsidian Agent API",
    version="1.0.0-phase1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "app://.", "file://"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v.strip()


class ChatResponse(BaseModel):
    response: str
    intent: str
    domain: str
    action: str | None = None
    success: bool = True
    needs_clarification: bool = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await process_message(request.message)
    return ChatResponse(**result)


@app.get("/status")
async def status():
    return get_today_status()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "obsidian-agent", "phase": 1}


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True,
    )
