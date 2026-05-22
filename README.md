# Codex Memory Enhancer

**Persistent, always-on memory for OpenAI Codex CLI.** No server, no daemon, no pip install — pure Python stdlib + SQLite.

```
codex-memory-enhancer/
├── install.sh                     ← Install everything in one command
├── skills/local-memory/
│   ├── SKILL.md                   ← Codex skill definition
│   └── memory.py                  ← Memory operations script (431 lines)
├── scripts/codex-memory           ← Wrapper: auto-restore context + launch Codex
└── config/
    └── codex-config.toml.example  ← Optional Codex profile
```

## Features

- **Session-to-session memory** — remembers projects, decisions, discoveries, user preferences
- **FTS5 full-text search** — fast semantic-like search via SQLite FTS5 (or LIKE fallback)
- **Dangerous content filter** — auto-rejects API keys, tokens, passwords, private keys
- **Zero dependencies** — Python stdlib only (`sqlite3`, `json`, `re`, `argparse`)
- **Fully local** — no server, no daemon, no cloud, no third-party API
- **4KB DB overhead** — negligible storage cost

## Quick Install

```bash
git clone https://github.com/wmyung/codex-memory-enhancer.git
cd codex-memory-enhancer
bash install.sh
```

The installer:
1. Copies `memory.py` + `SKILL.md` to `~/.codex/skills/local-memory/`
2. Installs `codex-memory` wrapper to `~/.local/bin/codex-memory`
3. Adds `[profiles.memory]` to `~/.codex/config.toml`
4. Adds `codexm` alias to `~/.bashrc`

## Usage

### Quick start (recommended)
```bash
codex-memory
```
This restores recent memory context, shows DB stats, then launches Codex with the `memory` profile.

### Inside Codex
The `$local-memory` skill is auto-loaded at startup. Use it naturally:

```
# Codex automatically restores context at session start
# Codex automatically saves important context during work
# Codex searches memory before asking you to repeat yourself
```

### Manual commands
```bash
# Save a memory
python3 ~/.codex/skills/local-memory/memory.py save \
  "Completed JWT auth refactor" \
  -k "project:auth-refactor" \
  -c project \
  -t "auth,jwt,refactor"

# Search
python3 ~/.codex/skills/local-memory/memory.py search "jwt"

# View recent
python3 ~/.codex/skills/local-memory/memory.py recent

# List all
python3 ~/.codex/skills/local-memory/memory.py list

# Read details
python3 ~/.codex/skills/local-memory/memory.py read 1

# Stats
python3 ~/.codex/skills/local-memory/memory.py stats

# Export
python3 ~/.codex/skills/local-memory/memory.py export -f markdown
```

### Categories
`general`, `preference`, `entity`, `event`, `case`, `pattern`, `project`, `task`, `decision`, `note` — or any custom label.

## How it works

```
codex-memory wrapper script
  │
  ├─ 1. python3 memory.py recent -n 5    ← Restore last session context
  ├─ 2. python3 memory.py stats          ← Show DB health
  └─ 3. codex -p memory "$@"             ← Launch Codex with memory profile
         │
         └── $local-memory skill loaded at Codex startup
               → search / save / list available during session
```

**Storage:** `~/.codex/skills/local-memory/memory.sqlite3` — single SQLite file, that's it.

## Safety

The script **automatically rejects** any content matching:
- API keys (`sk-...`, `AKIA...`)
- GitHub tokens (`ghp_...`)
- Slack tokens (`xox[baprs]-...`)
- Private keys (`-----BEGIN ... PRIVATE KEY-----`)
- Base64 secrets (40+ char blocks)

These patterns cannot be stored even intentionally — the script refuses with an error message.

## Requirements

- **Codex CLI** (v0.128.0+): `npm install -g @openai/codex`
- **Python 3.8+** (stdlib only)
- **Linux/macOS** (Windows WSL works)

## Related

- Inspired by [Hermes Agent](https://github.com/NousResearch/hermes-agent) Memory Enhancer
- [Codex CLI](https://github.com/openai/codex) — OpenAI's autonomous coding agent
