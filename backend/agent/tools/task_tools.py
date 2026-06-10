from datetime import date

from backend.vault.writer import append_task_to_daily_note, complete_task_in_daily_note, clear_tasks_today


def add_task(description: str, domain: str, for_date: date = None) -> dict:
    if not description:
        return {"success": False, "message": "No task description provided."}

    domain = domain.lower().replace(" ", "_")
    if domain not in ("backend", "frontend", "data_science"):
        domain = "backend"

    path = append_task_to_daily_note(description, domain, for_date)
    label = {"backend": "🖥️ BE", "frontend": "🌐 FE", "data_science": "📊 DS"}.get(domain, domain)

    return {
        "success": True,
        "message": f"Added [{label}] task: **{description}**",
        "action": f"✓ Written to Daily/{path.name}",
    }


def clear_tasks(domain: str = "all") -> dict:
    domain = domain.lower().replace(" ", "_")
    if domain not in ("all", "backend", "frontend", "data_science"):
        domain = "all"

    count = clear_tasks_today(domain)

    if count == 0:
        scope = f"[{domain}]" if domain != "all" else "today"
        return {
            "success": True,
            "message": f"No pending tasks to remove for {scope}.",
            "action": None,
        }

    scope  = f"[{domain}]" if domain != "all" else "today"
    plural = "task" if count == 1 else "tasks"
    return {
        "success": True,
        "message": f"Removed **{count}** pending {plural} from {scope}.",
        "action":  f"✓ Cleared {count} {plural} from today's daily note",
    }


def complete_task(description: str, for_date: date = None) -> dict:
    found = complete_task_in_daily_note(description, for_date)
    if found:
        return {
            "success": True,
            "message": f"✅ Marked complete: **{description}**",
            "action": "Task checked off · moved to Completed section",
        }
    return {
        "success": False,
        "message": (
            f"Could not find a pending task matching *{description}*. "
            "Use `/status` to see current tasks."
        ),
    }
