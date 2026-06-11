from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .formatters import ok_payload
from .parser import parse_datetime


class CodexApiError(RuntimeError):
    pass


class CodexApiUnavailable(CodexApiError):
    pass


APP_SERVER_TIMEOUT_SECONDS = 15.0
APP_SERVER_SHUTDOWN_SECONDS = 2.0
CLIENT_VERSION = "0.2.1"


def _codex_command() -> str:
    return shutil.which("codex") or str(Path.home() / ".local" / "bin" / "codex")


def _initialize_message() -> dict[str, Any]:
    return {
        "id": 1,
        "method": "initialize",
        "params": {
            "clientInfo": {
                "name": "codex-session-widget",
                "title": "Codex Session Widget",
                "version": CLIENT_VERSION,
            }
        },
    }


def _send_message(process: subprocess.Popen[str], message: dict[str, Any], deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise CodexApiUnavailable("Codex app-server request timed out.")
    if process.stdin is None:
        raise CodexApiUnavailable("Codex app-server stdin is unavailable.")
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise CodexApiUnavailable("Codex app-server request timed out.")
    return remaining


def _read_line(process: subprocess.Popen[str], deadline: float) -> str:
    if process.stdout is None:
        raise CodexApiUnavailable("Codex app-server stdout is unavailable.")

    stdout = process.stdout
    try:
        fd = stdout.fileno()
    except (AttributeError, OSError, ValueError):
        return stdout.readline()

    buffer = getattr(process, "_codex_stdout_buffer", "")
    if "\n" in buffer:
        line, rest = buffer.split("\n", 1)
        setattr(process, "_codex_stdout_buffer", rest)
        return line + "\n"

    while True:
        ready, _, _ = select.select([fd], [], [], _remaining_seconds(deadline))
        if not ready:
            if buffer:
                raise CodexApiUnavailable("Codex app-server returned invalid JSON.")
            raise CodexApiUnavailable("Codex app-server request timed out.")

        chunk = os.read(fd, 4096)
        if not chunk:
            if buffer:
                setattr(process, "_codex_stdout_buffer", "")
                return buffer
            return ""

        buffer += chunk.decode("utf-8", errors="replace")
        if "\n" in buffer:
            line, rest = buffer.split("\n", 1)
            setattr(process, "_codex_stdout_buffer", rest)
            return line + "\n"


def _read_response(process: subprocess.Popen[str], message_id: int, deadline: float) -> dict[str, Any]:
    while True:
        line = _read_line(process, deadline)
        if not line:
            raise CodexApiUnavailable("Codex app-server closed before returning a response.")
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CodexApiUnavailable("Codex app-server returned invalid JSON.") from exc
        if message.get("id") != message_id:
            continue
        if "error" in message:
            raise CodexApiError("Codex app-server returned an error.")
        result = message.get("result")
        if not isinstance(result, dict):
            raise CodexApiUnavailable("Codex app-server response result is invalid.")
        return result


def _cleanup_process(process: subprocess.Popen[str]) -> None:
    if process.stdin is not None:
        try:
            process.stdin.close()
        except OSError:
            pass
    try:
        process.terminate()
    except OSError:
        pass
    try:
        process.wait(timeout=APP_SERVER_SHUTDOWN_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=APP_SERVER_SHUTDOWN_SECONDS)
    except subprocess.TimeoutExpired:
        pass


def read_rate_limits(*, timeout_seconds: float = APP_SERVER_TIMEOUT_SECONDS) -> dict[str, Any]:
    try:
        process = subprocess.Popen(
            [_codex_command(), "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError as exc:
        raise CodexApiUnavailable("Codex CLI is not installed or not on PATH.") from exc

    deadline = time.monotonic() + timeout_seconds
    try:
        _send_message(process, _initialize_message(), deadline)
        _read_response(process, 1, deadline)
        _send_message(process, {"id": 2, "method": "account/rateLimits/read"}, deadline)
        return _read_response(process, 2, deadline)
    finally:
        _cleanup_process(process)


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
