"""
Phase 4 tests — /settings, /refresh-context, /first-run endpoints,
vault scanner (generate_context.py), useFirstRun hook (backend side only).
"""
import pytest
from pathlib import Path
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from backend import config
from backend.vault.writer import ensure_vault_structure, append_task_to_daily_note
from backend.main import app


# =============================================================================
# Helpers
# =============================================================================

@pytest.fixture
async def client(vault_path):
    """Async test client wired to a temp vault."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# =============================================================================
# GET /settings
# =============================================================================

class TestGetSettings:

    async def test_returns_expected_keys(self, client):
        resp = await client.get("/settings")
        assert resp.status_code == 200
        data = resp.json()
        for key in ("vault_path", "local_model", "groq_model", "groq_key_set",
                    "api_port", "max_backups", "ollama_base_url"):
            assert key in data

    async def test_groq_key_set_reflects_config(self, client, monkeypatch):
        monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
        resp = await client.get("/settings")
        assert resp.json()["groq_key_set"] is True

    async def test_groq_key_unset_is_false(self, client, monkeypatch):
        monkeypatch.setattr(config, "GROQ_API_KEY", "")
        resp = await client.get("/settings")
        assert resp.json()["groq_key_set"] is False

    async def test_vault_path_reflects_config(self, client, vault_path):
        resp = await client.get("/settings")
        assert str(vault_path) in resp.json()["vault_path"]


# =============================================================================
# POST /settings
# =============================================================================

class TestPostSettings:

    async def test_update_local_model(self, client, tmp_path, vault_path):
        # Write a minimal .env so the endpoint can find it
        env = Path(".env")
        original = env.read_text(encoding="utf-8") if env.exists() else ""
        env.write_text("LOCAL_MODEL=hermes3\n", encoding="utf-8")

        try:
            resp = await client.post("/settings", json={"local_model": "phi3"})
            assert resp.status_code == 200
            assert "LOCAL_MODEL" in resp.json()["updated"]
            assert config.LOCAL_MODEL == "phi3"
        finally:
            # Restore
            env.write_text(original, encoding="utf-8")
            config.LOCAL_MODEL = "hermes3"

    async def test_invalid_max_backups(self, client):
        resp = await client.post("/settings", json={"max_backups": 0})
        assert resp.status_code == 400

    async def test_nonexistent_vault_path_rejected(self, client):
        resp = await client.post("/settings", json={"vault_path": "C:/does/not/exist/xyz"})
        assert resp.status_code == 400

    async def test_valid_vault_path_accepted(self, client, vault_path):
        env = Path(".env")
        original = env.read_text(encoding="utf-8") if env.exists() else ""
        env.write_text(f"VAULT_PATH={vault_path}\n", encoding="utf-8")
        try:
            resp = await client.post("/settings", json={"vault_path": str(vault_path)})
            assert resp.status_code == 200
        finally:
            env.write_text(original, encoding="utf-8")


# =============================================================================
# GET /first-run
# =============================================================================

class TestFirstRun:

    async def test_first_run_true_when_no_notes(self, client, vault_path):
        ensure_vault_structure()
        resp = await client.get("/first-run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_first_run"] is True
        assert data["note_count"] == 0

    async def test_first_run_false_after_note_created(self, client, vault_path):
        ensure_vault_structure()
        append_task_to_daily_note("Some task", "backend")

        resp = await client.get("/first-run")
        data = resp.json()
        assert data["is_first_run"] is False
        assert data["note_count"] >= 1

    async def test_first_run_returns_vault_path(self, client, vault_path):
        ensure_vault_structure()
        resp = await client.get("/first-run")
        assert str(vault_path) in resp.json()["vault_path"]


# =============================================================================
# POST /refresh-context
# =============================================================================

class TestRefreshContext:

    async def test_refresh_writes_context_file(self, client, vault_path):
        ensure_vault_structure()
        # Patch the scanner to avoid side-effects
        with patch("scripts.generate_context.generate_context") as mock_gen:
            mock_gen.return_value = None
            resp = await client.post("/refresh-context")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# =============================================================================
# Vault scanner (generate_context.py)
# =============================================================================

class TestVaultScanner:

    def test_scan_empty_vault(self, vault_path):
        ensure_vault_structure()
        from scripts.generate_context import scan_vault
        info = scan_vault(vault_path)
        assert "projects" in info
        assert "technologies" in info
        assert isinstance(info["technologies"], list)

    def test_scan_detects_tech_keywords(self, vault_path):
        ensure_vault_structure()
        daily = vault_path / "Daily" / "2026-01-01.md"
        daily.write_text("worked on fastapi and redis today", encoding="utf-8")

        from scripts.generate_context import scan_vault
        info = scan_vault(vault_path)
        assert "fastapi" in info["technologies"]
        assert "redis" in info["technologies"]

    def test_generate_context_writes_file(self, vault_path):
        ensure_vault_structure()
        from scripts.generate_context import generate_context
        generate_context(vault_path)

        ctx = vault_path / "Agent" / "context.md"
        assert ctx.exists()
        content = ctx.read_text(encoding="utf-8")
        assert "Agent Context" in content
        assert "generated" in content

    def test_generate_context_overwrites_existing(self, vault_path):
        ensure_vault_structure()
        ctx = vault_path / "Agent" / "context.md"
        ctx.write_text("old content", encoding="utf-8")

        from scripts.generate_context import generate_context
        generate_context(vault_path)
        assert "old content" not in ctx.read_text(encoding="utf-8")
        assert "Agent Context" in ctx.read_text(encoding="utf-8")
