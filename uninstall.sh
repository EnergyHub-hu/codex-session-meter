#!/usr/bin/env bash
set -euo pipefail

UUID="codex-session-widget@local"
EXTENSION_TARGET="$HOME/.local/share/gnome-shell/extensions/$UUID"
BIN_LINK="$HOME/.local/bin/codex-session-widget"
VENV_DIR="$HOME/.local/share/codex-session-widget/venv"

if command -v gnome-extensions >/dev/null; then
  gnome-extensions disable "$UUID" >/dev/null 2>&1 || true
fi

rm -rf "$EXTENSION_TARGET" "$VENV_DIR"
rm -f "$BIN_LINK"

echo "Removed extension, helper venv, and command link."
echo "Kept ~/.config/codex-session-widget and ~/.cache/codex-session-widget for safety. Remove them manually if desired."
