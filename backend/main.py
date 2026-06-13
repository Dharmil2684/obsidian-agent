from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from backend.agent.core import process_message
from backend.agent.tools.status_tools import get_today_status
from backend.vault.writer import ensure_vault_structure
from backend.vault.reader import get_today_stats, read_daily_note
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
    version="1.0.0-phase4",
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
    return {"status": "ok", "service": "obsidian-agent", "phase": 4}


# ---------------------------------------------------------------------------
# Settings — read & write .env values at runtime
# ---------------------------------------------------------------------------

class SettingsResponse(BaseModel):
    vault_path: str
    local_model: str
    groq_model: str
    groq_key_set: bool
    api_port: int
    max_backups: int
    ollama_base_url: str


class SettingsUpdateRequest(BaseModel):
    vault_path: str | None = None
    local_model: str | None = None
    max_backups: int | None = None


@app.get("/settings", response_model=SettingsResponse)
async def get_settings():
    return SettingsResponse(
        vault_path      = str(config.VAULT_PATH),
        local_model     = config.LOCAL_MODEL,
        groq_model      = config.GROQ_MODEL,
        groq_key_set    = bool(config.GROQ_API_KEY),
        api_port        = config.API_PORT,
        max_backups     = config.MAX_BACKUPS,
        ollama_base_url = config.OLLAMA_BASE_URL,
    )


@app.post("/settings")
async def update_settings(req: SettingsUpdateRequest):
    """
    Write changed values back to .env and update the live config module.
    Only vault_path, local_model, max_backups are user-editable at runtime.
    """
    env_path = Path(".env")
    if not env_path.exists():
        raise HTTPException(status_code=404, detail=".env file not found")

    lines    = env_path.read_text(encoding="utf-8").splitlines()
    updates  = {}

    if req.vault_path is not None:
        vault = Path(req.vault_path)
        if not vault.exists():
            raise HTTPException(status_code=400, detail=f"Vault path does not exist: {req.vault_path}")
        updates["VAULT_PATH"]   = req.vault_path
        config.VAULT_PATH       = vault
        ensure_vault_structure()

    if req.local_model is not None:
        updates["LOCAL_MODEL"]  = req.local_model
        config.LOCAL_MODEL      = req.local_model

    if req.max_backups is not None:
        if req.max_backups < 1:
            raise HTTPException(status_code=400, detail="max_backups must be >= 1")
        updates["MAX_BACKUPS"]  = str(req.max_backups)
        config.MAX_BACKUPS      = req.max_backups

    # Rewrite .env preserving all existing lines
    new_lines = []
    written   = set()
    for line in lines:
        key = line.split("=")[0].strip()
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            written.add(key)
        else:
            new_lines.append(line)
    # Append any keys not yet present in .env
    for key, val in updates.items():
        if key not in written:
            new_lines.append(f"{key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return {"success": True, "updated": list(updates.keys())}


# ---------------------------------------------------------------------------
# Context refresh — re-run vault scanner to update Agent/context.md
# ---------------------------------------------------------------------------

@app.post("/refresh-context")
async def refresh_context():
    """Re-scan vault and regenerate Agent/context.md."""
    try:
        from scripts.generate_context import generate_context
        generate_context(config.VAULT_PATH)
        return {"success": True, "message": "Agent/context.md refreshed from vault scan."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# First-run detection
# ---------------------------------------------------------------------------

@app.get("/first-run")
async def first_run_check():
    """
    Returns is_first_run=True when the vault has no daily notes yet.
    The UI uses this to show an onboarding welcome message.
    """
    daily_dir   = config.VAULT_PATH / "Daily"
    note_count  = len(list(daily_dir.glob("*.md"))) if daily_dir.exists() else 0
    context_set = (config.VAULT_PATH / "Agent" / "context.md").exists()
    return {
        "is_first_run": note_count == 0,
        "note_count":   note_count,
        "context_set":  context_set,
        "vault_path":   str(config.VAULT_PATH),
    }


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
