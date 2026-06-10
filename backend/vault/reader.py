import re
import frontmatter
from datetime import date, timedelta
from typing import Optional

from backend import config


def get_daily_note_path(for_date: date = None):
    if for_date is None:
        for_date = date.today()
    return config.VAULT_PATH / "Daily" / f"{for_date.strftime('%Y-%m-%d')}.md"


def read_daily_note(for_date: date = None) -> Optional[dict]:
    path = get_daily_note_path(for_date)
    if not path.exists():
        return None
    post = frontmatter.load(str(path))
    return {"metadata": post.metadata, "content": post.content, "path": path}


def get_section_content(content: str, section_title: str) -> str:
    """Extract content between two ## headings."""
    pattern = rf"## {re.escape(section_title)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""


def get_unchecked_tasks(for_date: date = None) -> list:
    note = read_daily_note(for_date)
    if not note:
        return []

    tasks = []
    current_domain = None
    domain_map = {
        "🖥️ Backend": "backend",
        "🌐 Frontend": "frontend",
        "📊 Data Science": "data_science",
    }

    for line in note["content"].split("\n"):
        if line.startswith("### "):
            for label, domain in domain_map.items():
                if label in line:
                    current_domain = domain
                    break
        elif line.strip().startswith("- [ ]"):
            desc = line.strip()[5:].strip()
            if desc:
                tasks.append({"description": desc, "domain": current_domain})

    return tasks


def read_active_blockers() -> list:
    path = config.VAULT_PATH / "Blockers" / "active.md"
    if not path.exists():
        return []

    post = frontmatter.load(str(path))
    blockers = []
    for line in post.content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- 🔴") or (stripped.startswith("- [") and "🔴" in stripped):
            desc = re.sub(r"^-\s*(🔴)?\s*(\[.*?\])?\s*", "", stripped).strip()
            if desc:
                blockers.append({"description": desc, "raw_line": line})
    return blockers


def read_context() -> str:
    path = config.VAULT_PATH / "Agent" / "context.md"
    if not path.exists():
        return ""
    post = frontmatter.load(str(path))
    return post.content


def get_week_dates() -> list[date]:
    """Return Mon→today for the current week (no future days)."""
    today    = date.today()
    monday   = today - timedelta(days=today.weekday())
    return [monday + timedelta(days=i) for i in range((today - monday).days + 1)]


def _parse_tasks_from_note(content: str) -> tuple[list, list]:
    """Return (pending_tasks, completed_tasks) from a daily note's content."""
    domain_map = {
        "🖥️ Backend":     "backend",
        "🌐 Frontend":    "frontend",
        "📊 Data Science": "data_science",
    }
    current_domain = None
    pending, completed = [], []

    for line in content.split("\n"):
        if line.startswith("### "):
            for label, dom in domain_map.items():
                if label in line:
                    current_domain = dom
                    break
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            desc = stripped[5:].strip()
            if desc:
                pending.append({"description": desc, "domain": current_domain})
        elif stripped.startswith("- [x]"):
            desc = stripped[5:].strip()
            if desc:
                completed.append(desc)

    return pending, completed


def get_vault_snapshot() -> str:
    """
    Returns a concise plain-text snapshot of the current week's vault state.
    Injected into every LLM call so the agent knows what it's working with —
    past days show completed/pending history, today shows live state.
    Active blockers are always shown regardless of day.
    """
    domain_label = {"backend": "[BE]", "frontend": "[FE]", "data_science": "[DS]"}
    today        = date.today()
    week_dates   = get_week_dates()
    lines        = [f"=== VAULT STATE — Week of {week_dates[0].strftime('%b %d')} "
                    f"→ {today.strftime('%A, %b %d, %Y')} ==="]

    for d in week_dates:
        day_label = "TODAY" if d == today else d.strftime("%A %b %d")
        note      = read_daily_note(d)

        if note is None:
            if d == today:
                lines.append(f"\n[{day_label}] No daily note yet.")
            # Skip past days with no note — no noise
            continue

        pending, completed = _parse_tasks_from_note(note["content"])

        lines.append(f"\n[{day_label}]")

        if pending:
            lines.append(f"  Pending ({len(pending)}):")
            for t in pending:
                lbl = domain_label.get(t["domain"], "[?]")
                lines.append(f"    • {lbl} {t['description']}")
        else:
            lines.append("  Pending: none")

        if completed:
            lines.append(f"  Completed ({len(completed)}):")
            for c in completed:
                lines.append(f"    ✓ {c}")

    # Active blockers — always show, they span multiple days
    blockers = read_active_blockers()
    lines.append("\n[ACTIVE BLOCKERS]")
    if blockers:
        for b in blockers:
            lines.append(f"  🔴 {b['description']}")
    else:
        lines.append("  none")

    lines.append("\n=== END VAULT STATE ===")
    return "\n".join(lines)


def get_today_stats() -> dict:
    note = read_daily_note()
    if not note:
        return {"tasks": 0, "completed": 0, "blockers": 0, "by_domain": {}}

    lines = note["content"].split("\n")
    pending = [l for l in lines if l.strip().startswith("- [ ]") and l.strip()[5:].strip()]
    completed = [l for l in lines if l.strip().startswith("- [x]")]
    blockers = read_active_blockers()

    by_domain = {"backend": 0, "frontend": 0, "data_science": 0}
    domain_map = {
        "🖥️ Backend": "backend",
        "🌐 Frontend": "frontend",
        "📊 Data Science": "data_science",
    }
    current_domain = None
    for line in lines:
        if line.startswith("### "):
            for label, domain in domain_map.items():
                if label in line:
                    current_domain = domain
                    break
        elif line.strip().startswith("- [ ]") and line.strip()[5:].strip():
            if current_domain in by_domain:
                by_domain[current_domain] += 1

    return {
        "tasks": len(pending),
        "completed": len(completed),
        "blockers": len(blockers),
        "by_domain": by_domain,
    }
