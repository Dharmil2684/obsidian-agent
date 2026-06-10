import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Vault
VAULT_PATH = Path(os.getenv("VAULT_PATH", str(Path.home() / "ObsidianVault")))

# Local LLM (Ollama)
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "nous-hermes3")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "phi3-mini")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Cloud LLM (Groq — free tier)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# API server
API_HOST = os.getenv("API_HOST", "localhost")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Backup
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "3"))
