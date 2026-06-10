# Obsidian Agent — Implementation Plan
**Auto Obsidian Manager for Software Developer Workflow**
*Backend · Frontend · Data Science*

> Windows · Electron · Hermes-3 (Local) + Groq API Free Tier · Obsidian Vault

---

## 0. What We're Building

A Windows desktop app that lives in the **system tray**. Click the tray icon → a floating chat window appears. You talk to it naturally throughout the day. It reads and writes your Obsidian vault directly — creating tasks, logging blockers, resolving them, carrying forward incomplete work, and generating daily/weekly summaries — all through natural conversation or slash commands. You never open Obsidian manually to manage tasks again.

---

## 1. Core Capabilities

| Capability | How You Trigger It | What It Does to Obsidian |
|---|---|---|
| Add a task | "I'm working on the auth API today" or `/task` | Appends to today's daily note under correct domain |
| Log a blocker | "Stuck on CORS issue" or `/blocker` | Creates entry in `Blockers/active.md` + links in daily note |
| Resolve a blocker | "Fixed the CORS issue" or `/done` | Moves to `Blockers/resolved/`, marks complete in daily note |
| Complete a task | "Done with dashboard component" | Checks off task, moves to Completed section |
| Carry tasks forward | `/carry` or "prep tomorrow" | Moves all open tasks to tomorrow's Priorities section |
| Daily summary | `/summary` | Generates EOD recap in today's note (local model) |
| Weekly summary | `/week` | Aggregates 5 daily notes into `Weekly/` file (Groq cloud) |
| Tomorrow's priorities | `/priorities` | Ranks backlog by domain + age, writes to next daily note |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────┐
│           Electron App (System Tray)            │
│     Floating Window · React UI · Global Hotkey  │
└────────────────────┬────────────────────────────┘
                     │ HTTP localhost:8000
┌────────────────────▼────────────────────────────┐
│              Agent Server (FastAPI)             │
│  ┌──────────────┐   ┌──────────────────────┐   │
│  │ Chat Router  │   │  Intent Classifier   │   │
│  │  /chat       │   │  (Hermes-3 local)    │   │
│  └──────┬───────┘   └──────────┬───────────┘   │
│         └──────────────────────┘               │
│  ┌──────────────────────────────────────────┐   │
│  │         Agent Core (LangGraph)           │   │
│  │  Planner → Tool Selector → Executor      │   │
│  └──────────────────┬───────────────────────┘   │
│                     │                           │
│  ┌──────────────────▼───────────────────────┐   │
│  │              Tool Layer                  │   │
│  │  VaultReader · VaultWriter · Summarizer  │   │
│  └──────────────────┬───────────────────────┘   │
└─────────────────────│────────────────────────────┘
                      │ File I/O
┌─────────────────────▼────────────────────────────┐
│          Obsidian Vault (Local Markdown)         │
│         ~/ObsidianVault/  — your files           │
└──────────────────────────────────────────────────┘
```

### 2.1 Architecture Layers

| Layer | Technology | Responsibility |
|---|---|---|
| Desktop Shell | Electron (Node.js) | System tray icon, floating window, global hotkey, spawns Python on launch |
| UI / Chat Interface | React + Vite (inside Electron) | Chat window, domain tabs, status strip, slash command menu |
| Agent Server | FastAPI (Python) | HTTP API, chat endpoint, routes messages to agent core |
| Agent Core | LangGraph (Python) | Stateful agent: intent classify → select tool → execute → respond |
| Local LLM | Ollama + Hermes-3 8B Q4 | Intent classification, task writes, quick responses (on-device, GPU) |
| Cloud LLM | **Groq API — Free Tier** (Llama 3.3 70B) | Weekly summaries, priority analysis, complex reasoning (on demand) |
| Vault I/O | python-frontmatter + watchdog | Read/write markdown files, parse YAML frontmatter, watch for changes |
| Vector Store (Phase 3) | ChromaDB + nomic-embed-text | Semantic search across all notes, project context linking |

### 2.2 Data Flow

Every message you send follows this path:

1. Electron renderer → `POST /chat` on FastAPI (localhost:8000)
2. FastAPI hands message to LangGraph agent
3. Agent runs intent classifier (Hermes-3 local) → identifies action + domain
4. Agent selects and executes the right tool (vault read/write)
5. Tool result returned to agent → agent composes response
6. Response streams back to Electron UI in real time
7. UI shows agent message + action confirmation (e.g. *"Created blocker in Blockers/active.md"*)

### 2.3 Hybrid Model Strategy

Your RTX 3050 (4GB VRAM) runs Hermes-3 at Q4 quantization for all daily operations. Groq is only invoked for heavy analytical tasks — and it's free.

| Task Type | Model Used | Why |
|---|---|---|
| Intent classification | Hermes-3 local | Needs to be instant, runs 50+ times per day |
| Task / blocker CRUD | Hermes-3 local | Structured output, deterministic, private |
| EOD daily summary | Hermes-3 local | Summarising a single day's note, manageable context |
| Weekly summary | **Groq API — Free** | Aggregating 5 days, requires stronger reasoning |
| Priority analysis | **Groq API — Free** | Cross-domain backlog ranking needs nuanced judgment |
| Starting context gen | **Groq API — Free** | One-time deep analysis of your entire existing vault |

> **Groq Free Tier:** 14,400 requests/day · 500,000 tokens/min on Llama 3.3 70B. You'll use ~10–15 requests/week. Nowhere near the limit. Get your key at [console.groq.com](https://console.groq.com) — no credit card needed.

---

## 3. Obsidian Vault Structure

The vault is designed from scratch. Every folder has exactly one purpose. The agent treats the vault as both a database and a human-readable workspace — everything it writes is clean markdown you can edit manually at any time.

### 3.1 Folder Layout

```
ObsidianVault/
├── Daily/                      ← One note per day, auto-created by agent
│   ├── 2025-06-09.md
│   └── 2025-06-08.md
│
├── Projects/
│   ├── Backend/
│   │   ├── _index.md           ← Master project list for Backend
│   │   └── [project-name].md
│   ├── Frontend/
│   │   └── _index.md
│   └── DataScience/
│       └── _index.md
│
├── Weekly/                     ← Weekly summaries, generated on demand
│   └── 2025-W23.md
│
├── Blockers/
│   ├── active.md               ← All open blockers, single source of truth
│   └── resolved/               ← Archived by resolution date
│
├── Templates/
│   ├── daily-template.md
│   ├── weekly-template.md
│   └── project-template.md
│
└── Agent/
    ├── context.md              ← Agent's persistent memory about you
    └── changelog.md            ← Log of every write the agent makes
```

### 3.2 Daily Note Template

```markdown
---
date: 2025-06-09
day: Monday
tags: [daily]
---

# 2025-06-09 — Daily Log

## 🌅 Priorities (carried from yesterday)
<!-- agent pre-fills this from previous day's uncompleted tasks -->

## 🎯 Today's Tasks
### 🖥️ Backend
- [ ] 

### 🌐 Frontend
- [ ] 

### 📊 Data Science
- [ ] 

## 🚧 Active Blockers
<!-- agent syncs from Blockers/active.md -->

## ✅ Completed Today
<!-- agent moves tasks here when you say "done" -->

## 📝 Notes / Decisions

## 🌙 EOD Summary
<!-- filled when you ask /summary -->
```

### 3.3 Carry-Forward Logic

When you say `/carry` or "prep tomorrow":

1. Agent reads today's daily note
2. Finds all unchecked tasks: `- [ ] ...`
3. Finds all entries in `Blockers/active.md`
4. Opens or creates tomorrow's daily note
5. Writes Priorities section — **blockers first**, then pending tasks grouped by domain
6. Tags each carried item: `(→ carried from 2025-06-09)`
7. Marks originals in today's note as `[→]` so you know they moved
8. Logs the action in `Agent/changelog.md`

**Output format in tomorrow's Priorities:**
```markdown
## 🌅 Priorities (carried from 2025-06-09)
> 🚧 BLOCKERS FIRST:
- 🔴 [BE] CORS issue on /auth (carried from 2025-06-09)

> 📋 Pending Tasks:
- [BE] Auth API refactor (carried from 2025-06-09)
- [FE] Dashboard responsive layout (carried from 2025-06-09)
- [DS] Fix ML pipeline timeout (carried from 2025-06-09)
```

### 3.4 Weekly Summary Structure

Generated on demand via `/week`, uses Groq API (free).

```markdown
# Week 23 Summary — Jun 09–13, 2025

## 📊 Stats at a Glance
| Domain | Tasks Done | Tasks Pending | Blockers Opened | Blockers Resolved |
|--------|-----------|---------------|-----------------|-------------------|
| Backend | 8 | 2 | 1 | 1 |
| Frontend | 5 | 1 | 0 | 0 |
| Data Science | 3 | 2 | 2 | 1 |

## 🖥️ Backend — This Week
### Completed ...
### Carried Forward ...

## 🌐 Frontend — This Week ...
## 📊 Data Science — This Week ...
## 🚧 Open Blockers Entering Next Week ...
## 🌅 Recommended Focus for Next Week ...
```

---

## 4. Desktop App Design

### 4.1 System Tray Behaviour

| Action | Result |
|---|---|
| Left-click tray icon | Floating window opens / closes (toggle) |
| Right-click tray icon | Context menu: Open, Settings, Quit |
| `Ctrl+Shift+Space` (global) | Open window from anywhere, even when unfocused |
| Click outside window | Window auto-hides (does not quit) |
| App launch | Starts silently in tray, spawns Python backend, no splash screen |
| App quit | Python backend killed cleanly, vault saved |

### 4.2 Floating Window Layout (360px wide)

```
┌──────────────────────────────────────────┐
│ 🧠 Obsidian Agent    Mon, Jun 9 · local  │  ← Header
├──────────────────────────────────────────┤
│ All │ Backend │ Frontend │ Data Science  │  ← Domain tabs
├──────────────────────────────────────────┤
│ 📋 4 tasks  🚧 1 blocker  ✅ 3 done     │  ← Live status strip
├──────────────────────────────────────────┤
│                                          │
│  You: stuck on CORS, can't proceed       │
│                                          │
│  Agent: [BE] Logged as blocker: CORS     │
│  issue on /auth. Pinned in today's note. │
│  ✓ Written to Blockers/active.md         │
│                                          │  ← Chat area
├──────────────────────────────────────────┤
│ /task  /blocker  /done  /priorities  /wk │  ← Slash hints
├──────────────────────────────────────────┤
│ [ Type or use / commands...         ] ➤  │  ← Input
└──────────────────────────────────────────┘
```

### 4.3 Slash Commands

| Command | Shorthand | What Happens |
|---|---|---|
| `/task [description]` | `/task:be` `/task:fe` `/task:ds` | Add task, auto-detect domain or force with suffix |
| `/blocker [description]` | `/b` | Log a blocker, link to today's note and active.md |
| `/done [description]` | `/d` | Complete a task or resolve a blocker |
| `/carry` | — | Move all pending tasks to tomorrow's Priorities |
| `/summary` | `/s` | Generate today's EOD summary (local model) |
| `/priorities` | `/p` | Show and write tomorrow's ranked priorities |
| `/week` | `/w` | Generate weekly summary — current week (Groq API) |
| `/status` | — | Show today's task counts by domain |
| `/search [query]` | — | Semantic search across vault (Phase 3) |

---

## 5. Agent Intelligence

### 5.1 Intent Classification

The agent maps natural language to tool calls using Hermes-3 locally. No API call needed for daily operations.

| What You Say | Intent Detected | Tool Called |
|---|---|---|
| "I'm working on the auth API refactor" | create_task → Backend | `add_task(desc, domain=BE, date=today)` |
| "Stuck on CORS, can't proceed" | create_blocker → Backend | `create_blocker(desc, domain=BE)` |
| "Fixed the CORS thing" | resolve_blocker → Backend | `resolve_blocker(desc)` |
| "Done with dashboard component" | complete_task → Frontend | `complete_task(desc, domain=FE)` |
| "Prep tomorrow" or `/carry` | carry_forward | `carry_tasks_forward(today, tomorrow)` |
| "How many tasks left?" or `/status` | status_query | `get_today_status()` |
| "Summarise this week" or `/week` | weekly_summary → Groq | `generate_weekly_summary(week_num)` |

### 5.2 Domain Auto-Detection

When you don't specify a domain, Hermes-3 infers it from keywords. If ambiguous, it asks before acting.

| Domain | Signal Keywords (sample) |
|---|---|
| Backend | api, endpoint, database, sql, server, auth, django, fastapi, redis, kafka, docker, migration, schema, query, microservice |
| Frontend | component, ui, css, react, vue, html, design, responsive, layout, button, form, typescript, animation, modal, nav |
| Data Science | model, training, dataset, pipeline, feature, accuracy, ml, prediction, notebook, pandas, tensorflow, pytorch, sklearn, etl |

### 5.3 Agent's Persistent Context

`Agent/context.md` is prepended to every prompt. Generated once from your existing vault, updated as the agent learns your patterns. It contains:

- Your role and focus areas (Backend, Frontend, Data Science)
- Active projects detected from your vault
- Technologies you use frequently (inferred from task language)
- Your preferred task format and naming patterns
- Vault structure map so the agent always knows where to write

### 5.4 Tool Set

```
create_daily_note(date)
add_task(description, domain, priority, date)
create_blocker(description, domain, related_task)
resolve_blocker(blocker_id_or_description)
complete_task(description, date)
carry_tasks_forward(from_date, to_date)
generate_daily_summary(date)              → Hermes-3 local
generate_weekly_summary(week)             → Groq API free
get_priorities_for_tomorrow()             → Groq API free
search_notes(query)                       → Phase 3
get_project_status(project)               → Phase 3
```

---

## 6. Full Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Desktop shell | Electron v28+ | Windows · system tray + floating window |
| UI framework | React + Vite v18/v5 | Inside Electron renderer |
| Agent framework | LangGraph (Python) | Stateful multi-step agent |
| API server | FastAPI + Uvicorn | localhost:8000 |
| Local LLM runtime | Ollama (latest) | GPU via CUDA — RTX 3050 |
| Primary local model | nous-hermes3 8B Q4_K_M | ~5GB · fits in 4GB VRAM |
| Fallback local model | phi3-mini 3.8B | ~2GB · fast intent-only fallback |
| **Cloud model** | **Groq API · Llama 3.3 70B** | **Free tier · console.groq.com** |
| Vault I/O | python-frontmatter | Parse YAML frontmatter in markdown |
| File watching | watchdog | Detect external Obsidian edits |
| Embeddings (Phase 3) | nomic-embed-text via Ollama | Local embeddings, no cloud needed |
| Vector store (Phase 3) | ChromaDB | Local persistent semantic search |
| Build / packaging | electron-builder | Produces `.exe` installer for Windows |

### Hardware Fit

> **Your machine: Ryzen 7 5800H · 16GB RAM · RTX 3050 4GB VRAM**
>
> Hermes-3 8B Q4_K_M uses ~4.5GB VRAM — fits your GPU exactly. FastAPI + Electron together use ~300MB RAM. ChromaDB (Phase 3) adds ~200MB. Total system overhead at idle: ~500MB RAM. No bottlenecks for daily dev use.

---

## 7. Codebase Structure

```
obsidian-agent/
├── electron/                          ← Desktop shell
│   ├── main.js                        ← App entry, tray icon, window management
│   ├── preload.js                     ← Electron context bridge
│   └── assets/
│       └── tray-icon.png              ← 16x16 + 32x32 tray icons
│
├── renderer/                          ← React UI (runs inside Electron)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ChatWindow.jsx         ← Message list + streaming
│   │   │   ├── DomainTabs.jsx         ← BE / FE / DS filter tabs
│   │   │   ├── StatusStrip.jsx        ← Today's live counts
│   │   │   ├── SlashMenu.jsx          ← Autocomplete on /
│   │   │   └── ActionConfirm.jsx      ← Inline vault write confirmations
│   │   ├── hooks/
│   │   │   ├── useChat.js             ← Streaming chat state
│   │   │   └── useStatus.js           ← Polling today's task counts
│   │   └── main.jsx
│   └── vite.config.js
│
├── backend/                           ← Python agent server
│   ├── main.py                        ← FastAPI app, /chat endpoint
│   ├── agent/
│   │   ├── core.py                    ← LangGraph agent definition
│   │   ├── intent.py                  ← Intent classifier prompt + parser
│   │   ├── context.py                 ← Load Agent/context.md into prompts
│   │   └── tools/
│   │       ├── task_tools.py          ← add_task, complete_task
│   │       ├── blocker_tools.py       ← create_blocker, resolve_blocker
│   │       ├── carry_tools.py         ← carry_tasks_forward
│   │       ├── summary_tools.py       ← daily (local) + weekly (Groq)
│   │       └── status_tools.py        ← get_today_status
│   ├── vault/
│   │   ├── reader.py                  ← Read notes, parse frontmatter
│   │   ├── writer.py                  ← Write notes, backup before write
│   │   └── templates.py              ← daily / weekly / project templates
│   └── config.py                      ← Vault path, model settings, Groq API key
│
├── scripts/
│   ├── generate_context.py            ← One-time: build Agent/context.md from vault
│   ├── setup.bat                      ← Windows one-command setup
│   └── dev.bat                        ← Start backend + Electron in dev mode
│
├── package.json                       ← Electron + build config
├── requirements.txt                   ← Python deps (includes groq SDK)
└── README.md
```

---

## 8. Implementation Phases

Six weeks from nothing to a production desktop app. You can start using the agent after Phase 1 — each phase makes it better.

---

### Phase 1 — Core Foundation *(Week 1–2)*
**Goal: Agent can read/write vault, basic task/blocker CRUD works**

- [ ] Install Ollama, pull Hermes-3, verify GPU inference speed
- [ ] Set up FastAPI backend with `/chat` endpoint
- [ ] Vault reader/writer (python-frontmatter), daily note creation from template
- [ ] `add_task`, `create_blocker`, `resolve_blocker`, `complete_task` tools
- [ ] Intent classifier prompt with domain auto-detection
- [ ] Basic React chat UI served from Electron (window only, no tray yet)
- [ ] Config file: vault path, model choice, Groq API key

> **Milestone:** Say "I'm working on auth today" → task appears in your Obsidian vault ✓

---

### Phase 2 — Desktop App Shell *(Week 2–3)*
**Goal: Real system tray app on Windows**

- [ ] Electron main process: system tray icon, window creation
- [ ] Floating window anchored above tray (360px, borderless)
- [ ] Auto-hide on click-outside, toggle on tray icon click
- [ ] Global hotkey: `Ctrl+Shift+Space`
- [ ] Electron spawns Python backend as child process on app start
- [ ] Python backend kills cleanly on app quit
- [ ] Windows startup entry (optional — runs on login)
- [ ] electron-builder config for `.exe` packaging

> **Milestone:** A real desktop app living in your system tray ✓

---

### Phase 3 — Full Daily Loop *(Week 3–4)*
**Goal: Complete daily workflow automation**

- [ ] `carry_tasks_forward` with attribution tags
- [ ] EOD daily summary (local Hermes-3)
- [ ] Weekly summary with **Groq API** (free Llama 3.3 70B)
- [ ] `get_priorities_for_tomorrow` — backlog analysis + ranking (Groq)
- [ ] Domain tabs + live status strip in UI
- [ ] Slash command autocomplete menu in chat input
- [ ] Inline action confirmations in chat ("Created blocker in Blockers/active.md")
- [ ] Agent changelog: every write logged to `Agent/changelog.md`
- [ ] Backup-before-write: keep last 3 versions of any modified file

> **Milestone:** Full daily loop — morning priorities, mid-day updates, EOD, carry-forward ✓

---

### Phase 4 — Starting Context + Vault Migration *(Week 4–5)*
**Goal: Agent knows your world from day one**

- [ ] `generate_context.py` — scans existing vault, extracts projects + tech stack + patterns
- [ ] Builds `Agent/context.md` — no need to re-explain yourself to the agent
- [ ] Interactive first-run setup wizard (vault path, Groq API key entry)
- [ ] Settings panel: change vault path, model, toggle cloud on/off
- [ ] Existing vault migration: detect and map current structure to new layout

> **Milestone:** Agent immediately understands your existing projects and context ✓

---

### Phase 5 — Intelligence Layer *(Week 5–6)*
**Goal: Agent gets smarter about your work patterns**

- [ ] ChromaDB local vector store + nomic-embed-text embeddings
- [ ] Index all vault notes on startup, incremental updates via watchdog
- [ ] `/search [query]` — semantic search across all notes
- [ ] Project context linking: tasks auto-link to matching project notes
- [ ] Blocker age tracking: oldest blockers surfaced first in priorities
- [ ] Recurring task detection: agent flags tasks added 3+ days in a row

> **Milestone:** Agent can say "You've had the ML pipeline timeout open for 4 days" ✓

---

### Phase 6 — Polish + Production *(Week 6+)*
**Goal: Installable, polished, production-ready**

- [ ] Auto-updater (electron-updater) for future versions
- [ ] Windows toast notification when carry-forward or summary completes
- [ ] Dark/light mode toggle (syncs with Windows system theme)
- [ ] Export weekly summary to PDF (optional)
- [ ] Performance: lazy-load vector index, don't block tray on cold start
- [ ] Final `.exe` packaging with icon, installer, self-signed cert

> **Milestone:** Production-ready app, installable on any Windows machine ✓

---

## 9. Setup Guide

### 9.1 Prerequisites

| Tool | Install | Notes |
|---|---|---|
| Node.js 20+ | nodejs.org | Required for Electron |
| Python 3.11+ | python.org | Required for FastAPI + LangGraph |
| Ollama | ollama.ai | Required for local model |
| CUDA Toolkit | nvidia.com/cuda | GPU acceleration for RTX 3050 |
| Git | git-scm.com | To clone the repo |
| **Groq API Key (free)** | **console.groq.com → API Keys** | **Free account, no credit card needed** |

> **Getting your Groq key:** Go to [console.groq.com](https://console.groq.com) → Sign up free → API Keys → Create API Key. Takes 2 minutes.

### 9.2 One-Command Setup (Windows)

```bat
git clone https://github.com/you/obsidian-agent
cd obsidian-agent
setup.bat --vault "C:\Users\You\ObsidianVault"
```

The setup script does:
- `pip install -r requirements.txt` (includes groq Python SDK)
- `npm install` in root and `renderer/`
- `ollama pull nous-hermes3` (~5GB download, one time)
- `ollama pull nomic-embed-text` (for Phase 3 search)
- Prompts for your **Groq API key** and vault path
- Runs `generate_context.py` on your vault
- Builds Electron app and opens it

### 9.3 Development Mode

```bat
dev.bat
```

Starts FastAPI on `:8000`, Vite dev server on `:5173`, and Electron pointed at Vite. Hot reload on all three layers.

---

## 10. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Desktop framework | Electron | You know web dev (React/JS), fastest path to a real app |
| Window style | Floating tray popup | Minimal friction — always one click away, never a full app to manage |
| Local model | Hermes-3 8B Q4 | Best instruction-following at this size, fits RTX 3050 4GB VRAM |
| Cloud model | Groq API (free) | Llama 3.3 70B rivals paid models, completely free tier |
| Agent framework | LangGraph | Stateful graph gives reliable multi-step tool execution |
| Vault interaction | Direct file I/O | No Obsidian plugin needed, works even when Obsidian is closed |
| Task storage | Vault IS the database | Single source of truth, no SQLite, everything in human-readable markdown |
| Backup strategy | Last 3 versions per file | Agent mistakes are recoverable without drama |
| Cloud trigger | Manual / on-demand only | You control when Groq API is called — no surprises |
| Domain detection | Keyword heuristic + LLM confirm | Fast for clear cases, asks when ambiguous — never silently wrong |
| Starting context | Generated from your vault | Agent knows your world from day one without you re-explaining |

---

## 11. Future Expansions (Post Phase 6)

| Feature | What It Adds |
|---|---|
| Voice input (Whisper.cpp) | Speak tasks while coding, hands-free logging |
| Git integration | Agent links tasks to commits/PRs automatically |
| Mobile access | Expose agent over LAN, chat from phone on same WiFi |
| Fine-tuning | After 30 days of logs, fine-tune Hermes on your own conversations |
| Pomodoro integration | Agent tracks deep work sessions, surfaces in weekly summary |
| Multi-vault | Switch between personal and work vaults in settings |

---

## Where to Start Right Now

1. **`ollama pull nous-hermes3`** — start the ~5GB download now, it takes time
2. **Get Groq API key** — [console.groq.com](https://console.groq.com) → sign up free → API Keys → Create (2 mins, no card)
3. **Decide your vault path** — the entire folder structure builds around it
4. **Say the word** — I'll start writing Phase 1 code: FastAPI backend or Electron shell, your choice

---

*Auto Obsidian Manager · Personal Dev Tool · Backend · Frontend · Data Science*
