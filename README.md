# Obsidian Agent

A local-first AI desktop assistant that lives in your **Windows system tray** and manages your [Obsidian](https://obsidian.md) vault through natural conversation.

Built for software developers who want a fast, private workflow manager — no cloud required.

---

## What it does

You type naturally in a floating chat window. The agent understands your intent, writes to your vault, and responds conversationally:

> "Add a backend task to fix the auth middleware bug"  
> "I finished the database migration"  
> "What's blocking me right now?"  
> "Add three tasks: write unit tests, update the docs, review PR #42"

Everything lands in structured Obsidian markdown — daily notes, blocker tracker, weekly summaries — ready to open in Obsidian anytime.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Electron (system tray)              │
│  ┌─────────────────────────────────────────┐    │
│  │   React + Vite  (floating chat window)  │    │
│  └────────────────┬────────────────────────┘    │
│                   │ HTTP (localhost:8000)        │
│  ┌────────────────▼────────────────────────┐    │
│  │   FastAPI + Uvicorn  (Python backend)   │    │
│  │   ┌─────────────┐   ┌───────────────┐  │    │
│  │   │  Hermes-3   │   │  Groq API     │  │    │
│  │   │  (local LLM)│   │  (summaries)  │  │    │
│  │   └──────┬──────┘   └───────────────┘  │    │
│  │          │  vault I/O                  │    │
│  └──────────▼──────────────────────────────┘    │
│             Obsidian Vault (markdown files)      │
└─────────────────────────────────────────────────┘
```

| Layer | Technology |
|---|---|
| Desktop shell | Electron 28 |
| UI | React 18 + Vite 5 |
| Agent server | FastAPI + Uvicorn |
| Local LLM | [Hermes-3](https://ollama.com/library/hermes3) via Ollama |
| Cloud LLM (summaries) | Groq API — `llama-3.3-70b-versatile` (free tier) |
| Vault I/O | `python-frontmatter` + `watchdog` |
| Tests | pytest + pytest-asyncio |

---

## Features

- **System tray app** — lives in your tray, never clutters your taskbar
- **Global hotkey** — `Ctrl+Shift+Space` opens/hides the window from anywhere
- **LLM-first intelligence** — Hermes-3 handles intent classification, multi-task splitting, domain inference, description cleaning, correction detection
- **Full week context** — agent reads Mon→today before every reply; no blind answers
- **Domain tabs** — filter tasks by Backend / Frontend / Data Science / All
- **Slash commands** — `/task`, `/done`, `/blocker`, `/status`, `/clear`, `/carry`, `/summary`, `/week`
- **Fuzzy task completion** — "finished upgradation" matches "upgrade the API" correctly
- **Vault structure** — daily notes, active blockers, resolved blockers, weekly notes, changelog, context file

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Windows 10/11 | — | Primary target |
| Node.js | 18 + | [nodejs.org](https://nodejs.org) |
| Python | 3.10 + | [python.org](https://python.org) |
| Ollama | latest | [ollama.com](https://ollama.com) — must be running |
| Hermes-3 model | — | `ollama pull hermes3` |
| Groq API key | free | [console.groq.com/keys](https://console.groq.com/keys) |

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/Dharmil2684/obsidian-agent.git
cd obsidian-agent
```

Copy `.env.example` to `.env` and fill in your values:

```bash
copy .env.example .env
# Edit .env:
#   VAULT_PATH=C:\Path\To\Your\ObsidianVault
#   GROQ_API_KEY=your_key_here
```

### 2. Install dependencies

```bash
# Node (Electron + Vite)
npm run install:all

# Python (FastAPI backend)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Pull the local model

```bash
ollama pull hermes3
```

> Requires ~4.5 GB VRAM (Q4_K_M quantisation). Works on RTX 3050 4 GB+.

### 4. Run in dev mode

```bash
scripts\dev.bat
```

This opens three windows:
- FastAPI backend → `http://localhost:8000`
- Vite dev server → `http://localhost:5173`
- Electron app → system tray icon appears

**Left-click** the tray icon or press **`Ctrl+Shift+Space`** to open the chat window.

---

## Vault structure

```
YourVault/
├── Daily/
│   └── YYYY-MM-DD.md        ← daily notes with tasks by domain
├── Weekly/
│   └── YYYY-WNN.md          ← weekly summaries
├── Blockers/
│   ├── active.md            ← current blockers (🔴 lines)
│   └── resolved/            ← archived resolved blockers
└── Agent/
    ├── context.md           ← project context fed to the LLM
    └── changelog.md         ← every action the agent takes
```

---

## Chat commands

| Command | What it does |
|---|---|
| `/task` | Add a task (or just type naturally) |
| `/done` | Mark a task complete |
| `/blocker` | Log a blocker |
| `/status` | Today's task + blocker counts |
| `/clear` | Remove all unchecked tasks for today |
| `/carry` | Carry yesterday's unfinished tasks forward *(Phase 3)* |
| `/summary` | Generate end-of-day summary *(Phase 3)* |
| `/week` | Generate weekly summary via Groq *(Phase 3)* |

---

## Running tests

```bash
# Activate venv first
.venv\Scripts\activate

pytest
# 80 tests, all passing
```

---

## Roadmap

- [x] **Phase 1** — FastAPI backend, vault I/O, LLM-first agent, React UI, Electron window, 80 tests
- [x] **Phase 2** — System tray, floating window, auto-hide, global hotkey, single-instance lock, Windows startup option
- [x] **Phase 3** — `carry_tasks_forward`, EOD summary (Hermes-3), weekly summary (Groq), weekly note writer, 97 tests total
- [ ] **Phase 4** — First-run setup wizard, settings panel, vault scanner (`generate_context.py`)
- [ ] **Phase 5** — ChromaDB semantic search, project context linking, blocker age tracking
- [ ] **Phase 6** — Auto-updater, Windows toast notifications, dark/light theme toggle, `.exe` packaging

---

## Hardware tested on

- Ryzen 7 5800H · 16 GB RAM · RTX 3050 4 GB (Hermes-3 Q4_K_M fits in VRAM)

---

## License

MIT
