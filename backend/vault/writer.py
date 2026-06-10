import re
import shutil
from datetime import datetime, date
from pathlib import Path

from backend import config
from backend.vault.templates import (
    get_daily_template,
    get_active_blockers_template,
    get_context_template,
    get_changelog_template,
)


# ---------------------------------------------------------------------------
# Vault bootstrap
# ---------------------------------------------------------------------------

def ensure_vault_structure():
    """Create all required folders and seed files if they don't exist."""
    dirs = [
        config.VAULT_PATH / "Daily",
        config.VAULT_PATH / "Projects" / "Backend",
        config.VAULT_PATH / "Projects" / "Frontend",
        config.VAULT_PATH / "Projects" / "DataScience",
        config.VAULT_PATH / "Weekly",
        config.VAULT_PATH / "Blockers" / "resolved",
        config.VAULT_PATH / "Templates",
        config.VAULT_PATH / "Agent",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    _seed_file(
        config.VAULT_PATH / "Blockers" / "active.md",
        get_active_blockers_template(),
    )
    _seed_file(
        config.VAULT_PATH / "Agent" / "context.md",
        get_context_template(),
    )
    _seed_file(
        config.VAULT_PATH / "Agent" / "changelog.md",
        get_changelog_template(),
    )


def _seed_file(path: Path, content: str):
    if not path.exists():
        path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def _backup_file(path: Path):
    if not path.exists():
        return
    backup_dir = path.parent / ".agent_backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{path.stem}_{timestamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    # Prune old backups — keep only MAX_BACKUPS
    all_backups = sorted(backup_dir.glob(f"{path.stem}_*{path.suffix}"))
    while len(all_backups) > config.MAX_BACKUPS:
        all_backups.pop(0).unlink()


# ---------------------------------------------------------------------------
# Daily note helpers
# ---------------------------------------------------------------------------

def get_or_create_daily_note(for_date: date = None) -> Path:
    if for_date is None:
        for_date = date.today()
    path = config.VAULT_PATH / "Daily" / f"{for_date.strftime('%Y-%m-%d')}.md"
    if not path.exists():
        dt = datetime.combine(for_date, datetime.min.time())
        path.write_text(get_daily_template(dt), encoding="utf-8")
    return path


def clear_tasks_today(domain: str = "all") -> int:
    """
    Remove all pending (unchecked) tasks from today's note.
    domain: 'all' | 'backend' | 'frontend' | 'data_science'
    Returns count of tasks removed.
    """
    path = get_or_create_daily_note()
    _backup_file(path)
    content = path.read_text(encoding="utf-8")

    domain_headers = {
        "backend":      "### 🖥️ Backend",
        "frontend":     "### 🌐 Frontend",
        "data_science": "### 📊 Data Science",
    }

    lines          = content.split("\n")
    current_domain = None
    removed        = 0
    new_lines      = []

    for line in lines:
        # Track which domain section we're in
        for dom, header in domain_headers.items():
            if header in line:
                current_domain = dom
                break

        # Remove line if it's an unchecked task in the target domain
        if line.strip().startswith("- [ ]") and line.strip()[5:].strip():
            if domain == "all" or current_domain == domain:
                removed += 1
                continue  # skip — don't append

        new_lines.append(line)

    path.write_text("\n".join(new_lines), encoding="utf-8")
    scope = domain if domain != "all" else "all domains"
    _log_changelog(f"Cleared {removed} pending tasks ({scope})")
    return removed


def append_task_to_daily_note(description: str, domain: str, for_date: date = None) -> Path:
    path = get_or_create_daily_note(for_date)
    _backup_file(path)
    content = path.read_text(encoding="utf-8")

    domain_headers = {
        "backend": "### 🖥️ Backend",
        "frontend": "### 🌐 Frontend",
        "data_science": "### 📊 Data Science",
    }
    header = domain_headers.get(domain, "### 🖥️ Backend")

    if header in content:
        idx = content.index(header) + len(header)
        newline_idx = content.index("\n", idx)
        content = content[:newline_idx] + f"\n- [ ] {description}" + content[newline_idx:]
    else:
        content += f"\n{header}\n- [ ] {description}\n"

    path.write_text(content, encoding="utf-8")
    _log_changelog(f"Added [{domain}] task: {description}")
    return path


# ---------------------------------------------------------------------------
# Fuzzy task matching
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    'a', 'an', 'the', 'i', 'to', 'in', 'on', 'at', 'of', 'for', 'and', 'or',
    'it', 'is', 'was', 'my', 'this', 'that', 'those', 'have', 'has', 'been',
    'so', 'are', 'be', 'do', 'did', 'get', 'got', 'its', 'we', 'he', 'she',
}


def _task_matches(search: str, task_line: str) -> bool:
    """True if search term matches a stored task line.
    Uses word-level prefix matching so 'upgradation' matches 'upgrade'.
    """
    search_l = search.lower()
    line_l = task_line.lower()

    # 1. Direct substring
    if search_l in line_l:
        return True

    # 2. Word-level prefix overlap
    def _words(text: str) -> list:
        return [
            w for w in re.findall(r'[a-z]+', text.lower())
            if w not in _STOP_WORDS and len(w) > 2
        ]

    s_words = _words(search)
    l_words = _words(line_l)
    if not s_words:
        return False

    def _prefix_match(w1: str, w2: str) -> bool:
        min_len = min(len(w1), len(w2), 5)
        return min_len >= 3 and w1[:min_len] == w2[:min_len]

    matched = sum(
        1 for sw in s_words
        if any(_prefix_match(sw, lw) for lw in l_words)
    )
    # Match if at least 2 content words overlap (or all if fewer than 2)
    return matched >= min(2, len(s_words))


def complete_task_in_daily_note(description: str, for_date: date = None) -> bool:
    path = get_or_create_daily_note(for_date)
    _backup_file(path)
    content = path.read_text(encoding="utf-8")

    lines = content.split("\n")
    found_idx = None
    completed_section_idx = None

    for i, line in enumerate(lines):
        if "## ✅ Completed Today" in line:
            completed_section_idx = i
        if line.strip().startswith("- [ ]") and _task_matches(description, line) and found_idx is None:
            found_idx = i

    if found_idx is None:
        return False

    # Mark as checked
    lines[found_idx] = lines[found_idx].replace("- [ ]", "- [x]", 1)
    completed_line = lines.pop(found_idx)

    # Re-find completed section after pop (index may have shifted)
    for i, line in enumerate(lines):
        if "## ✅ Completed Today" in line:
            completed_section_idx = i
            break

    if completed_section_idx is not None:
        lines.insert(completed_section_idx + 1, completed_line)

    path.write_text("\n".join(lines), encoding="utf-8")
    _log_changelog(f"Completed task: {description}")
    return True


# ---------------------------------------------------------------------------
# Blockers
# ---------------------------------------------------------------------------

def add_blocker_to_active(description: str, domain: str) -> Path:
    path = config.VAULT_PATH / "Blockers" / "active.md"
    _backup_file(path)

    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = get_active_blockers_template()

    domain_prefix = {"backend": "BE", "frontend": "FE", "data_science": "DS"}.get(domain, "GEN")
    date_str = date.today().strftime("%Y-%m-%d")
    content += f"- 🔴 [{domain_prefix}] {description} (logged: {date_str})\n"
    path.write_text(content, encoding="utf-8")

    # Mirror in today's daily note
    daily_path = get_or_create_daily_note()
    daily_content = daily_path.read_text(encoding="utf-8")
    if "## 🚧 Active Blockers" in daily_content:
        marker = "## 🚧 Active Blockers"
        idx = daily_content.index(marker) + len(marker)
        newline_idx = daily_content.index("\n", idx)
        daily_content = (
            daily_content[:newline_idx]
            + f"\n- 🔴 [{domain_prefix}] {description}"
            + daily_content[newline_idx:]
        )
        daily_path.write_text(daily_content, encoding="utf-8")

    _log_changelog(f"Created blocker [{domain_prefix}]: {description}")
    return path


def resolve_blocker_in_active(description: str) -> bool:
    active_path = config.VAULT_PATH / "Blockers" / "active.md"
    if not active_path.exists():
        return False

    _backup_file(active_path)
    content = active_path.read_text(encoding="utf-8")
    desc_lower = description.lower()
    lines = content.split("\n")
    found_line = None

    for i, line in enumerate(lines):
        if desc_lower in line.lower() and "🔴" in line:
            found_line = lines.pop(i)
            break

    if not found_line:
        return False

    active_path.write_text("\n".join(lines), encoding="utf-8")

    # Archive to resolved/
    date_str = date.today().strftime("%Y-%m-%d")
    resolved_dir = config.VAULT_PATH / "Blockers" / "resolved"
    resolved_dir.mkdir(exist_ok=True)
    resolved_path = resolved_dir / f"{date_str}-resolved.md"

    if resolved_path.exists():
        archive = resolved_path.read_text(encoding="utf-8")
    else:
        archive = f"# Resolved Blockers — {date_str}\n\n"

    clean_desc = found_line.strip().lstrip("- 🔴").strip()
    archive += f"- ✅ {clean_desc} (resolved: {date_str})\n"
    resolved_path.write_text(archive, encoding="utf-8")

    # Update today's note — swap 🔴 → ✅ for matching line
    daily_path = get_or_create_daily_note()
    daily_content = daily_path.read_text(encoding="utf-8")
    for line in daily_content.split("\n"):
        if "🔴" in line and desc_lower[:20] in line.lower():
            daily_content = daily_content.replace(line, line.replace("🔴", "✅"), 1)
            break
    daily_path.write_text(daily_content, encoding="utf-8")

    _log_changelog(f"Resolved blocker: {description}")
    return True


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------

def _log_changelog(message: str):
    changelog_path = config.VAULT_PATH / "Agent" / "changelog.md"
    if not changelog_path.exists():
        changelog_path.write_text(get_changelog_template(), encoding="utf-8")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"- `{timestamp}` {message}\n"
    changelog_path.write_text(
        changelog_path.read_text(encoding="utf-8") + entry, encoding="utf-8"
    )
