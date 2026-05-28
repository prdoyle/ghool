#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"
LINK="$BIN_DIR/ghool"
SKILL_DIR="$HOME/.claude/skills/ghool"
SKILL_FILE="$SKILL_DIR/SKILL.md"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
PERMISSION_RULE='Bash(ghool with-key *)'

check_venv()      { [ -d "$VENV" ]; }
check_installed() { [ -x "$VENV/bin/ghool" ]; }
check_linked()    { [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$VENV/bin/ghool" ]; }
check_skill()     { check_installed && [ -f "$SKILL_FILE" ] && \
                    "$VENV/bin/ghool" skill | diff - "$SKILL_FILE" &>/dev/null; }
check_path()      { command -v ghool &>/dev/null; }
check_permission() {
    [ -f "$CLAUDE_SETTINGS" ] || return 1
    python3 - "$CLAUDE_SETTINGS" "$PERMISSION_RULE" <<'EOF'
import json, sys
try:
    s = json.load(open(sys.argv[1]))
    sys.exit(0 if sys.argv[2] in s.get('permissions', {}).get('allow', []) else 1)
except Exception:
    sys.exit(1)
EOF
}

if [ "${1:-}" = "--status" ]; then
    check_venv       && echo "[✓] Virtual environment (.venv)" \
                     || echo "[✗] Virtual environment (.venv)"
    check_installed  && echo "[✓] Package installed" \
                     || echo "[✗] Package installed"
    check_linked     && echo "[✓] Binary linked (~/.local/bin/ghool)" \
                     || echo "[✗] Binary linked (~/.local/bin/ghool)"
    check_skill      && echo "[✓] Claude skill installed (~/.claude/skills/ghool/SKILL.md)" \
                     || echo "[✗] Claude skill installed (~/.claude/skills/ghool/SKILL.md)"
    check_path       && echo "[✓] On PATH (ghool command available)" \
                     || echo "[✗] On PATH (ghool command available)"
    check_permission && echo "[✓] Claude Code allowlist entry present (~/.claude/settings.json)" \
                     || echo "[✗] Claude Code allowlist entry present (~/.claude/settings.json)"
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

if check_permission; then
    echo "[✓] Claude Code allowlist entry already present"
else
    python3 - "$CLAUDE_SETTINGS" "$PERMISSION_RULE" <<'EOF'
import json, pathlib, sys
settings_path = pathlib.Path(sys.argv[1])
rule = sys.argv[2]
settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
allow = settings.setdefault('permissions', {}).setdefault('allow', [])
allow.append(rule)
settings_path.parent.mkdir(parents=True, exist_ok=True)
settings_path.write_text(json.dumps(settings, indent=2) + '\n')
EOF
    echo "[✓] Claude Code allowlist entry added (~/.claude/settings.json)"
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
