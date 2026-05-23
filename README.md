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
  <code>bash install.sh</code> → Codex remembers everything. Done.
</p>

---

## The Problem

**Codex CLI has no long-term memory.** Every session starts from scratch. You tell it the same project context, the same preferences, the same constraints — over and over.

Existing solutions are overkill:
- Vector DBs (Chroma, Qdrant) → need a server, pip install, API, embedding model
- LangChain memory → framework lock-in, heavy
- LLM Wiki → human-readable knowledge base, **not** an agent's working memory

**This is different.** It's not a wiki. It's not RAG. It's a **persistent scratchpad** that Codex uses automatically — session to session, project to project.

---

## Features

### 🧠 Session-to-session memory
Codex remembers projects, decisions, discoveries, preferences, and errors across sessions. Your context never dies.

### 📁 Per-project isolated databases
```
python3 memory.py save "analysis results: h2=0.15" -p B003 -k "project:ldsc" -i 4
python3 memory.py save "deployment config: port 8080" -p my-app -c config
```
Each project gets its own SQLite file. No cross-contamination.

### ⭐ Importance scoring (1–5)
High-importance memories (4+) get priority in context injection. Low-importance (1–2) stays searchable but doesn't clutter context.

```
-i 5 → Always included in session context
-i 1 → Searchable but not in condensed view
```

### ⏰ TTL auto-expiry
Memories self-destruct after a duration:
```
python3 memory.py save "temp build config" -k "build:temp" -i 2 --ttl 7d
```

### 🔍 FTS5 full-text search
SQLite FTS5 ranks results by relevance. Faster and smarter than grepping markdown files.

```
python3 memory.py search "deployment issue"
```

### 🏷️ Tag filtering
```
python3 memory.py search "auth" -t "project:my-app"
python3 memory.py list -c preference
```

### 🛡️ Built-in secret filter
**API keys, tokens, passwords, private keys cannot be stored.** The script rejects them at the content level — not as an afterthought, but as a hard guarantee.

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
# ✅ Python 3.8+ (stdlib only)
```

### 🔬 Optional semantic search
If `sentence-transformers` is installed, `search --semantic` uses cosine similarity for semantic matching.

### 🔄 Portable
```bash
# Export
python3 memory.py export -f markdown > memories.md
python3 memory.py export -f json > memories.json

# Import
python3 memory.py import -f memories.json
```

---

## Quick Install

```bash
git clone <repo-url>
cd codex-memory-enhancer
bash install.sh
```

**What the installer does:**
1. Copies `memory.py` + `SKILL.md` → `~/.codex/skills/local-memory/`
2. Creates `projects/` directory for per-project DBs

---

## Commands

```bash
# Save a memory
python3 memory.py save "<content>" \
  -k "<unique-key>" -c <category> -t "<tag1>,<tag2>" \
  -i <1-5> [--ttl 7d] [-p PROJECT]

# Search (FTS5 or LIKE fallback)
python3 memory.py search "<query>" [-n 10] [-t TAG] [--semantic] [-p PROJECT]

# List recent
python3 memory.py recent [-n 10] [-p PROJECT]

# List all
python3 memory.py list [-n 20] [-c CATEGORY] [-p PROJECT]

# Read details
python3 memory.py read <id> [-p PROJECT]

# Delete
python3 memory.py forget <id> [-p PROJECT]

# DB stats
python3 memory.py stats [-p PROJECT]

# Context injection (high-importance + recent)
python3 memory.py condense [-n 5] [-p PROJECT]

# Export
python3 memory.py export [-f json|markdown] [-p PROJECT]

# Import
python3 memory.py import -f export.json [-p PROJECT]

# Purge expired
python3 memory.py cleanup [--dry-run] [-p PROJECT]

# Session end
python3 memory.py session-end [-p PROJECT]
```

### Categories
`general` · `preference` · `entity` · `event` · `case` · `pattern` · `project` · `task` · `decision` · `note` — or anything you want.

---

## Example Workflow

```bash
# Session start — restore context
python3 ~/.codex/skills/local-memory/memory.py condense -n 5
python3 ~/.codex/skills/local-memory/memory.py stats

# Save a discovery
python3 ~/.codex/skills/local-memory/memory.py save \
  "SQLite reads are 10x faster with index on updated_at" \
  -k "discovery:sqlite-index" -c note -t "sqlite,performance" -i 4

# Save a user preference
python3 ~/.codex/skills/local-memory/memory.py save \
  "User prefers 2-space YAML, 4-space Python" \
  -k "pref:indentation" -c preference -t "style,convention" -i 5

# Per-project context
python3 ~/.codex/skills/local-memory/memory.py -p B003 save \
  "Analysis results: correlation r=0.42, p<0.001" \
  -k "analysis:correlation" -c pattern -i 4 --ttl 90d

# Search before asking user to repeat themselves
python3 ~/.codex/skills/local-memory/memory.py search "deployment"
```

---

## Session Start Protocol (for Codex)

When a session starts, the skill loads automatically. Recommended flow:

1. Run `python3 ~/.codex/skills/local-memory/memory.py condense -n 5` for context
2. Run `python3 ~/.codex/skills/local-memory/memory.py stats` for DB state
3. Search before asking: `python3 ~/.codex/skills/local-memory/memory.py search "<query>"`
4. Save context on task completion

---

## Requirements

- **Codex CLI** (v0.128.0+): `npm install -g @openai/codex`
- **Python 3.8+** (stdlib only)
- **OS**: Linux, macOS, Windows WSL

---

## Project Structure

```
codex-memory-enhancer/
├── install.sh                    ← One-shot install
├── README.md                     ← This file
├── LICENSE                       ← MIT
├── skills/local-memory/
│   ├── SKILL.md                  ← Codex skill definition
│   └── memory.py                 ← Memory engine (stdlib only)
├── scripts/
│   └── codex-memory              ← Optional wrapper script
├── config/
│   └── codex-config.example.toml ← Optional Codex profile
└── .gitignore
```

---

## Data Location

| Data | Path |
|------|------|
| Default DB | `~/.codex/skills/local-memory/memory.sqlite3` |
| Per-project DBs | `~/.codex/skills/local-memory/projects/<project>.sqlite3` |
| Skill definition | `~/.codex/skills/local-memory/SKILL.md` |
| Script | `~/.codex/skills/local-memory/memory.py` |

---

## v1 → v2 Migration

The v2.0 upgrade is backward-compatible. Existing v1 databases are automatically detected and migrated:
- New columns: `importance` (default: 3), `ttl` (default: NULL) — added via ALTER TABLE
- Project DBs are created automatically on `-p PROJECT` usage
- FTS triggers are recreated on next access

No manual migration needed. Run `python3 memory.py stats` to verify.

---

## Roadmap

- [ ] Interactive `browse` mode
- [ ] Batch tag editor
- [ ] Obsidian sync
- [ ] Richer semantic search with caching
- [ ] Memory consolidation (merge duplicates)

PRs welcome. Ideas welcome.

---

## Related

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** — multi-provider agent framework with built-in Memory Enhancer plugin
- **[Codex CLI](https://github.com/openai/codex)** — OpenAI's autonomous coding agent CLI
- **[SQLite FTS5](https://www.sqlite.org/fts5.html)** — the search engine behind it all. No vector DB needed.
