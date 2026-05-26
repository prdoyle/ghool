#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"
LINK="$BIN_DIR/ghool"
SKILL_DIR="$HOME/.claude/skills/ghool"
SKILL_FILE="$SKILL_DIR/SKILL.md"

check_venv()      { [ -d "$VENV" ]; }
check_installed() { [ -x "$VENV/bin/ghool" ]; }
check_linked()    { [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$VENV/bin/ghool" ]; }
check_skill()     { check_installed && [ -f "$SKILL_FILE" ] && \
                    "$VENV/bin/ghool" skill | diff - "$SKILL_FILE" &>/dev/null; }
check_path()      { command -v ghool &>/dev/null; }

if [ "${1:-}" = "--status" ]; then
    check_venv      && echo "[✓] Virtual environment (.venv)" \
                    || echo "[✗] Virtual environment (.venv)"
    check_installed && echo "[✓] Package installed" \
                    || echo "[✗] Package installed"
    check_linked    && echo "[✓] Binary linked (~/.local/bin/ghool)" \
                    || echo "[✗] Binary linked (~/.local/bin/ghool)"
    check_skill     && echo "[✓] Claude skill installed (~/.claude/skills/ghool/SKILL.md)" \
                    || echo "[✗] Claude skill installed (~/.claude/skills/ghool/SKILL.md)"
    check_path      && echo "[✓] On PATH (ghool command available)" \
                    || echo "[✗] On PATH (ghool command available)"
    exit 0
fi

if check_venv; then
    echo "[✓] Virtual environment already exists"
else
    echo "[ ] Creating virtual environment..."
    python3 -m venv "$VENV"
    echo "[✓] Virtual environment created"
fi

if check_installed; then
    echo "[✓] Package already installed"
else
    echo "[ ] Installing package..."
    "$VENV/bin/pip" install -e ".[dev]"
    echo "[✓] Package installed"
fi

mkdir -p "$BIN_DIR"
if check_linked; then
    echo "[✓] Binary already linked"
else
    ln -sf "$VENV/bin/ghool" "$LINK"
    echo "[✓] Binary linked to ~/.local/bin/ghool"
fi

mkdir -p "$SKILL_DIR"
if check_skill; then
    echo "[✓] Claude skill already up to date"
else
    "$VENV/bin/ghool" skill > "$SKILL_FILE"
    echo "[✓] Claude skill installed"
fi

if check_path; then
    echo "[✓] ghool is on your PATH"
else
    echo ""
    echo "Installed to ~/.local/bin/ghool"
    echo "Add this to ~/.zshrc to put it on your PATH:"
    echo ""
    echo '  export PATH="$HOME/.local/bin:$PATH"'
    echo ""
    echo "Then run: source ~/.zshrc or start a fresh terminal window"
fi
