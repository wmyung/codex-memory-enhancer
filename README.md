<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue"/>
  <img src="https://img.shields.io/badge/python-3.8%2B-blue"/>
  <img src="https://img.shields.io/badge/dependencies-0-success"/>
  <img src="https://img.shields.io/badge/server-none-success"/>
</p>

<h1 align="center">🧠 Codex Memory Enhancer</h1>
<p align="center">
  <b>Persistent, always-on memory for OpenAI Codex CLI.</b><br>
  No server. No daemon. No pip install. No vector DB. Pure Python stdlib + SQLite.
</p>

<p align="center">
  <code>bash install.sh</code> → <code>codex-memory</code> → Codex remembers everything. Done.
</p>

---

## The Problem

**Codex CLI has no long-term memory.** Every session starts from scratch. You tell it the same project context, the same preferences, the same constraints — over and over.

Vibe coding loses its magic when the agent has amnesia.

Existing solutions are overkill:
- Vector DBs (Chroma, Qdrant) → need a server, pip install, API, embedding model
- LangChain memory → framework lock-in, heavy
- LLM Wiki (Karpathy) → human-readable knowledge base, **not** an agent's working memory

**This is different.** It's not a wiki. It's not RAG. It's a **persistent scratchpad** that Codex uses automatically — session to session, project to project.

---

## Demo

```bash
# Monday — working on auth refactor
codex-memory
# Codex restores context, you work, Codex auto-saves progress

# Tuesday — new session
codex-memory
# 🧠 "Let me check what you were working on..."
# → Shows: "Completed JWT auth refactor - middleware + token refresh + tests"
# → Codex picks up right where you left off
```

[▶️ 23-second asciicast] (TODO: add screencast)

---

## Quick Install

```bash
git clone https://github.com/wmyung/codex-memory-enhancer.git
cd codex-memory-enhancer
bash install.sh
```

**What the installer does:**
1. Copies `memory.py` + `SKILL.md` → `~/.codex/skills/local-memory/`
2. Installs `codex-memory` wrapper → `~/.local/bin/codex-memory`
3. Adds `[profiles.memory]` → `~/.codex/config.toml`
4. Adds `codexm` alias → `~/.bashrc`

### One-liner (curl)
```bash
bash <(curl -s https://raw.githubusercontent.com/wmyung/codex-memory-enhancer/main/install.sh)
```

---

## Features

### 🧠 Session-to-session memory
Codex remembers projects, decisions, discoveries, preferences, and errors across sessions. Your context never dies.

### 🔍 FTS5 full-text search
SQLite FTS5 ranks results by relevance. Faster and smarter than grepping markdown files.

```bash
python3 memory.py search "jwt token refresh"
# → 1. "Completed JWT auth refactor" (score 0.00)
# → 2. "Discovered: token refresh race condition" (score -1.24)
```

### 🛡️ Built-in secret filter
**API keys, tokens, passwords, private keys cannot be stored.** The script rejects them at the content level — not as an afterthought, but as a hard guarantee.

```bash
python3 memory.py save "my api key is sk-abc123..."
# → ✗ Refused: content matches dangerous pattern 'sk-abc123...'
```

Patterns blocked: `sk-*` (OpenAI), `ghp_*` (GitHub), `AKIA*` (AWS), `xox[baprs]-*` (Slack), `-----BEGIN ... PRIVATE KEY-----`, base64 secrets.

### 🚫 Zero dependencies
```bash
# What you DON'T need:
# ❌ pip install chromadb
# ❌ pip install langchain
# ❌ pip install sentence-transformers
# ❌ docker pull qdrant/qdrant
# ❌ OPENAI_API_KEY for embeddings
# ❌ A server process

# What you DO need:
# ✅ Python 3.8+ (stdlib only — sqlite3, json, re, argparse — all built-in)
```

### 📦 Storage footprint: one file, 40KB
```
~/.codex/skills/local-memory/memory.sqlite3  ← literally the only file
```

40KB empty. ~200KB after months of use. No WAL explosion. No compaction needed.

### 🔄 Portable
```bash
# Move to another machine
scp user@server:.codex/skills/local-memory/memory.sqlite3 .

# Export to anything
python3 memory.py export -f markdown > memories.md
python3 memory.py export -f json > memories.json
```

No vendor lock-in. Your memory is a SQLite file — the most portable database format on earth.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  codex-memory (wrapper)                                      │
│                                                              │
│  1. python3 memory.py recent -n 5   ← "What was I doing?"    │
│  2. python3 memory.py stats         ← "How's the DB?"        │
│  3. codex -p memory "$@"            ← Launch Codex           │
│         │                                                     │
│         └── $local-memory skill auto-loaded at Codex startup  │
│               ├─ Session start → recent + stats               │
│               ├─ During work → auto-save context              │
│               └─ Before asking → search memory first           │
└─────────────────────────────────────────────────────────────┘
```

**Storage layer:**
```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Codex CLI   │────▶│   memory.py      │────▶│  SQLite FTS5 │
│  (codex exec)│     │  (431 lines)     │     │  (no server) │
└──────────────┘     └──────────────────┘     └──────────────┘
```

---

## Manual Commands

```bash
# Save
python3 memory.py save "User prefers 2-space YAML" -k "pref:yaml-style" -c preference -t "style,convention"

# Search (FTS5)
python3 memory.py search "deployment issue"

# List recent
python3 memory.py recent

# Read details
python3 memory.py read 7

# Delete
python3 memory.py forget 7

# DB stats
python3 memory.py stats

# Full export
python3 memory.py export -f markdown
```

### Categories
`general` · `preference` · `entity` · `event` · `case` · `pattern` · `project` · `task` · `decision` · `note` — or anything you want.

---

## Comparison: LLM Wiki vs Codex Memory Enhancer

Two different tools for two different jobs. Here's how they stack up:

| Dimension | LLM Wiki (Karpathy) | Codex Memory Enhancer |
|-----------|--------------------|----------------------|
| **What it stores** | Structured knowledge (concepts, entities, comparisons) | Working context (tasks, decisions, discoveries) |
| **Storage format** | Markdown files in a directory tree | Single SQLite file with FTS5 index |
| **Who reads it** | **Humans + AI** — opens in Obsidian, VS Code, any editor | **AI only** — accessed via `memory.py` CLI |
| **Who writes it** | Agent + human curation, ingest → summarize → file | Agent auto-saves during Codex sessions |
| **Search** | `grep` / `search_files` over markdown | FTS5 ranked full-text search |
| **Structure** | SCHEMA.md + index.md + log.md (strict conventions) | Key-value + category + tags (flexible) |
| **Safety filter** | None | Auto-rejects API keys, tokens, secrets |
| **Footprint** | Grows with every ingested source | ~40KB empty, ~200KB heavy use |
| **Portability** | Copy markdown files | Export to JSON or Markdown |
| **Best for** | Knowledge management, research, long-term reference | Session continuity, project context, working memory |
| **Dependencies** | None (markdown files) | None (Python stdlib) |
| **Setup time** | Manual directory creation + SCHEMA | `bash install.sh` — 3 seconds |

### When to use which

| Scenario | Use |
|----------|:---:|
| "I want a personal Wikipedia for my research" | ✅ **LLM Wiki** |
| "Codex keeps forgetting what I was working on" | ✅ **Memory Enhancer** |
| "I need to browse my notes in Obsidian" | ✅ **LLM Wiki** |
| "I want Codex to auto-save context without me thinking about it" | ✅ **Memory Enhancer** |
| Both! | **Use both** — export from Memory Enhancer, ingest into LLM Wiki |

### Complementary workflow

```
Codex Memory Enhancer          LLM Wiki
┌──────────────────┐          ┌──────────────────┐
│ Session memory   │──export─▶│ Knowledge base   │
│ (auto, ephemeral)│  markdow │ (curated, perman)│
└──────────────────┘          └──────────────────┘
```

Weekly or monthly: `python3 memory.py export -f markdown > ~/wiki/raw/memory-dump/YYYY-MM.md` → LLM Wiki ingests it. Short-term memory becomes long-term knowledge.

---

## Comparison: Other Approaches

| Solution | Server | pip install | Setup time | Auto-save | Secret filter | Offline |
|----------|:-----:|:-----------:|:----------:|:---------:|:-------------:|:-------:|
| **Codex Memory Enhancer** | ❌ | ❌ | **3 sec** | ✅ | ✅ | ✅ |
| LLM Wiki (Karpathy) | ❌ | ❌ | 5 min | ❌ | ❌ | ✅ |
| ChromaDB | ✅ | ✅ | 30 min | ❌ | ❌ | ✅ |
| Mem0 | ✅ | ✅ | 15 min | ❌ | ❌ | ❌ |
| LangChain Memory | ❌ | ✅ | 10 min | ❌ | ❌ | ✅ |
| OpenAI Assistants | ✅ | ❌ | 5 min | ❌ | ❌ | ❌ |
| Claude Projects | ✅ | ❌ | 1 min | ❌ | ❌ | ❌ |

---

## Requirements

- **Codex CLI** (v0.128.0+): `npm install -g @openai/codex`
- **Python 3.8+** (stdlib only — nothing to install)
- **OS**: Linux, macOS, Windows WSL

---

## Project Structure

```
codex-memory-enhancer/
├── install.sh                              ← 3-second install
├── skills/local-memory/
│   ├── SKILL.md                            ← Codex skill definition (loaded at startup)
│   └── memory.py                           ← Memory engine (431 lines, stdlib only)
├── scripts/codex-memory                     ← Wrapper: auto-restore + launch
└── config/codex-config.example.toml        ← Optional Codex profile
```

---

## Roadmap (ideas welcome)

- [ ] **TTL / auto-expiry**: Memories older than N days get archived or de-prioritized
- [ ] **Import from Claude Code / ChatGPT**: Migrate external context into the DB
- [ ] **CLI improvements**: Interactive `browse` mode, batch tag editor
- [ ] **Obsidian sync**: Auto-export to a markdown vault for human browsing
- [ ] **Embeddings (optional)**: Plug in `sentence-transformers` for true semantic search if installed

PRs welcome. Ideas welcome.

---

## Related

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** — multi-provider agent that inspired this. Has a built-in Memory Enhancer plugin.
- **[Codex CLI](https://github.com/openai/codex)** — OpenAI's autonomous coding agent CLI. This skill runs inside it.
- **[llm-wiki (Karpathy)](https://gist.github.com/karpathy/442a6bf555914e8939891c11519de94f)** — human-readable knowledge base in markdown.
- **[SQLite FTS5](https://www.sqlite.org/fts5.html)** — the search engine behind it all. No vector DB needed.
