"""
Intent classification — Phase 1

Architecture:
  1. Exact slash commands → lightweight rules (deterministic, no LLM needed)
  2. All natural language → Hermes-3 (LLM decides everything: intent, domain,
     task count, cleaned descriptions, correction detection, clarification needs)
  3. Ollama offline → minimal rule-based fallback (emergency only)
"""
import json
import re

import httpx

from backend import config
from backend.vault.reader import get_vault_snapshot

# ---------------------------------------------------------------------------
# Schema helper
# ---------------------------------------------------------------------------

def _make_result(
    intent: str,
    domain: str,
    description: str,
    tasks: list,
    is_correction: bool,
    needs_clarification: bool,
    clarification_question,
    confidence: float,
    source: str = "rules",
) -> dict:
    return {
        "intent": intent,
        "tasks": tasks,
        "domain": domain,
        "description": description,
        "is_correction": is_correction,
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
        "confidence": confidence,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Slash command rules — deterministic, LLM not needed
# ---------------------------------------------------------------------------

_SLASH_EXACT = {
    "/status":  ("get_status",        "unknown", ""),
    "/s":       ("get_status",        "unknown", ""),
    "/carry":   ("carry_forward",     "unknown", ""),
    "/summary": ("generate_summary",  "unknown", ""),
    "/week":    ("generate_weekly",   "unknown", ""),
    "/w":       ("generate_weekly",   "unknown", ""),
    "/clear":   ("clear_tasks",       "all",     ""),
}

_DOMAIN_SUFFIX_MAP = {
    ":be": "backend",     "/be": "backend",
    ":fe": "frontend",    "/fe": "frontend",
    ":ds": "data_science","/ds": "data_science",
}


def _try_slash(message: str):
    """Handle exact slash commands without the LLM. Returns dict or None."""
    msg       = message.strip()
    msg_lower = msg.lower()

    if msg_lower in _SLASH_EXACT:
        intent, domain, desc = _SLASH_EXACT[msg_lower]
        return _make_result(intent, domain, desc, [], False, False, None, 1.0, "slash-rule")

    if msg_lower.startswith("/task") or msg_lower.startswith("/t "):
        domain = _detect_domain_suffix(msg_lower)
        desc   = _text_after_command(msg)
        return _make_result(
            "create_task", domain, desc,
            [{"description": desc, "domain": domain}],
            False, False, None, 1.0, "slash-rule",
        )

    if msg_lower.startswith("/blocker") or msg_lower.startswith("/b ") or msg_lower == "/b":
        domain = _detect_domain_suffix(msg_lower)
        desc   = _text_after_command(msg)
        return _make_result("create_blocker", domain, desc, [], False, False, None, 1.0, "slash-rule")

    if msg_lower.startswith("/done") or msg_lower.startswith("/d ") or msg_lower == "/d":
        desc   = _text_after_command(msg)
        fix_kw = ("fix", "fixed", "resolved", "resolve")
        intent = "resolve_blocker" if any(w in desc.lower() for w in fix_kw) else "complete_task"
        return _make_result(intent, _detect_domain_suffix(msg_lower), desc, [], False, False, None, 1.0, "slash-rule")

    return None


# ---------------------------------------------------------------------------
# LLM system prompt — Hermes-3 owns all natural-language intelligence
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are the intelligence layer for a personal developer task management system.
Analyse the user message and return ONLY a valid JSON object — no explanation, no markdown, no extra text.

JSON schema (return exactly this structure):
{
  "intent": "<string>",
  "tasks": [{"description": "<clean title>", "domain": "<string>"}],
  "domain": "<string>",
  "description": "<clean title>",
  "is_correction": <bool>,
  "needs_clarification": <bool>,
  "clarification_question": "<string or null>",
  "confidence": <float>
}

Intent values — pick exactly one:
  create_task       — user is starting or working on something new
  create_blocker    — user is stuck, blocked, has an error preventing progress
  resolve_blocker   — user fixed, unblocked, or resolved something
  complete_task     — user finished or completed something
  clear_tasks       — user wants to remove/delete/clear pending tasks from today
  carry_forward     — user wants to prep tomorrow or carry pending tasks
  get_status        — user wants to see task/blocker counts
  generate_summary  — user wants an EOD/daily summary
  generate_weekly   — user wants a weekly summary
  chitchat          — anything else

clear_tasks rules:
  domain = which domain to clear: backend | frontend | data_science | all
  "remove all tasks" / "clear today's tasks" / "delete all tasks" → domain: all
  "remove backend tasks" / "clear BE tasks" → domain: backend
  Always reference the VAULT STATE below to confirm what will be removed.

Domain values: backend | frontend | data_science | unknown

Domain signal keywords:
  backend      — api, endpoint, database, sql, server, auth, django, fastapi, redis, kafka,
                 docker, migration, schema, nuget, dotnet, csharp, drivers, lat-long, method
  frontend     — component, ui, css, react, vue, html, design, layout, button, form,
                 typescript, animation, modal, nav, dashboard, responsive
  data_science — model, training, dataset, pipeline, feature, ml, prediction, notebook,
                 pandas, tensorflow, pytorch, sklearn, etl

CRITICAL RULES — follow every one:

1. MULTI-TASK DETECTION
   "tasks" array must have one entry per distinct task the user mentions.
   If user says "1. X  2. Y" → two entries. "3 tasks: ..." → three entries.
   Never merge multiple tasks into one entry.

2. DESCRIPTION CLEANING (apply to EVERY description and every tasks[].description)
   Produce a concise, title-cased action phrase. Strip all conversational filler:
   - Strip: "i have to", "i need to", "so i", "i'm working on", "working on",
     "there are X in [domain] so", "have to", "need to", "those are", "i", "so"
   - Strip trailing domain context: "in backend", "in the frontend", "in backend"
   - Normalise to base action form: "upgradation" → "Upgrade", "fixing" → "Fix",
     "implementation" → "Implement", "updation" → "Update"
   Examples:
     "there are vulnerabilities in backend so i have to upgrade nuget packages"
       → "Upgrade NuGet Packages"
     "i have to update drivers lat-long action name instead of using method name in backend"
       → "Update Drivers Lat-Long Action Name"
     "have already completed the nuget package upgradation"
       → "NuGet Package Upgrade"
     "stuck on CORS, can't proceed"
       → "CORS Issue"
     "done with dashboard component"
       → "Dashboard Component"

3. COMPLETION NORMALISATION
   For complete_task and resolve_blocker, normalise the description to its stored base form.
   "nuget package upgradation" → "NuGet Package Upgrade"

4. IS_CORRECTION
   Set true when the user is correcting the agent's previous mistake, with no new task data.
   "those were two separate tasks, create 2 instead of 1" → is_correction: true
   If the message also has a numbered list → is_correction: false (process the new data).

5. NEEDS_CLARIFICATION
   Set true only when domain is genuinely ambiguous AND intent writes to the vault.
   If domain can be reasonably inferred from keywords → infer it, do not ask.
   If true, write a short friendly clarification_question.

6. CONFIDENCE: 0.9+ certain · 0.6–0.8 likely · below 0.5 guessing

EXAMPLES:

Input: "so i have 2 tasks today, 1. there are vulnerabilities in backend so i have to upgrade nuget packages, 2. i have to update drivers lat-long action name instead of using method name in backend"
Output: {"intent":"create_task","tasks":[{"description":"Upgrade NuGet Packages","domain":"backend"},{"description":"Update Drivers Lat-Long Action Name","domain":"backend"}],"domain":"backend","description":"Upgrade NuGet Packages","is_correction":false,"needs_clarification":false,"clarification_question":null,"confidence":0.97}

Input: "i'm working on auth API refactor"
Output: {"intent":"create_task","tasks":[{"description":"Auth API Refactor","domain":"backend"}],"domain":"backend","description":"Auth API Refactor","is_correction":false,"needs_clarification":false,"clarification_question":null,"confidence":0.95}

Input: "have already completed the nuget package upgradation"
Output: {"intent":"complete_task","tasks":[],"domain":"backend","description":"NuGet Package Upgrade","is_correction":false,"needs_clarification":false,"clarification_question":null,"confidence":0.92}

Input: "those were two separate tasks, create 2 instead of 1"
Output: {"intent":"chitchat","tasks":[],"domain":"unknown","description":"","is_correction":true,"needs_clarification":false,"clarification_question":null,"confidence":0.95}

Input: "stuck on CORS, can't proceed"
Output: {"intent":"create_blocker","tasks":[],"domain":"backend","description":"CORS Issue","is_correction":false,"needs_clarification":false,"clarification_question":null,"confidence":0.9}

Input: "fixed the CORS thing"
Output: {"intent":"resolve_blocker","tasks":[],"domain":"backend","description":"CORS Issue","is_correction":false,"needs_clarification":false,"clarification_question":null,"confidence":0.9}

Input: "done with dashboard component"
Output: {"intent":"complete_task","tasks":[],"domain":"frontend","description":"Dashboard Component","is_correction":false,"needs_clarification":false,"clarification_question":null,"confidence":0.95}
"""


# ---------------------------------------------------------------------------
# Main classify function
# ---------------------------------------------------------------------------

async def classify_intent(message: str) -> dict:
    """
    Classify user intent.
    - Slash commands → rules (instant, no LLM call)
    - Natural language → Hermes-3 (all intelligence delegated to LLM)
    - Ollama offline → minimal fallback
    """
    # Slash commands bypass the LLM — they're already deterministic
    slash_result = _try_slash(message)
    if slash_result:
        return slash_result

    # Natural language → let the LLM decide everything
    # Give the LLM a live snapshot of the vault so it can reason about real state
    vault_state = get_vault_snapshot()
    system_with_state = _SYSTEM_PROMPT + f"""

CURRENT VAULT STATE (read this before deciding what to do):
{vault_state}
"""

    payload = {
        "model": config.LOCAL_MODEL,
        "messages": [
            {"role": "system", "content": system_with_state},
            {"role": "user",   "content": message},
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 400},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            raw = resp.json()["message"]["content"].strip()

            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            parsed = json.loads(raw)
            return {
                "intent":               parsed.get("intent", "chitchat"),
                "tasks":                parsed.get("tasks", []),
                "domain":               parsed.get("domain", "unknown"),
                "description":          parsed.get("description", message),
                "is_correction":        bool(parsed.get("is_correction", False)),
                "needs_clarification":  bool(parsed.get("needs_clarification", False)),
                "clarification_question": parsed.get("clarification_question"),
                "confidence":           float(parsed.get("confidence", 0.5)),
                "source": "llm",
            }

        except (httpx.ConnectError, httpx.TimeoutException):
            r = _offline_fallback(message)
            r["source"] = "rules-ollama-offline"
            return r
        except httpx.HTTPStatusError:
            r = _offline_fallback(message)
            r["source"] = "rules-model-unavailable"
            return r
        except (json.JSONDecodeError, KeyError):
            r = _offline_fallback(message)
            r["source"] = "rules-parse-error"
            return r


# ---------------------------------------------------------------------------
# Offline fallback — emergency only, when Ollama is completely unreachable
# ---------------------------------------------------------------------------

def _offline_fallback(message: str) -> dict:
    """Minimal fallback used only when Ollama is offline."""
    msg = message.lower().strip()

    if any(w in msg for w in ("stuck on", "blocked by", "can't proceed", "cant proceed",
                               "issue with", "getting error", "problem with")):
        return _make_result("create_blocker", _detect_domain_suffix(msg),
                            message, [], False, False, None, 0.7)

    if any(w in msg for w in ("fixed", "resolved", "unblocked")):
        return _make_result("resolve_blocker", _detect_domain_suffix(msg),
                            message, [], False, False, None, 0.7)

    if any(w in msg for w in ("done with", "finished", "completed", "already complete",
                               "already completed")):
        return _make_result("complete_task", _detect_domain_suffix(msg),
                            message, [], False, False, None, 0.7)

    if any(w in msg for w in ("working on", "i'm working", "building", "implementing",
                               "have to", "need to", "setting up")):
        domain = _detect_domain_suffix(msg)
        return _make_result(
            "create_task", domain, message,
            [{"description": message, "domain": domain}],
            False, False, None, 0.6,
        )

    if any(w in msg for w in ("how many", "tasks left", "show status")):
        return _make_result("get_status", "unknown", "", [], False, False, None, 0.8)

    if "prep tomorrow" in msg or msg == "carry":
        return _make_result("carry_forward", "unknown", "", [], False, False, None, 0.8)

    return _make_result("chitchat", "unknown", message, [], False, False, None, 0.4)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BACKEND_KW = {"api", "endpoint", "database", "db", "sql", "server", "auth", "django",
               "fastapi", "redis", "kafka", "docker", "migration", "schema", "nuget",
               "dotnet", "csharp", "drivers"}
_FRONTEND_KW = {"component", "ui", "css", "react", "vue", "html", "design", "responsive",
                "layout", "button", "form", "typescript", "animation", "modal", "nav"}
_DS_KW       = {"model", "training", "dataset", "pipeline", "feature", "accuracy", "ml",
               "prediction", "notebook", "pandas", "tensorflow", "pytorch", "sklearn", "etl"}


def _detect_domain_suffix(msg: str) -> str:
    for suffix, domain in _DOMAIN_SUFFIX_MAP.items():
        if suffix in msg:
            return domain
    words = set(msg.lower().split())
    be = len(words & _BACKEND_KW)
    fe = len(words & _FRONTEND_KW)
    ds = len(words & _DS_KW)
    if max(be, fe, ds) == 0:
        return "unknown"
    if be >= fe and be >= ds:
        return "backend"
    if fe >= be and fe >= ds:
        return "frontend"
    return "data_science"


def _text_after_command(text: str) -> str:
    """Return text after the slash command token. '/task:be Auth refactor' → 'Auth refactor'."""
    parts = text.strip().split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""

