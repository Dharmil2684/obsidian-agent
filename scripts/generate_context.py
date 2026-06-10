"""
One-time script: scan an existing Obsidian vault and generate Agent/context.md
Usage: python scripts/generate_context.py [vault_path]
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend import config
from backend.vault.writer import ensure_vault_structure


def scan_vault(vault_path: Path) -> dict:
    projects = {"backend": [], "frontend": [], "data_science": []}
    technologies = set()
    total_notes = 0

    # Scan Projects folder
    for domain_dir in (vault_path / "Projects").iterdir() if (vault_path / "Projects").exists() else []:
        if domain_dir.is_dir():
            domain_key = domain_dir.name.lower().replace(" ", "_")
            for md_file in domain_dir.glob("*.md"):
                if md_file.stem != "_index":
                    for k in projects:
                        if k in domain_key or domain_key in k:
                            projects[k].append(md_file.stem)

    # Scan Daily notes for tech keywords
    _TECH_KW = {
        "fastapi", "django", "redis", "kafka", "docker", "postgres", "mysql",
        "react", "vue", "typescript", "tailwind", "vite",
        "pandas", "pytorch", "tensorflow", "sklearn", "jupyter",
    }
    daily_dir = vault_path / "Daily"
    if daily_dir.exists():
        for md_file in sorted(daily_dir.glob("*.md"))[-30:]:  # last 30 days
            total_notes += 1
            text = md_file.read_text(encoding="utf-8", errors="ignore").lower()
            for kw in _TECH_KW:
                if kw in text:
                    technologies.add(kw)

    return {
        "projects": projects,
        "technologies": sorted(technologies),
        "total_notes": total_notes,
    }


def generate_context(vault_path: Path):
    ensure_vault_structure()
    info = scan_vault(vault_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "---",
        "tags: [agent-context]",
        f"generated: {now}",
        "---",
        "",
        "# Agent Context",
        "",
        "## Developer Profile",
        "- **Focus Areas:** Backend, Frontend, Data Science",
        f"- **Context generated:** {now}",
        f"- **Daily notes scanned:** {info['total_notes']}",
        "",
    ]

    for domain, project_list in info["projects"].items():
        if project_list:
            lines.append(f"## Active {domain.title()} Projects")
            for p in project_list:
                lines.append(f"- {p}")
            lines.append("")

    if info["technologies"]:
        lines.append("## Detected Technology Stack")
        lines.append(", ".join(t.title() for t in info["technologies"]))
        lines.append("")

    lines += [
        "## Vault Structure",
        "- `Daily/` — One note per day",
        "- `Projects/` — Backend / Frontend / DataScience sub-folders",
        "- `Weekly/` — Weekly summaries (generated on demand)",
        "- `Blockers/` — active.md + resolved/",
        "- `Templates/` — Note templates",
        "- `Agent/` — This context file + changelog",
        "",
    ]

    context_path = vault_path / "Agent" / "context.md"
    context_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[ok] Context written to {context_path}")


if __name__ == "__main__":
    vault = Path(sys.argv[1]) if len(sys.argv) > 1 else config.VAULT_PATH
    if not vault.exists():
        print(f"[ERROR] Vault path does not exist: {vault}")
        sys.exit(1)
    generate_context(vault)
