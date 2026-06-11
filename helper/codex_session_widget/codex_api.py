from __future__ import annotations

import json
import subprocess
from datetime import datetime
from typing import Any

from .formatters import ok_payload
from .parser import parse_datetime


class CodexApiError(RuntimeError):
    pass


class CodexApiUnavailable(CodexApiError):
    pass


def _send_message(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if process.stdin is None:
        raise CodexApiUnavailable("Codex app-server stdin is unavailable.")
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _read_response(process: subprocess.Popen[str], message_id: int) -> dict[str, Any]:
    if process.stdout is None:
        raise CodexApiUnavailable("Codex app-server stdout is unavailable.")

    while True:
        line = process.stdout.readline()
        if not line:
            raise CodexApiUnavailable("Codex app-server closed before returning a response.")
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CodexApiUnavailable("Codex app-server returned invalid JSON.") from exc
        if message.get("id") != message_id:
            continue
        if "error" in message:
            raise CodexApiError(str(message["error"]))
        result = message.get("result")
        if not isinstance(result, dict):
            raise CodexApiUnavailable("Codex app-server response result is invalid.")
        return result


def read_rate_limits() -> dict[str, Any]:
    try:
        process = subprocess.Popen(
            ["codex", "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise CodexApiUnavailable("Codex CLI is not installed or not on PATH.") from exc

    try:
        _send_message(process, {"id": 1, "method": "initialize", "params": {"clientName": "codex-session-widget"}})
        _read_response(process, 1)
        _send_message(process, {"id": 2, "method": "account/rateLimits/read"})
        return _read_response(process, 2)
    finally:
        if process.stdin is not None:
            process.stdin.close()
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def _window_values(window: object, now: datetime) -> tuple[int | None, datetime | None]:
    if not isinstance(window, dict):
        return None, None

    percent_value = window.get("usedPercent")
    try:
        percent = int(round(float(percent_value))) if percent_value is not None else None
    except (TypeError, ValueError):
        percent = None

    reset_at = parse_datetime(window.get("resetsAt"), now=now)
    return percent, reset_at


def rate_limits_to_payload(
    response: dict[str, Any],
    now: datetime,
    *,
    poll_interval_minutes: int,
    display_format: str,
    show_weekly_limits: bool,
    panel_icon: str,
) -> dict[str, Any]:
    rate_limits = response.get("rateLimits")
    if not isinstance(rate_limits, dict):
        raise CodexApiUnavailable("Codex rate limit response is missing rateLimits.")

    primary_percent, primary_reset_at = _window_values(rate_limits.get("primary"), now)
    if primary_reset_at is None:
        raise CodexApiUnavailable("Codex rate limit response is missing primary reset time.")

    secondary_percent, secondary_reset_at = _window_values(rate_limits.get("secondary"), now)
    return ok_payload(
        primary_reset_at,
        now,
        "codex_app_server:account/rateLimits/read",
        percent=primary_percent,
        weekly_percent=secondary_percent,
        weekly_reset_at=secondary_reset_at,
        source_label="Codex CLI API",
        poll_interval_minutes=poll_interval_minutes,
        display_format=display_format,
        show_weekly_limits=show_weekly_limits,
        panel_icon=panel_icon,
    )
