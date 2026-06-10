from datetime import date

from backend.vault.reader import get_today_stats, read_active_blockers


def get_today_status() -> dict:
    today = date.today()
    stats = get_today_stats()
    blockers = read_active_blockers()

    if stats["tasks"] == 0 and stats["completed"] == 0:
        return {
            "success": True,
            "message": (
                f"📋 No tasks yet for **{today.strftime('%A, %b %d')}**.\n\n"
                "Start by saying *\"I'm working on X\"* or use `/task`."
            ),
            "stats": stats,
        }

    bd = stats["by_domain"]
    domain_parts = []
    if bd.get("backend"):
        domain_parts.append(f"🖥️ BE: {bd['backend']}")
    if bd.get("frontend"):
        domain_parts.append(f"🌐 FE: {bd['frontend']}")
    if bd.get("data_science"):
        domain_parts.append(f"📊 DS: {bd['data_science']}")

    domain_str = " · ".join(domain_parts) if domain_parts else "no pending tasks"

    blocker_list = ""
    if blockers:
        blocker_list = "\n**Active blockers:**\n" + "\n".join(
            f"- 🔴 {b['description']}" for b in blockers
        )

    message = (
        f"**Today — {today.strftime('%A, %b %d')}**\n\n"
        f"📋 Pending: **{stats['tasks']}** ({domain_str})\n"
        f"✅ Completed: **{stats['completed']}**\n"
        f"🚧 Blockers: **{stats['blockers']}**"
        + blocker_list
    )

    return {"success": True, "message": message, "stats": stats}
