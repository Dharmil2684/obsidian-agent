"""Tests for agent tools — no Ollama required."""
import pytest
from datetime import date

from backend.vault.writer import ensure_vault_structure
from backend.agent.tools.task_tools import add_task, complete_task
from backend.agent.tools.blocker_tools import create_blocker, resolve_blocker
from backend.agent.tools.status_tools import get_today_status


class TestTaskTools:
    def test_add_task_success(self, vault_path):
        ensure_vault_structure()
        result = add_task("Auth API refactor", "backend")
        assert result["success"] is True
        assert "Auth API refactor" in result["message"]
        assert "action" in result

    def test_add_task_domain_normalised(self, vault_path):
        ensure_vault_structure()
        result = add_task("Build nav component", "Frontend")  # capitalised
        assert result["success"] is True

    def test_add_task_unknown_domain_defaults_to_backend(self, vault_path):
        ensure_vault_structure()
        result = add_task("Some task", "unknown")
        assert result["success"] is True

    def test_add_task_empty_description(self, vault_path):
        ensure_vault_structure()
        result = add_task("", "backend")
        assert result["success"] is False

    def test_complete_task_found(self, vault_path):
        ensure_vault_structure()
        add_task("Dashboard component", "frontend")
        result = complete_task("Dashboard component")
        assert result["success"] is True
        assert "Dashboard component" in result["message"]

    def test_complete_task_not_found(self, vault_path):
        ensure_vault_structure()
        result = complete_task("ghost task that never existed")
        assert result["success"] is False

    def test_complete_task_partial_match(self, vault_path):
        ensure_vault_structure()
        add_task("Fix the auth middleware", "backend")
        result = complete_task("auth middleware")
        assert result["success"] is True


class TestBlockerTools:
    def test_create_blocker_success(self, vault_path):
        ensure_vault_structure()
        result = create_blocker("CORS issue on /auth", "backend")
        assert result["success"] is True
        assert "CORS issue" in result["message"]
        assert "action" in result

    def test_create_blocker_empty_description(self, vault_path):
        ensure_vault_structure()
        result = create_blocker("", "backend")
        assert result["success"] is False

    def test_resolve_blocker_success(self, vault_path):
        ensure_vault_structure()
        create_blocker("Redis not connecting", "backend")
        result = resolve_blocker("Redis not connecting")
        assert result["success"] is True

    def test_resolve_blocker_not_found(self, vault_path):
        ensure_vault_structure()
        result = resolve_blocker("nonexistent blocker xyz")
        assert result["success"] is False
        assert "Could not find" in result["message"]

    def test_create_and_resolve_full_cycle(self, vault_path):
        ensure_vault_structure()
        create_blocker("Docker compose fails on startup", "backend")
        create_blocker("CSS grid bug in Safari", "frontend")

        r1 = resolve_blocker("Docker compose")
        assert r1["success"] is True

        r2 = resolve_blocker("CSS grid bug")
        assert r2["success"] is True


class TestStatusTools:
    def test_status_empty_day(self, vault_path):
        ensure_vault_structure()
        result = get_today_status()
        assert result["success"] is True
        assert "No tasks" in result["message"]

    def test_status_with_tasks(self, vault_path):
        ensure_vault_structure()
        add_task("Auth refactor", "backend")
        add_task("Nav component", "frontend")
        result = get_today_status()
        assert result["success"] is True
        assert result["stats"]["tasks"] == 2

    def test_status_with_blocker(self, vault_path):
        ensure_vault_structure()
        create_blocker("Kafka lag", "backend")
        result = get_today_status()
        assert result["stats"]["blockers"] == 1

    def test_status_completed_reflected(self, vault_path):
        ensure_vault_structure()
        add_task("Write unit tests", "backend")
        complete_task("Write unit tests")
        result = get_today_status()
        assert result["stats"]["completed"] == 1
        assert result["stats"]["tasks"] == 0
