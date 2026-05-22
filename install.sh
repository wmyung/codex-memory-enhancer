#!/bin/bash
# codex-memory-enhancer install.sh
# Installs the local-memory skill for Codex CLI.
# No server, no daemon, no pip install — pure Python stdlib + SQLite.

set -euo pipefail

SKILL_DIR="$HOME/.codex/skills/local-memory"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🧠 Codex Memory Enhancer — Install"
echo ""

# 1. Copy skill files
echo "📁 Installing skill to $SKILL_DIR..."
mkdir -p "$SKILL_DIR"
cp "$SCRIPT_DIR/skills/local-memory/memory.py" "$SKILL_DIR/"
cp "$SCRIPT_DIR/skills/local-memory/SKILL.md" "$SKILL_DIR/"

# 2. Copy wrapper script
echo "📁 Installing wrapper to ~/.local/bin/codex-memory..."
mkdir -p "$HOME/.local/bin"
cp "$SCRIPT_DIR/scripts/codex-memory" "$HOME/.local/bin/codex-memory"
chmod +x "$HOME/.local/bin/codex-memory"

# 3. Optional: add Codex profile
CONFIG_FILE="$HOME/.codex/config.toml"
if [ -f "$CONFIG_FILE" ] && ! grep -q "profiles.memory" "$CONFIG_FILE" 2>/dev/null; then
    echo "📝 Adding [profiles.memory] to $CONFIG_FILE..."
    cat >> "$CONFIG_FILE" << 'TOMLEOF'

[profiles.memory]
model = "gpt-5.5"

[profiles.memory.project_doc]
# === LOCAL MEMORY SYSTEM ===
# This Codex environment has $local-memory skill installed.
#
# SESSION START: Run `python3 ~/.codex/skills/local-memory/memory.py recent -n 5`
#   and `python3 ~/.codex/skills/local-memory/memory.py stats`
#
# DURING SESSION:
# - Search before asking: `python3 ~/.codex/skills/local-memory/memory.py search "query"`
# - Save context: `python3 ~/.codex/skills/local-memory/memory.py save "content" -k "key" -c cat -t "tags"`
# - NEVER store API keys, tokens, passwords (script auto-rejects)
TOMLEOF
fi

# 4. Optional: add alias to .bashrc
if ! grep -q "codex-memory" "$HOME/.bashrc" 2>/dev/null; then
    echo "📝 Adding codexm alias to ~/.bashrc..."
    cat >> "$HOME/.bashrc" << 'ALIASEOF'

# codex-memory: auto-restore memory context before Codex
alias codexm='codex-memory'
ALIASEOF
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Usage:"
echo "  codex-memory        # Auto-restore memory + launch Codex (recommended)"
echo "  codex -p memory     # Launch with memory profile"
echo ""
echo "Inside Codex:"
echo "  \$local-memory skill is auto-loaded."
echo "  Just work normally — Codex will save/restore context."
echo ""
echo "To verify:"
echo "  python3 ~/.codex/skills/local-memory/memory.py stats"
