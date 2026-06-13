from datetime import date, timedelta

from backend.vault.reader import get_unchecked_tasks, read_daily_note
from backend.vault.writer import append_task_to_daily_note, get_or_create_daily_note


def carry_tasks_forward(from_date: date = None, to_date: date = None) -> dict:
    """
    Copy all unchecked tasks from `from_date` (default: yesterday) into `to_date`
    (default: today).  Skips tasks already present in the target note to avoid
    duplicates.  Returns a summary message.
    """
    today     = date.today()
    from_date = from_date or (today - timedelta(days=1))
    to_date   = to_date   or today

    if from_date == to_date:
        return {"success": False, "message": "Source and target date are the same — nothing to carry."}

    # Check source exists
    source_note = read_daily_note(from_date)
    if not source_note:
        return {
            "success": False,
            "message": f"No daily note found for {from_date.strftime('%A %b %d')} — nothing to carry.",
        }

    pending = get_unchecked_tasks(from_date)
    if not pending:
        return {
            "success": True,
            "message": f"No pending tasks on {from_date.strftime('%A %b %d')} — you were all caught up! 🎉",
        }

    # Build set of task descriptions already in target note to avoid duplicates
    target_note = read_daily_note(to_date)
    existing: set[str] = set()
    if target_note:
        for line in target_note["content"].split("\n"):
            stripped = line.strip()
            if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
                existing.add(stripped[5:].strip().lower())

    carried, skipped = [], []
    for task in pending:
        desc   = task["description"]
        domain = task["domain"] or "backend"
        if desc.lower() in existing:
            skipped.append(desc)
            continue
        append_task_to_daily_note(desc, domain, to_date)
        carried.append((desc, domain))

    if not carried and skipped:
        return {
            "success": True,
            "message": (
                f"All {len(skipped)} task(s) from {from_date.strftime('%A')} are already in today's note."
            ),
            "action":  "carry_forward",
            "carried": 0,
            "skipped": len(skipped),
        }

    domain_icon = {"backend": "🖥️", "frontend": "🌐", "data_science": "📊"}
    lines = [f"Carried **{len(carried)}** task(s) from {from_date.strftime('%A %b %d')}:\n"]
    for desc, dom in carried:
        lines.append(f"- {domain_icon.get(dom, '•')} {desc}")
    if skipped:
        lines.append(f"\n_{len(skipped)} already present — skipped._")

    return {
        "success": True,
        "message": "\n".join(lines),
        "action":  "carry_forward",
        "carried": len(carried),
        "skipped": len(skipped),
    }
