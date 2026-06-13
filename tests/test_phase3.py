"""
Phase 3 tests — carry_tasks_forward, EOD summary, weekly summary,
weekly note creation, EOD note writing.

All vault I/O is redirected to a temp directory via the `vault_path` fixture.
LLM calls (Ollama + Groq) are mocked so tests never hit the network.
"""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from backend import config
from backend.vault.writer import ensure_vault_structure, append_task_to_daily_note, get_or_create_daily_note
from backend.vault.reader import get_unchecked_tasks


# =============================================================================
# carry_tasks_forward
# =============================================================================

class TestCarryTasksForward:

    def test_carry_simple(self, vault_path):
        ensure_vault_structure()
        yesterday = date.today() - timedelta(days=1)

        # Add two tasks to yesterday
        append_task_to_daily_note("Fix auth bug",     "backend",  yesterday)
        append_task_to_daily_note("Update CSS",       "frontend", yesterday)

        from backend.agent.tools.carry_tools import carry_tasks_forward
        result = carry_tasks_forward(from_date=yesterday)

        assert result["success"] is True
        assert result["carried"] == 2

        # Both should now appear in today's note
        today_tasks = [t["description"] for t in get_unchecked_tasks(date.today())]
        assert "Fix auth bug" in today_tasks
        assert "Update CSS" in today_tasks

    def test_carry_skips_duplicates(self, vault_path):
        ensure_vault_structure()
        yesterday = date.today() - timedelta(days=1)

        append_task_to_daily_note("Write tests", "backend", yesterday)
        # Same task already in today
        append_task_to_daily_note("Write tests", "backend", date.today())

        from backend.agent.tools.carry_tools import carry_tasks_forward
        result = carry_tasks_forward(from_date=yesterday)

        assert result["success"] is True
        assert result["skipped"] == 1
        assert result["carried"] == 0

    def test_carry_from_empty_day(self, vault_path):
        ensure_vault_structure()
        yesterday = date.today() - timedelta(days=1)
        # No note for yesterday

        from backend.agent.tools.carry_tools import carry_tasks_forward
        result = carry_tasks_forward(from_date=yesterday)

        assert result["success"] is False

    def test_carry_from_completed_tasks_only(self, vault_path):
        """A note where everything is done → zero carried."""
        ensure_vault_structure()
        yesterday = date.today() - timedelta(days=1)
        # Create the note then mark the task done
        append_task_to_daily_note("Deploy service", "backend", yesterday)

        from backend.vault.writer import complete_task_in_daily_note
        complete_task_in_daily_note("Deploy service", yesterday)

        from backend.agent.tools.carry_tools import carry_tasks_forward
        result = carry_tasks_forward(from_date=yesterday)

        assert result["success"] is True
        assert "all caught up" in result["message"]

    def test_carry_same_date_rejected(self, vault_path):
        ensure_vault_structure()
        from backend.agent.tools.carry_tools import carry_tasks_forward
        today = date.today()
        result = carry_tasks_forward(from_date=today, to_date=today)
        assert result["success"] is False
        assert "same" in result["message"].lower()

    def test_carry_preserves_domain(self, vault_path):
        ensure_vault_structure()
        yesterday = date.today() - timedelta(days=1)
        append_task_to_daily_note("Train model", "data_science", yesterday)

        from backend.agent.tools.carry_tools import carry_tasks_forward
        result = carry_tasks_forward(from_date=yesterday)

        tasks = get_unchecked_tasks(date.today())
        ds_tasks = [t for t in tasks if t["domain"] == "data_science"]
        assert any("Train model" in t["description"] for t in ds_tasks)


# =============================================================================
# EOD summary writer
# =============================================================================

class TestEODSummaryWriter:

    def test_write_eod_summary_to_note(self, vault_path):
        ensure_vault_structure()
        from backend.vault.writer import write_eod_summary
        path = write_eod_summary("## Great day!\nGot stuff done.")
        content = path.read_text(encoding="utf-8")
        assert "Great day!" in content
        assert "🌙 EOD Summary" in content

    def test_write_eod_summary_overwrites_existing(self, vault_path):
        ensure_vault_structure()
        from backend.vault.writer import write_eod_summary
        write_eod_summary("First summary.")
        write_eod_summary("Second summary — replaced.")
        path = get_or_create_daily_note()
        content = path.read_text(encoding="utf-8")
        assert "Second summary" in content
        assert "First summary" not in content


# =============================================================================
# Weekly note writer
# =============================================================================

class TestWeeklyNoteWriter:

    def test_creates_weekly_note(self, vault_path):
        ensure_vault_structure()
        from backend.vault.writer import get_or_create_weekly_note
        path = get_or_create_weekly_note()
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Week" in content
        assert "AI Weekly Summary" in content

    def test_weekly_note_idempotent(self, vault_path):
        ensure_vault_structure()
        from backend.vault.writer import get_or_create_weekly_note
        p1 = get_or_create_weekly_note()
        p1.write_text("custom content")
        p2 = get_or_create_weekly_note()
        assert p2.read_text() == "custom content"  # not overwritten

    def test_write_weekly_summary(self, vault_path):
        ensure_vault_structure()
        from backend.vault.writer import write_weekly_summary
        path = write_weekly_summary("## Weekly Wins\n- Shipped feature X")
        content = path.read_text(encoding="utf-8")
        assert "Shipped feature X" in content
        assert "AI Weekly Summary" in content

    def test_write_weekly_summary_overwrites(self, vault_path):
        ensure_vault_structure()
        from backend.vault.writer import write_weekly_summary
        write_weekly_summary("First weekly.")
        write_weekly_summary("Second weekly — replaced.")
        from backend.vault.writer import get_or_create_weekly_note
        content = get_or_create_weekly_note().read_text(encoding="utf-8")
        assert "Second weekly" in content
        assert "First weekly" not in content


# =============================================================================
# generate_daily_summary — mock Ollama
# =============================================================================

class TestGenerateDailySummary:

    @pytest.fixture(autouse=True)
    def _mock_ollama(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": "Great day! You shipped the auth feature. Rest well."}
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.agent.tools.summary_tools.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__  = AsyncMock(return_value=False)
            instance.post       = AsyncMock(return_value=mock_resp)
            MockClient.return_value = instance
            yield

    async def test_summary_writes_to_note(self, vault_path):
        ensure_vault_structure()
        append_task_to_daily_note("Build auth", "backend")
        from backend.vault.writer import complete_task_in_daily_note
        complete_task_in_daily_note("Build auth")

        from backend.agent.tools.summary_tools import generate_daily_summary
        result = await generate_daily_summary()

        assert result["success"] is True
        assert "Great day" in result["message"]

        path = get_or_create_daily_note()
        assert "Great day" in path.read_text(encoding="utf-8")

    async def test_summary_returns_text_on_success(self, vault_path):
        ensure_vault_structure()
        from backend.agent.tools.summary_tools import generate_daily_summary
        result = await generate_daily_summary()
        assert result["success"] is True
        assert len(result["message"]) > 0


# =============================================================================
# generate_daily_summary — Ollama offline
# =============================================================================

class TestGenerateDailySummaryOffline:

    async def test_ollama_offline_returns_failure(self, vault_path):
        ensure_vault_structure()

        import httpx as _httpx
        with patch("backend.agent.tools.summary_tools.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__  = AsyncMock(return_value=False)
            instance.post       = AsyncMock(side_effect=_httpx.ConnectError("offline"))
            MockClient.return_value = instance

            from backend.agent.tools.summary_tools import generate_daily_summary
            result = await generate_daily_summary()

        assert result["success"] is False
        assert "unavailable" in result["message"].lower() or "offline" in result["message"].lower()


# =============================================================================
# generate_weekly_summary — mock Groq
# =============================================================================

class TestGenerateWeeklySummary:

    @pytest.fixture(autouse=True)
    def _mock_groq(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "## Weekly Wins\n- Shipped 3 features"}}]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.agent.tools.summary_tools.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__  = AsyncMock(return_value=False)
            instance.post       = AsyncMock(return_value=mock_resp)
            MockClient.return_value = instance
            yield

    async def test_weekly_writes_to_note(self, vault_path, monkeypatch):
        ensure_vault_structure()
        monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")

        from backend.agent.tools.summary_tools import generate_weekly_summary
        result = await generate_weekly_summary()

        assert result["success"] is True
        assert "Weekly Wins" in result["message"]

        from backend.vault.writer import get_or_create_weekly_note
        content = get_or_create_weekly_note().read_text(encoding="utf-8")
        assert "Shipped 3 features" in content

    async def test_weekly_fails_gracefully_without_key(self, vault_path, monkeypatch):
        ensure_vault_structure()
        monkeypatch.setattr(config, "GROQ_API_KEY", "")

        from backend.agent.tools.summary_tools import generate_weekly_summary
        result = await generate_weekly_summary()

        assert result["success"] is False
        assert "GROQ_API_KEY" in result["message"] or "Groq" in result["message"]
