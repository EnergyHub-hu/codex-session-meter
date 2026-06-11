#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UUID="codex-session-widget@local"
EXTENSION_TARGET="$HOME/.local/share/gnome-shell/extensions/$UUID"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/codex-session-widget"
CACHE_DIR="$HOME/.cache/codex-session-widget"
DATA_DIR="$HOME/.local/share/codex-session-widget"
VENV_DIR="$HOME/.local/share/codex-session-widget/venv"

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

mkdir -p "$BIN_DIR" "$(dirname "$EXTENSION_TARGET")" "$CONFIG_DIR" "$CACHE_DIR" "$DATA_DIR"
chmod 700 "$BIN_DIR" "$CONFIG_DIR" "$CACHE_DIR" "$DATA_DIR"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install "$ROOT_DIR/helper"

ln -sf "$VENV_DIR/bin/codex-session-widget" "$BIN_DIR/codex-session-widget"

rm -rf "$EXTENSION_TARGET"
mkdir -p "$EXTENSION_TARGET"
cp -R "$ROOT_DIR/extension/." "$EXTENSION_TARGET/"

if [ -e "$CONFIG_DIR/config.toml" ]; then
    chmod 600 "$CONFIG_DIR/config.toml"
fi
if [ -e "$CACHE_DIR/state.json" ]; then
    chmod 600 "$CACHE_DIR/state.json"
fi
if [ -e "$CACHE_DIR/widget.log" ]; then
    chmod 600 "$CACHE_DIR/widget.log"
fi

echo "Installed helper to $VENV_DIR"
echo "Installed GNOME extension to $EXTENSION_TARGET"
echo "Ensure $BIN_DIR is in PATH for GNOME Shell, then run:"
echo "  gnome-extensions enable $UUID"
echo "If it does not appear, log out/in or restart GNOME Shell, then enable it with Extension Manager."
