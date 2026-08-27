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
CLIENT_VERSION = "0.3.0"


def _codex_command() -> str:
    return shutil.which("codex") or str(Path.home() / ".local" / "bin" / "codex")


def _initialize_message() -> dict[str, Any]:
    return {
        "id": 1,
        "method": "initialize",
        "params": {
            "clientInfo": {
                "name": "codex-session-meter",
                "title": "Codex Session Meter",
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


SESSION_WINDOW_MAX_MINUTES = 2 * 24 * 60


def _window_values(window: object, now: datetime) -> tuple[int | None, datetime | None, int | None]:
    if not isinstance(window, dict):
        return None, None, None

    percent_value = window.get("usedPercent")
    try:
        percent = int(round(float(percent_value))) if percent_value is not None else None
    except (TypeError, ValueError):
        percent = None

    reset_at = parse_datetime(window.get("resetsAt"), now=now)

    minutes_value = window.get("windowDurationMins")
    try:
        window_minutes = int(minutes_value) if minutes_value is not None else None
    except (TypeError, ValueError):
        window_minutes = None

    return percent, reset_at, window_minutes


def _classify_windows(
    rate_limits: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    windows = []
    for key in ("primary", "secondary"):
        window = rate_limits.get(key)
        if isinstance(window, dict) and window.get("usedPercent") is not None and window.get("resetsAt") is not None:
            windows.append((key, window))

    if not windows:
        return None, None
    if len(windows) == 1:
        return windows[0][1], None

    def is_weekly(entry: tuple[str, dict[str, Any]]) -> bool:
        minutes = entry[1].get("windowDurationMins")
        try:
            return int(minutes) >= SESSION_WINDOW_MAX_MINUTES
        except (TypeError, ValueError):
            return False

    weekly_entries = [entry for entry in windows if is_weekly(entry)]
    session_entries = [entry for entry in windows if not is_weekly(entry)]
    if len(weekly_entries) == 1:
        return weekly_entries[0][1], session_entries[0][1] if session_entries else None
    return windows[0][1], windows[1][1]


def rate_limits_to_payload(
    response: dict[str, Any],
    now: datetime,
    *,
    poll_interval_minutes: int,
    show_session: bool,
    show_daily: bool,
    show_weekly: bool,
    weekly_workdays: int,
    panel_icon: str,
    display_mode: str = "pace",
) -> dict[str, Any]:
    rate_limits = response.get("rateLimits")
    if not isinstance(rate_limits, dict):
        raise CodexApiUnavailable("Codex rate limit response is missing rateLimits.")

    weekly_window, session_window = _classify_windows(rate_limits)
    weekly_used_percent, weekly_reset_at, _ = _window_values(weekly_window, now)
    if weekly_used_percent is None or weekly_reset_at is None:
        raise CodexApiUnavailable("Codex rate limit response is missing weekly usage data.")

    session_used_percent, session_reset_at, session_window_mins = (
        _window_values(session_window, now) if session_window is not None else (None, None, None)
    )
    return ok_payload(
        weekly_reset_at,
        now,
        "codex_app_server:account/rateLimits/read",
        weekly_used_percent=weekly_used_percent,
        source_label="Codex CLI API",
        poll_interval_minutes=poll_interval_minutes,
        show_session=show_session,
        show_daily=show_daily,
        show_weekly=show_weekly,
        weekly_workdays=weekly_workdays,
        panel_icon=panel_icon,
        session_used_percent=session_used_percent,
        session_reset_at=session_reset_at,
        session_window_mins=session_window_mins,
        display_mode=display_mode,
    )
