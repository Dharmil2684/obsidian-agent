"""Tests for intent classification — slash rules, offline fallback, and async classify."""
import pytest

from backend.agent.intent import (
    _try_slash,
    _offline_fallback,
    _detect_domain_suffix,
    classify_intent,
)

# ---------------------------------------------------------------------------
# Slash command rules (deterministic — no LLM)
# ---------------------------------------------------------------------------

class TestSlashRules:
    def test_slash_status(self):
        r = _try_slash("/status")
        assert r["intent"] == "get_status"
        assert r["source"] == "slash-rule"
        assert r["confidence"] == 1.0

    def test_slash_s_shorthand(self):
        r = _try_slash("/s")
        assert r["intent"] == "get_status"

    def test_slash_carry(self):
        r = _try_slash("/carry")
        assert r["intent"] == "carry_forward"

    def test_slash_summary(self):
        r = _try_slash("/summary")
        assert r["intent"] == "generate_summary"

    def test_slash_week(self):
        r = _try_slash("/week")
        assert r["intent"] == "generate_weekly"

    def test_slash_w_shorthand(self):
        r = _try_slash("/w")
        assert r["intent"] == "generate_weekly"

    def test_slash_task_plain(self):
        r = _try_slash("/task Auth API refactor")
        assert r["intent"] == "create_task"
        assert r["confidence"] == 1.0
        assert len(r["tasks"]) == 1
        assert "Auth API refactor" in r["tasks"][0]["description"]

    def test_slash_task_be_suffix(self):
        r = _try_slash("/task:be Auth API refactor")
        assert r["tasks"][0]["domain"] == "backend"

    def test_slash_task_fe_suffix(self):
        r = _try_slash("/task:fe Dashboard layout")
        assert r["tasks"][0]["domain"] == "frontend"

    def test_slash_task_ds_suffix(self):
        r = _try_slash("/task:ds ML pipeline fix")
        assert r["tasks"][0]["domain"] == "data_science"

    def test_slash_blocker(self):
        r = _try_slash("/blocker CORS issue")
        assert r["intent"] == "create_blocker"

    def test_slash_b_shorthand(self):
        r = _try_slash("/b Redis timeout")
        assert r["intent"] == "create_blocker"

    def test_slash_done(self):
        r = _try_slash("/done Dashboard component")
        assert r["intent"] == "complete_task"

    def test_slash_done_with_fix(self):
        r = _try_slash("/done fixed the CORS thing")
        assert r["intent"] == "resolve_blocker"

    def test_natural_language_returns_none(self):
        assert _try_slash("I'm working on auth") is None

    def test_result_schema_complete(self):
        r = _try_slash("/task:be Auth refactor")
        for key in ("intent", "tasks", "domain", "description", "is_correction",
                    "needs_clarification", "clarification_question", "confidence", "source"):
            assert key in r


# ---------------------------------------------------------------------------
# Offline fallback (emergency — no LLM)
# ---------------------------------------------------------------------------

class TestOfflineFallback:
    def test_blocker_keywords(self):
        r = _offline_fallback("stuck on CORS, can't proceed")
        assert r["intent"] == "create_blocker"

    def test_resolve_keywords(self):
        r = _offline_fallback("fixed the redis issue")
        assert r["intent"] == "resolve_blocker"

    def test_complete_keywords(self):
        r = _offline_fallback("done with dashboard component")
        assert r["intent"] == "complete_task"

    def test_task_keywords(self):
        r = _offline_fallback("working on auth API refactor")
        assert r["intent"] == "create_task"
        assert len(r["tasks"]) == 1

    def test_status_keywords(self):
        r = _offline_fallback("how many tasks left?")
        assert r["intent"] == "get_status"

    def test_chitchat_fallback(self):
        r = _offline_fallback("what's the weather like?")
        assert r["intent"] == "chitchat"

    def test_result_schema_complete(self):
        r = _offline_fallback("working on auth")
        for key in ("intent", "tasks", "domain", "description", "is_correction",
                    "needs_clarification", "clarification_question", "confidence", "source"):
            assert key in r


# ---------------------------------------------------------------------------
# Domain suffix detection
# ---------------------------------------------------------------------------

class TestDomainSuffix:
    def test_be_suffix(self):
        assert _detect_domain_suffix("/task:be something") == "backend"

    def test_fe_suffix(self):
        assert _detect_domain_suffix("task:fe something") == "frontend"

    def test_ds_suffix(self):
        assert _detect_domain_suffix("task:ds something") == "data_science"

    def test_backend_keyword(self):
        assert _detect_domain_suffix("fastapi endpoint fix") == "backend"

    def test_frontend_keyword(self):
        assert _detect_domain_suffix("react component broken") == "frontend"

    def test_ds_keyword(self):
        assert _detect_domain_suffix("pandas pipeline failing") == "data_science"

    def test_no_signal_returns_unknown(self):
        assert _detect_domain_suffix("hello there") == "unknown"


# ---------------------------------------------------------------------------
# classify_intent async — falls back gracefully when model unavailable
# ---------------------------------------------------------------------------

class TestClassifyIntentAsync:
    """When Ollama is offline or model not found, should fall back to rules."""

    async def test_slash_bypasses_llm(self):
        r = await classify_intent("/status")
        assert r["intent"] == "get_status"
        assert r["source"] == "slash-rule"

    async def test_slash_task_bypasses_llm(self):
        r = await classify_intent("/task:be Auth refactor")
        assert r["intent"] == "create_task"
        assert r["source"] == "slash-rule"

    async def test_fallback_on_natural_language(self):
        # If Ollama is offline, still returns a valid dict
        r = await classify_intent("stuck on CORS issue")
        assert r["intent"] in ("create_blocker", "chitchat")
        assert "source" in r

    async def test_schema_always_complete(self):
        r = await classify_intent("/carry")
        for key in ("intent", "tasks", "domain", "description", "is_correction",
                    "needs_clarification", "clarification_question", "confidence", "source"):
            assert key in r

