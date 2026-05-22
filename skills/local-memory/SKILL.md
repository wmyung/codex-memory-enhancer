---
name: local-memory
description: "Persistent session-to-session memory for Codex. No server, no daemon, no pip install. Remembers projects, decisions, discoveries, and context across sessions."
version: 1.0.0
---

# $local-memory — Persistent Memory for Codex

**What this is:** A local SQLite-backed memory system that preserves context across Codex sessions. No server, no daemon, no pip install — pure Python stdlib.

**Data location:** `~/.codex/skills/local-memory/memory.sqlite3`
**Script:** `python3 ~/.codex/skills/local-memory/memory.py`

## Session Start Protocol

When starting a session with `$local-memory`:

1. Run `python3 ~/.codex/skills/local-memory/memory.py recent -n 5` to see recent context.
2. Run `python3 ~/.codex/skills/local-memory/memory.py stats` for DB state.
3. If the user mentions something familiar, search before asking them to repeat: `python3 ~/.codex/skills/local-memory/memory.py search "<query>"`.

## Commands

### Save a memory
```
python3 ~/.codex/skills/local-memory/memory.py save "<content>" -k "<unique-key>" -c <category> -t "<tag1>,<tag2>"
```
- `-k` (key): Unique identifier, e.g. `project:my-project`, `decision:use-fastapi`
- `-c` (category): `general`, `preference`, `entity`, `event`, `case`, `pattern`, `project`, `task`, `decision`, `note`, or any custom
- `-t` (tags): Comma-separated for filtering

**When to save:**
- Starting/finishing a task — save what was done
- User gives important context, preferences, or constraints
- You discover a non-trivial insight (tool quirk, workaround)
- A decision is made that affects future work

### Search memory
```
python3 ~/.codex/skills/local-memory/memory.py search "<query>" [-n <limit>]
```
Always search before asking the user to repeat themselves. Uses SQLite FTS5 full-text search (or LIKE fallback).

### List memories
```
python3 ~/.codex/skills/local-memory/memory.py list [-n <limit>] [-c <category>]
```

### Read a specific memory
```
python3 ~/.codex/skills/local-memory/memory.py read <id>
```

### View recent activity
```
python3 ~/.codex/skills/local-memory/memory.py recent [-n <limit>]
```

### Delete a memory
```
python3 ~/.codex/skills/local-memory/memory.py forget <id>
```

### Database stats
```
python3 ~/.codex/skills/local-memory/memory.py stats
```

### Export all memories
```
python3 ~/.codex/skills/local-memory/memory.py export -f json
python3 ~/.codex/skills/local-memory/memory.py export -f markdown
```

## Safety Rules

1. **NEVER store secrets.** The script automatically rejects: API keys (`sk-...`, `AKIA...`), tokens (`ghp_...`, `xox[baprs]-...`), private keys (`-----BEGIN ... PRIVATE KEY-----`), and credential patterns. Do not bypass.

2. **Keep it concise.** Store summaries, decisions, discoveries, and key context — not code dumps or full error logs.

3. **Every memory should matter weeks later.** If it won't be useful next session, don't save it.

4. **Session boundaries.** When switching projects or starting a significant new task, save current context first.

## Example Workflow

```
# Session start — restore context
python3 ~/.codex/skills/local-memory/memory.py recent -n 5

# Search before asking
python3 ~/.codex/skills/local-memory/memory.py search "deployment issue"

# Save after completing a task
python3 ~/.codex/skills/local-memory/memory.py save \
  "Completed JWT auth refactor - middleware + token refresh + all tests passing" \
  -k "project:auth-refactor" -c project -t "auth,jwt,refactor"

# Save a discovery
python3 ~/.codex/skills/local-memory/memory.py save \
  "Surprising property: reads are 10x faster with index on updated_at" \
  -k "discovery:sqlite-index" -c note -t "sqlite,performance"

# Save user preference
python3 ~/.codex/skills/local-memory/memory.py save \
  "User prefers 2-space YAML, 4-space Python" \
  -k "pref:indentation" -c preference -t "style,convention"
```
