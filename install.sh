#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi

.venv/bin/pip install -e ".[dev]"

mkdir -p ~/.local/bin
ln -sf "$(pwd)/.venv/bin/ghool" ~/.local/bin/ghool

if ! command -v ghool &>/dev/null; then
    echo ""
    echo "Installed to ~/.local/bin/ghool"
    echo "Add this to ~/.zshrc to put it on your PATH:"
    echo ""
    echo '  export PATH="$HOME/.local/bin:$PATH"'
    echo ""
    echo "Then run: source ~/.zshrc or start a fresh terminal window"
fi
