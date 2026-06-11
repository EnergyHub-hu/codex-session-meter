from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
import subprocess
import urllib.error
import urllib.request
import webbrowser

from .config import ANALYTICS_URL, CODEX_AUTH_FILE
from .parser import MAX_ANALYTICS_PAYLOAD_CHARS


@dataclass(frozen=True)
class AuthenticatedResponse:
    status_code: int
    headers: dict[str, str]
    text: str


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


def codex_auth_summary() -> dict:
    return {
        "ok": True,
        "auth_provider": "codex_cli",
        "codex_cli_available": codex_cli_available(),
        "auth_file": str(CODEX_AUTH_FILE),
        "auth_file_exists": codex_auth_file_exists(),
        "has_access_token": codex_access_token() is not None,
        "login_url": ANALYTICS_URL,
    }


def open_login() -> None:
    if codex_cli_available():
        subprocess.run(["codex", "login"], check=True)
        return

    webbrowser.open(ANALYTICS_URL)


def _read_bounded_text(response) -> str:
    body = response.read(MAX_ANALYTICS_PAYLOAD_CHARS + 1)
    if len(body) > MAX_ANALYTICS_PAYLOAD_CHARS:
        raise RuntimeError("payload_too_large")
    return body.decode("utf-8", errors="replace")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_json_with_token(endpoint: str, headers: dict[str, str]) -> AuthenticatedResponse:
    request = urllib.request.Request(endpoint, headers=headers, method="GET")
    opener = urllib.request.build_opener(_NoRedirectHandler)
    try:
        with opener.open(request, timeout=30) as response:
            return AuthenticatedResponse(
                status_code=response.status,
                headers=dict(response.headers.items()),
                text=_read_bounded_text(response),
            )
    except urllib.error.HTTPError as exc:
        return AuthenticatedResponse(
            status_code=exc.code,
            headers=dict(exc.headers.items()),
            text=_read_bounded_text(exc),
        )


def open_analytics() -> None:
    webbrowser.open(ANALYTICS_URL)


def logout() -> None:
    if codex_cli_available():
        subprocess.run(["codex", "logout"], check=False)
