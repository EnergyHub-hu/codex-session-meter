from __future__ import annotations

from datetime import datetime

from .config import DEFAULT_DISPLAY_FORMAT, DEFAULT_SHOW_WEEKLY_LIMITS, SESSION_SECONDS


def clamp_percent(value: float) -> int:
    return max(0, min(100, round(value)))


def calculate_percent(reset_at: datetime, now: datetime, window_seconds: int = SESSION_SECONDS) -> int:
    remaining = max(0, (reset_at - now).total_seconds())
    elapsed = max(0, window_seconds - remaining)
    return clamp_percent((elapsed / window_seconds) * 100)


def remaining_percent(used_percent: int) -> int:
    return clamp_percent(100 - clamp_percent(used_percent))


def format_remaining_hu(seconds: int) -> str:
    minutes = max(0, int(seconds // 60))
    if minutes >= 60:
        hours, mins = divmod(minutes, 60)
        return f"{hours}ó {mins}p"
    return f"{minutes}p"


def build_display(
    used_percent: int,
    reset_at: datetime,
    now: datetime,
    weekly_percent: int | None = None,
    weekly_reset_at: datetime | None = None,
    display_format: str = DEFAULT_DISPLAY_FORMAT,
    show_weekly_limits: bool = DEFAULT_SHOW_WEEKLY_LIMITS,
) -> str:
    reset_time = reset_at.astimezone().strftime("%H:%M")
    remaining = format_remaining_hu(max(0, int((reset_at - now).total_seconds())))
    weekly_reset_text = f" / {weekly_reset_at.astimezone().strftime('%m.%d.')}" if show_weekly_limits and weekly_reset_at else ""
    if display_format == "compact":
        session_text = f"{remaining_percent(used_percent)}%"
        if show_weekly_limits and weekly_percent is not None:
            session_text = f"{session_text} / {remaining_percent(weekly_percent)}%"
        return f"{session_text} | {reset_time} ({remaining}){weekly_reset_text}"

    session_text = f"Session {remaining_percent(used_percent)}%"
    if show_weekly_limits and weekly_percent is not None:
        session_text = f"{session_text} / {remaining_percent(weekly_percent)}%"
    return f"{session_text} | Reset {reset_time} ({remaining}){weekly_reset_text}"


def ok_payload(
    reset_at: datetime,
    now: datetime,
    source: str,
    percent: int | None = None,
    weekly_percent: int | None = None,
    weekly_reset_at: datetime | None = None,
    source_label: str | None = None,
    poll_interval_minutes: int | None = None,
    display_format: str = DEFAULT_DISPLAY_FORMAT,
    show_weekly_limits: bool = DEFAULT_SHOW_WEEKLY_LIMITS,
    panel_icon: str = "brain",
) -> dict:
    local_reset = reset_at.astimezone()
    local_now = now.astimezone()
    used_percent = calculate_percent(local_reset, local_now) if percent is None else clamp_percent(percent)
    remaining_seconds = max(0, int((local_reset - local_now).total_seconds()))
    weekly_reset_local = weekly_reset_at.astimezone() if weekly_reset_at else None
    return {
        "ok": True,
        "status": "ok",
        "display": build_display(
            used_percent,
            local_reset,
            local_now,
            weekly_percent=weekly_percent,
            weekly_reset_at=weekly_reset_local,
            display_format=display_format,
            show_weekly_limits=show_weekly_limits,
        ),
        "percent": remaining_percent(used_percent),
        "used_percent": used_percent,
        "weekly_percent": remaining_percent(weekly_percent) if weekly_percent is not None else None,
        "weekly_reset_at": weekly_reset_local.isoformat(timespec="seconds") if weekly_reset_local else None,
        "weekly_reset_date_local": weekly_reset_local.strftime("%m.%d.") if weekly_reset_local else None,
        "source_label": source_label or "Codex usage API",
        "reset_at": local_reset.isoformat(timespec="seconds"),
        "reset_time_local": local_reset.strftime("%H:%M"),
        "remaining_seconds": remaining_seconds,
        "remaining_human_hu": format_remaining_hu(remaining_seconds),
        "last_updated": local_now.isoformat(timespec="seconds"),
        "source": source,
        "settings": {
            **({"poll_interval_minutes": poll_interval_minutes} if poll_interval_minutes is not None else {}),
            "display_format": display_format,
            "show_weekly_limits": show_weekly_limits,
            "panel_icon": panel_icon,
        },
    }


def error_payload(
    status: str,
    display: str,
    message: str,
    *,
    last_success: dict | None = None,
    poll_interval_minutes: int | None = None,
    display_format: str = DEFAULT_DISPLAY_FORMAT,
    show_weekly_limits: bool = DEFAULT_SHOW_WEEKLY_LIMITS,
    panel_icon: str = "brain",
) -> dict:
    payload = {
        "ok": False,
        "status": status,
        "display": display,
        "message": message,
        "settings": {
            **({"poll_interval_minutes": poll_interval_minutes} if poll_interval_minutes is not None else {}),
            "display_format": display_format,
            "show_weekly_limits": show_weekly_limits,
            "panel_icon": panel_icon,
        },
    }
    payload["source_label"] = {
        "auth_required": "Codex CLI auth",
        "config_error": "Configuration",
        "network_error": "Network",
        "rate_limited": "Codex usage API",
        "parse_error": "Codex data source",
    }.get(status, "Codex data source")
    if last_success:
        payload["last_success"] = last_success
        payload["display"] = f"{last_success.get('display', display)} | {display}"
    return payload
