#!/bin/bash
# codex-memory-enhancer install.sh
# Installs the local-memory skill for Codex CLI.
# No server, no daemon, no pip install — pure Python stdlib + SQLite.

set -euo pipefail

SKILL_DIR="$HOME/.codex/skills/local-memory"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🧠 Codex Memory Enhancer v2.0 — Install"
echo ""

# 1. Copy skill files
echo "📁 Installing skill to $SKILL_DIR..."
mkdir -p "$SKILL_DIR"
cp "$SCRIPT_DIR/skills/local-memory/memory.py" "$SKILL_DIR/"
cp "$SCRIPT_DIR/skills/local-memory/SKILL.md" "$SKILL_DIR/"

# 2. Create projects directory for per-project DBs
mkdir -p "$SKILL_DIR/projects"

# 3. Copy wrapper script (if exists)
if [ -f "$SCRIPT_DIR/scripts/codex-memory" ]; then
    echo "📁 Installing wrapper to ~/.local/bin/codex-memory..."
    mkdir -p "$HOME/.local/bin"
    cp "$SCRIPT_DIR/scripts/codex-memory" "$HOME/.local/bin/codex-memory"
    chmod +x "$HOME/.local/bin/codex-memory"
fi

# 4. Test the installation
echo "🔍 Verifying installation..."
if python3 -c "import sqlite3; print('✓ SQLite available')" 2>/dev/null; then
    python3 "$SKILL_DIR/memory.py" stats 2>/dev/null && echo "✓ Memory system working" || echo "  (first run: will initialize on first use)"
else
    echo "⚠️  Python sqlite3 module not found. Install python3 with sqlite support."
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Quick test:"
echo "  python3 ~/.codex/skills/local-memory/memory.py stats"
echo "  python3 ~/.codex/skills/local-memory/memory.py save 'Hello world' -k 'test:hello' -i 1"
echo ""
echo "Docs:"
echo "  cat ~/.codex/skills/local-memory/SKILL.md"
