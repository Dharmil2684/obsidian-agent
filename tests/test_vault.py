"""Tests for vault reader and writer — no Ollama or network required."""
import pytest
from datetime import date

from backend.vault.writer import (
    ensure_vault_structure,
    get_or_create_daily_note,
    append_task_to_daily_note,
    complete_task_in_daily_note,
    add_blocker_to_active,
    resolve_blocker_in_active,
)
from backend.vault.reader import (
    read_daily_note,
    get_unchecked_tasks,
    read_active_blockers,
    get_today_stats,
)
from backend import config


class TestVaultStructure:
    def test_ensure_creates_all_directories(self, vault_path):
        ensure_vault_structure()
        assert (vault_path / "Daily").is_dir()
        assert (vault_path / "Projects" / "Backend").is_dir()
        assert (vault_path / "Projects" / "Frontend").is_dir()
        assert (vault_path / "Projects" / "DataScience").is_dir()
        assert (vault_path / "Weekly").is_dir()
        assert (vault_path / "Blockers" / "resolved").is_dir()
        assert (vault_path / "Templates").is_dir()
        assert (vault_path / "Agent").is_dir()

    def test_ensure_seeds_required_files(self, vault_path):
        ensure_vault_structure()
        assert (vault_path / "Blockers" / "active.md").exists()
        assert (vault_path / "Agent" / "context.md").exists()
        assert (vault_path / "Agent" / "changelog.md").exists()

    def test_idempotent(self, vault_path):
        ensure_vault_structure()
        ensure_vault_structure()  # should not raise


class TestDailyNote:
    def setup_method(self):
        self.today = date.today()

    def test_creates_daily_note(self, vault_path):
        ensure_vault_structure()
        path = get_or_create_daily_note(self.today)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert self.today.strftime("%Y-%m-%d") in content
        assert "## 🎯 Today's Tasks" in content

    def test_does_not_overwrite_existing(self, vault_path):
        ensure_vault_structure()
        path = get_or_create_daily_note(self.today)
        path.write_text("custom content", encoding="utf-8")
        get_or_create_daily_note(self.today)
        assert path.read_text(encoding="utf-8") == "custom content"

    def test_read_returns_none_when_missing(self, vault_path):
        ensure_vault_structure()
        result = read_daily_note(date(2000, 1, 1))
        assert result is None

    def test_read_returns_content_when_exists(self, vault_path):
        ensure_vault_structure()
        get_or_create_daily_note(self.today)
        result = read_daily_note(self.today)
        assert result is not None
        assert "content" in result
        assert "metadata" in result


class TestTaskOperations:
    def test_append_task_backend(self, vault_path):
        ensure_vault_structure()
        append_task_to_daily_note("Auth API refactor", "backend")
        tasks = get_unchecked_tasks()
        assert any("Auth API refactor" in t["description"] for t in tasks)

    def test_append_task_frontend(self, vault_path):
        ensure_vault_structure()
        append_task_to_daily_note("Dashboard layout", "frontend")
        tasks = get_unchecked_tasks()
        assert any("Dashboard layout" in t["description"] for t in tasks)

    def test_append_task_data_science(self, vault_path):
        ensure_vault_structure()
        append_task_to_daily_note("Fix ML pipeline timeout", "data_science")
        tasks = get_unchecked_tasks()
        assert any("Fix ML pipeline" in t["description"] for t in tasks)

    def test_complete_task_marks_checkbox(self, vault_path):
        ensure_vault_structure()
        append_task_to_daily_note("Build login form", "frontend")
        result = complete_task_in_daily_note("Build login form")
        assert result is True
        path = get_or_create_daily_note()
        content = path.read_text(encoding="utf-8")
        assert "- [x] Build login form" in content

    def test_complete_task_returns_false_when_not_found(self, vault_path):
        ensure_vault_structure()
        result = complete_task_in_daily_note("nonexistent task xyz")
        assert result is False

    def test_multiple_tasks_different_domains(self, vault_path):
        ensure_vault_structure()
        append_task_to_daily_note("BE Task", "backend")
        append_task_to_daily_note("FE Task", "frontend")
        append_task_to_daily_note("DS Task", "data_science")
        tasks = get_unchecked_tasks()
        domains = {t["domain"] for t in tasks}
        assert "backend" in domains
        assert "frontend" in domains
        assert "data_science" in domains


class TestBlockerOperations:
    def test_add_blocker_creates_entry(self, vault_path):
        ensure_vault_structure()
        add_blocker_to_active("CORS issue on /auth", "backend")
        blockers = read_active_blockers()
        assert any("CORS issue" in b["description"] for b in blockers)

    def test_add_blocker_updates_daily_note(self, vault_path):
        ensure_vault_structure()
        add_blocker_to_active("Database timeout", "backend")
        note = read_daily_note()
        assert note is not None
        assert "Database timeout" in note["content"]

    def test_resolve_blocker_removes_from_active(self, vault_path):
        ensure_vault_structure()
        add_blocker_to_active("Redis connection refused", "backend")
        result = resolve_blocker_in_active("Redis connection refused")
        assert result is True
        blockers = read_active_blockers()
        assert not any("Redis connection" in b["description"] for b in blockers)

    def test_resolve_blocker_archives_to_resolved(self, vault_path):
        ensure_vault_structure()
        add_blocker_to_active("Kafka consumer lag", "backend")
        resolve_blocker_in_active("Kafka consumer lag")
        resolved_dir = vault_path / "Blockers" / "resolved"
        resolved_files = list(resolved_dir.glob("*.md"))
        assert len(resolved_files) == 1
        content = resolved_files[0].read_text(encoding="utf-8")
        assert "Kafka consumer" in content

    def test_resolve_nonexistent_blocker_returns_false(self, vault_path):
        ensure_vault_structure()
        result = resolve_blocker_in_active("something that was never logged")
        assert result is False


class TestStats:
    def test_stats_empty_vault(self, vault_path):
        ensure_vault_structure()
        stats = get_today_stats()
        assert stats["tasks"] == 0
        assert stats["completed"] == 0
        assert stats["blockers"] == 0

    def test_stats_with_tasks(self, vault_path):
        ensure_vault_structure()
        append_task_to_daily_note("Task A", "backend")
        append_task_to_daily_note("Task B", "frontend")
        stats = get_today_stats()
        assert stats["tasks"] == 2
        assert stats["by_domain"]["backend"] == 1
        assert stats["by_domain"]["frontend"] == 1

    def test_stats_completed_count(self, vault_path):
        ensure_vault_structure()
        append_task_to_daily_note("Task to finish", "backend")
        complete_task_in_daily_note("Task to finish")
        stats = get_today_stats()
        assert stats["completed"] == 1
        assert stats["tasks"] == 0
