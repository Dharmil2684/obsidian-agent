from backend.vault.writer import add_blocker_to_active, resolve_blocker_in_active


def create_blocker(description: str, domain: str) -> dict:
    if not description:
        return {"success": False, "message": "No blocker description provided."}

    domain = domain.lower().replace(" ", "_")
    if domain not in ("backend", "frontend", "data_science"):
        domain = "backend"

    prefix = {"backend": "BE", "frontend": "FE", "data_science": "DS"}.get(domain, "GEN")
    add_blocker_to_active(description, domain)

    return {
        "success": True,
        "message": f"🚧 Logged blocker [{prefix}]: **{description}**",
        "action": "✓ Written to Blockers/active.md + today's note",
    }


def resolve_blocker(description: str) -> dict:
    found = resolve_blocker_in_active(description)
    if found:
        return {
            "success": True,
            "message": f"✅ Resolved blocker: **{description}**",
            "action": "Moved to Blockers/resolved/ · marked in today's note",
        }
    return {
        "success": False,
        "message": (
            f"Could not find an active blocker matching *{description}*. "
            "Use `/status` to see active blockers."
        ),
    }
