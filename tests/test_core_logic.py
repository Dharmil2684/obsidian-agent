"""Tests for core.py routing — uses mocked classify_intent so no LLM needed."""
import pytest
from unittest.mock import patch, AsyncMock

from backend.vault.writer import ensure_vault_structure


def _clf(intent, domain="backend", description="Test Task", tasks=None,
         is_correction=False, needs_clarification=False, clarification_question=None):
    """Build a mock classify_intent result."""
    return {
        "intent": intent,
        "tasks": tasks or [],
        "domain": domain,
        "description": description,
        "is_correction": is_correction,
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
        "confidence": 0.95,
        "source": "llm",
    }


class TestCoreRouting:
    async def test_create_single_task(self, vault_path):
        ensure_vault_structure()
        from backend.agent.core import process_message
        with patch("backend.agent.core.classify_intent", new=AsyncMock(return_value=_clf(
            "create_task", "backend", "Auth API Refactor",
            tasks=[{"description": "Auth API Refactor", "domain": "backend"}]
        ))):
            result = await process_message("working on auth api")
        assert result["success"] is True
        assert "Auth API Refactor" in result["response"]

    async def test_create_multi_task(self, vault_path):
        ensure_vault_structure()
        from backend.agent.core import process_message
        with patch("backend.agent.core.classify_intent", new=AsyncMock(return_value=_clf(
            "create_task", "backend", "Upgrade NuGet Packages",
            tasks=[
                {"description": "Upgrade NuGet Packages", "domain": "backend"},
                {"description": "Update Drivers Lat-Long Action Name", "domain": "backend"},
            ]
        ))):
            result = await process_message("1. upgrade nuget packages 2. update drivers lat-long")
        assert result["success"] is True
        assert "2 tasks" in result["response"]
        assert "Upgrade NuGet Packages" in result["response"]
        assert "Update Drivers Lat-Long Action Name" in result["response"]

    async def test_correction_returns_restate_prompt(self, vault_path):
        ensure_vault_structure()
        from backend.agent.core import process_message
        with patch("backend.agent.core.classify_intent", new=AsyncMock(return_value=_clf(
            "chitchat", "unknown", "", is_correction=True
        ))):
            result = await process_message("those were two separate tasks")
        assert result["needs_clarification"] is True
        assert "sorry" in result["response"].lower() or "right" in result["response"].lower()

    async def test_clarification_uses_llm_question(self, vault_path):
        ensure_vault_structure()
        from backend.agent.core import process_message
        with patch("backend.agent.core.classify_intent", new=AsyncMock(return_value=_clf(
            "create_task", "unknown", "Build something",
            needs_clarification=True,
            clarification_question="Is this for Backend or Frontend?"
        ))):
            result = await process_message("build something")
        assert result["needs_clarification"] is True
        assert "Backend or Frontend" in result["response"]

    async def test_create_blocker(self, vault_path):
        ensure_vault_structure()
        from backend.agent.core import process_message
        with patch("backend.agent.core.classify_intent", new=AsyncMock(return_value=_clf(
            "create_blocker", "backend", "CORS Issue"
        ))):
            result = await process_message("stuck on CORS")
        assert result["success"] is True
        assert "CORS Issue" in result["response"]

    async def test_complete_task(self, vault_path):
        ensure_vault_structure()
        from backend.agent.core import process_message
        # First add the task
        from backend.agent.tools.task_tools import add_task
        add_task("NuGet Package Upgrade", "backend")

        with patch("backend.agent.core.classify_intent", new=AsyncMock(return_value=_clf(
            "complete_task", "backend", "NuGet Package Upgrade"
        ))):
            result = await process_message("completed nuget package upgradation")
        assert result["success"] is True

    async def test_get_status(self, vault_path):
        ensure_vault_structure()
        from backend.agent.core import process_message
        with patch("backend.agent.core.classify_intent", new=AsyncMock(return_value=_clf(
            "get_status", "unknown", ""
        ))):
            result = await process_message("/status")
        assert result["success"] is True

    async def test_resolve_blocker(self, vault_path):
        ensure_vault_structure()
        from backend.agent.core import process_message
        from backend.agent.tools.blocker_tools import create_blocker
        create_blocker("CORS Issue", "backend")

        with patch("backend.agent.core.classify_intent", new=AsyncMock(return_value=_clf(
            "resolve_blocker", "backend", "CORS Issue"
        ))):
            result = await process_message("fixed the CORS thing")
        assert result["success"] is True

    async def test_response_has_personality(self, vault_path):
        ensure_vault_structure()
        from backend.agent.core import process_message
        with patch("backend.agent.core.classify_intent", new=AsyncMock(return_value=_clf(
            "create_task", "backend", "Auth Refactor",
            tasks=[{"description": "Auth Refactor", "domain": "backend"}]
        ))):
            result = await process_message("working on auth")
        ack_words = ["Got it", "Added", "On it", "Noted", "Sure thing"]
        assert any(w in result["response"] for w in ack_words)

