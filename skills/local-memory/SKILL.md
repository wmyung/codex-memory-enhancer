---
name: local-memory
description: "Persistent session-to-session memory for Codex. No server, no daemon, no pip install — pure Python stdlib. Supports project-isolated DBs, importance scoring, TTL expiry, and optional semantic search."
version: 2.0.0
---

# $local-memory — Persistent Memory for Codex

**What this is:** A local SQLite-backed memory system that preserves context across Codex sessions. No server, no daemon, no external dependencies — pure Python stdlib.

**Data location:** `~/.codex/skills/local-memory/` (default) + `~/.codex/skills/local-memory/projects/*.sqlite3` (per-project)

**Script:** `python3 ~/.codex/skills/local-memory/memory.py`

## Quick Start

```
# Install (one-time)
bash ~/.codex/skills/local-memory/install.sh

# Session start — restore context
python3 ~/.codex/skills/local-memory/memory.py recent -n 5

# Save an important discovery
python3 ~/.codex/skills/local-memory/memory.py save \
  "DISCOVERY: reads are 10x faster with index on updated_at" \
  -k "discovery:sqlite-index" -c note -t "sqlite,performance" -i 4

# Search before asking the user to repeat themselves
python3 ~/.codex/skills/local-memory/memory.py search "deployment"
```

## Session Start Protocol

When starting a session with `$local-memory`:

1. Run `python3 ~/.codex/skills/local-memory/memory.py recent -n 5` to see recent context.
2. Run `python3 ~/.codex/skills/local-memory/memory.py stats` for DB state.
3. If the user mentions something familiar, search before asking them to repeat: `python3 ~/.codex/skills/local-memory/memory.py search "<query>"`.

## Commands

### Save a memory
```
python3 ~/.codex/skills/local-memory/memory.py save "<content>" \
  -k "<unique-key>" -c <category> -t "<tag1>,<tag2>" \
  -i <1-5> [--ttl 7d] [-p PROJECT]
```
- `-k` (key): Unique identifier, e.g. `project:my-project`, `decision:use-fastapi`
- `-c` (category): `general`, `preference`, `entity`, `event`, `case`, `pattern`, `project`, `task`, `decision`, `note`, or any custom
- `-t` (tags): Comma-separated for filtering (e.g. `project:B003,type:result`)
- `-i` (importance): 1–5, default 3. 4+ = high priority, always included in condense
- `--ttl`: Auto-expiry (e.g. `7d`, `30d`, `12h`). Expired memories are purged on next access
- `-p` (project): Project name for isolated DB (e.g. `-p B003`)

### Search memory
```
python3 ~/.codex/skills/local-memory/memory.py search "<query>" \
  [-n <limit>] [-t <tag-filter>] [--semantic] [-p PROJECT]
```
- Uses FTS5 full-text search by default, LIKE fallback
- `-t` filters by tag pattern, e.g. `-t "project:B003"` or `-t "type:result"`
- `--semantic`: if `sentence-transformers` is installed, uses semantic search (cosine similarity)
- Always search before asking the user to repeat themselves

### List memories
```
python3 ~/.codex/skills/local-memory/memory.py list [-n 20] [-c CATEGORY] [-p PROJECT]
```

### Read a specific memory
```
python3 ~/.codex/skills/local-memory/memory.py read <id> [-p PROJECT]
```

### View recent activity
```
python3 ~/.codex/skills/local-memory/memory.py recent [-n 10] [-p PROJECT]
```

### Delete a memory
```
python3 ~/.codex/skills/local-memory/memory.py forget <id> [-p PROJECT]
```

### Database stats
```
python3 ~/.codex/skills/local-memory/memory.py stats [-p PROJECT]
```
Shows: total count, category distribution, importance distribution, FTS5 status, date range, DB size.

### Condensed context (for injection)
```
python3 ~/.codex/skills/local-memory/memory.py condense [-n 5] [-p PROJECT]
```
Generates a brief context summary combining high-importance (4+) and recent memories — ideal for injecting into LLM system prompts at session start.

### Export
```
python3 ~/.codex/skills/local-memory/memory.py export [-f json|markdown] [-p PROJECT]
```

### Import from JSON
```
python3 ~/.codex/skills/local-memory/memory.py import -f export.json [-p PROJECT]
```

### Purge expired memories
```
python3 ~/.codex/skills/local-memory/memory.py cleanup [--dry-run] [-p PROJECT]
```

### Session end hook
```
python3 ~/.codex/skills/local-memory/memory.py session-end [-p PROJECT]
```
Purges expired memories and reports total count. Call at session exit.

## Safety Rules

1. **NEVER store secrets.** The script automatically rejects: API keys (`sk-...`, `AKIA...`), tokens (`ghp_...`, `xox[baprs]-...`), private keys (`-----BEGIN ... PRIVATE KEY-----`), and credential patterns. Do not bypass.

2. **Keep it concise.** Store summaries, decisions, discoveries, and key context — not code dumps or full error logs.

3. **Every memory should matter weeks later.** If it won't be useful next session, don't save it.

4. **Session boundaries.** When switching projects or starting a significant new task, save current context first.

## Examples

```
# Session start — restore context
python3 ~/.codex/skills/local-memory/memory.py recent -n 5

# Save after completing a task
python3 ~/.codex/skills/local-memory/memory.py save \
  "Completed JWT auth refactor — middleware + token refresh + all tests passing" \
  -k "project:auth-refactor" -c project -t "auth,jwt,refactor" -i 4

# Save a user preference
python3 ~/.codex/skills/local-memory/memory.py save \
  "User prefers 2-space YAML, 4-space Python" \
  -k "pref:indentation" -c preference -t "style,convention" -i 5

# Per-project memory
python3 ~/.codex/skills/local-memory/memory.py -p B003 save \
  "Analysis results: LDSC h2=0.15-0.25 across 3 MDD definitions" \
  -k "analysis:ldsc-h2" -c pattern -t "project:B003,type:result" -i 4 --ttl 90d

# Search with tag filter
python3 ~/.codex/skills/local-memory/memory.py search "deployment issue" -t "project:my-app"
```

## v1 → v2 Migration

The v2.0 upgrade is backward-compatible. Existing v1 databases are automatically detected and migrated:
- `importance` column added (default: 3)
- `ttl` column added (default: NULL)
- Project DBs are created automatically on `-p PROJECT` usage

No manual migration needed.
