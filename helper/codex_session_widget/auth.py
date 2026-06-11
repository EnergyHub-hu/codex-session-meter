from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import webbrowser

from .config import ANALYTICS_URL, CODEX_AUTH_FILE


def codex_cli_available() -> bool:
    return shutil.which("codex") is not None


def codex_auth_file_exists() -> bool:
    return CODEX_AUTH_FILE.exists()


def _access_token_from_data(data: object) -> str | None:
    if not isinstance(data, dict):
        return None

    tokens = data.get("tokens")
    if isinstance(tokens, dict):
        token = tokens.get("access_token")
        if isinstance(token, str) and token.strip():
            return token.strip()

    token = data.get("access_token")
    if isinstance(token, str) and token.strip():
        return token.strip()

    return None


def codex_access_token() -> str | None:
    try:
        data = json.loads(CODEX_AUTH_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None

    return _access_token_from_data(data)


def _auth_file_label() -> tuple[str, str]:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        expected = Path(codex_home).expanduser() / "auth.json"
        if CODEX_AUTH_FILE == expected:
            return "$CODEX_HOME/auth.json", "custom_codex_home"

    default_auth_file = Path.home() / ".codex" / "auth.json"
    if CODEX_AUTH_FILE == default_auth_file:
        return "~/.codex/auth.json", "default_codex_home"

    return "custom_codex_home/auth.json", "custom_codex_home"


def codex_auth_summary() -> dict:
    auth_file, auth_file_location = _auth_file_label()
    return {
        "ok": True,
        "auth_provider": "codex_cli",
        "codex_cli_available": codex_cli_available(),
        "auth_file": auth_file,
        "auth_file_location": auth_file_location,
        "auth_file_exists": codex_auth_file_exists(),
        "has_access_token": codex_access_token() is not None,
        "login_url": ANALYTICS_URL,
    }


def open_login() -> None:
    if codex_cli_available():
        subprocess.run(["codex", "login"], check=True)
        return

    webbrowser.open(ANALYTICS_URL)


def open_analytics() -> None:
    webbrowser.open(ANALYTICS_URL)


def logout() -> None:
    if codex_cli_available():
        subprocess.run(["codex", "logout"], check=False)
