"""
Phase 3 — summary tools

generate_daily_summary  → Hermes-3 (local Ollama)  — EOD reflection
generate_weekly_summary → Groq API (free tier)      — weekly digest
"""
import json
from datetime import date, timedelta

import httpx

from backend import config
from backend.vault.reader import (
    read_daily_note,
    get_week_dates,
    _parse_tasks_from_note,
    read_active_blockers,
)
from backend.vault.writer import write_eod_summary, write_weekly_summary

# ---------------------------------------------------------------------------
# Helpers — build context strings for each LLM
# ---------------------------------------------------------------------------

def _build_daily_context(for_date: date) -> str:
    """Summarise today's note into a compact string for the EOD prompt."""
    note = read_daily_note(for_date)
    if not note:
        return "No daily note available."

    pending, completed = _parse_tasks_from_note(note["content"])
    blockers           = read_active_blockers()
    domain_icon        = {"backend": "🖥️", "frontend": "🌐", "data_science": "📊"}

    lines = [f"Date: {for_date.strftime('%A %B %d, %Y')}"]
    lines.append(f"\nCompleted today ({len(completed)}):")
    for c in completed:
        lines.append(f"  ✓ {c}")

    lines.append(f"\nStill pending ({len(pending)}):")
    for t in pending:
        lines.append(f"  • {domain_icon.get(t['domain'], '?')} {t['description']}")

    if blockers:
        lines.append(f"\nActive blockers ({len(blockers)}):")
        for b in blockers:
            lines.append(f"  🔴 {b['description']}")

    return "\n".join(lines)


def _build_weekly_context() -> str:
    """Summarise Mon→today for the Groq weekly prompt."""
    domain_icon = {"backend": "🖥️", "frontend": "🌐", "data_science": "📊"}
    week_dates  = get_week_dates()
    blockers    = read_active_blockers()
    lines       = []

    total_done    = 0
    total_pending = 0

    for d in week_dates:
        note = read_daily_note(d)
        if not note:
            continue
        pending, completed = _parse_tasks_from_note(note["content"])
        total_done    += len(completed)
        total_pending += len(pending)
        day_label      = d.strftime("%A %b %d")

        lines.append(f"\n{day_label}:")
        for c in completed:
            lines.append(f"  ✓ {c}")
        for t in pending:
            lines.append(f"  ⬜ {domain_icon.get(t['domain'], '?')} {t['description']}")

    summary_header = (
        f"Week of {week_dates[0].strftime('%b %d')} — {week_dates[-1].strftime('%b %d, %Y')}\n"
        f"Total completed: {total_done}  |  Still pending: {total_pending}"
    )
    if blockers:
        summary_header += f"\nOpen blockers: {len(blockers)}"
        for b in blockers:
            summary_header += f"\n  🔴 {b['description']}"

    return summary_header + "\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Daily EOD summary — Hermes-3 via Ollama
# ---------------------------------------------------------------------------

_DAILY_SYSTEM = (
    "You are a thoughtful personal productivity assistant. "
    "Given a developer's daily activity log, write a concise but warm EOD (end-of-day) summary. "
    "Structure it as:\n"
    "1. **What got done** — highlight wins, even small ones\n"
    "2. **What's still open** — brief, no judgment\n"
    "3. **Blockers** — acknowledge and suggest a next action if obvious\n"
    "4. **One sentence encouragement** to end\n\n"
    "Keep it under 200 words. Use markdown. Be honest but positive."
)


async def generate_daily_summary(for_date: date = None) -> dict:
    for_date = for_date or date.today()
    ctx      = _build_daily_context(for_date)

    payload = {
        "model":  config.LOCAL_MODEL,
        "stream": False,
        "messages": [
            {"role": "system",  "content": _DAILY_SYSTEM},
            {"role": "user",    "content": f"Here is my day:\n\n{ctx}\n\nPlease write my EOD summary."},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{config.OLLAMA_BASE_URL}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data    = resp.json()
            summary = data["message"]["content"].strip()
    except Exception as exc:
        return {
            "success": False,
            "message": f"Couldn't generate summary — Ollama unavailable: {exc}",
        }

    # Write into the daily note's EOD section
    write_eod_summary(summary, for_date)

    return {
        "success": True,
        "message": summary,
        "action":  "generate_summary",
    }


# ---------------------------------------------------------------------------
# Weekly summary — Groq API (llama-3.3-70b-versatile)
# ---------------------------------------------------------------------------

_WEEKLY_SYSTEM = (
    "You are a senior engineering manager helping a developer reflect on their week. "
    "Given a log of tasks and blockers across domains (Backend, Frontend, Data Science), "
    "write a structured weekly summary:\n\n"
    "1. **Weekly Wins** — 3-5 bullet points of actual accomplishments\n"
    "2. **Carried Forward** — tasks not yet done (be neutral, not critical)\n"
    "3. **Blockers** — status and suggested next steps\n"
    "4. **Focus Recommendation for Next Week** — top 2-3 priorities with reasoning\n"
    "5. **One Sentence** — motivational closer\n\n"
    "Use markdown. Be concise (under 300 words). Be honest."
)


async def generate_weekly_summary(for_date: date = None) -> dict:
    if not config.GROQ_API_KEY:
        return {
            "success": False,
            "message": (
                "Groq API key not set.\n\n"
                "Add `GROQ_API_KEY=your_key` to your `.env` file.\n"
                "Get a free key at https://console.groq.com/keys"
            ),
        }

    for_date = for_date or date.today()
    ctx      = _build_weekly_context()

    payload = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _WEEKLY_SYSTEM},
            {"role": "user",   "content": f"Here is my week:\n\n{ctx}\n\nPlease write my weekly summary."},
        ],
        "max_tokens": 600,
        "temperature": 0.4,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.GROQ_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data    = resp.json()
            summary = data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as exc:
        return {
            "success": False,
            "message": f"Groq API error ({exc.response.status_code}): {exc.response.text[:200]}",
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"Weekly summary failed: {exc}",
        }

    # Write into weekly note
    write_weekly_summary(summary, for_date)

    return {
        "success": True,
        "message": summary,
        "action":  "generate_weekly",
    }

