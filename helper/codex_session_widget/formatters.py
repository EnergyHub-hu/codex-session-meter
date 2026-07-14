from __future__ import annotations

from datetime import datetime

from .config import DEFAULT_DISPLAY_FORMAT


def clamp_percent(value: float) -> int:
    return max(0, min(100, round(value)))


def remaining_percent(used_percent: int) -> int:
    return clamp_percent(100 - clamp_percent(used_percent))


def format_remaining_hu(seconds: int) -> str:
    minutes = max(0, int(seconds // 60))
    if minutes >= 24 * 60:
        days, remaining_minutes = divmod(minutes, 24 * 60)
        hours, mins = divmod(remaining_minutes, 60)
        return f"{days}n {hours}ó {mins}p"
    if minutes >= 60:
        hours, mins = divmod(minutes, 60)
        return f"{hours}ó {mins}p"
    return f"{minutes}p"


def build_display(
    weekly_used_percent: int,
    weekly_reset_at: datetime,
    now: datetime,
    display_format: str = DEFAULT_DISPLAY_FORMAT,
) -> str:
    reset_date = weekly_reset_at.astimezone().strftime("%m.%d.")
    quota_remaining = remaining_percent(weekly_used_percent)
    if display_format == "compact":
        return f"{quota_remaining}% | {reset_date}"

    return f"Heti keret {quota_remaining}% | Reset {reset_date}"


def ok_payload(
    weekly_reset_at: datetime,
    now: datetime,
    source: str,
    weekly_used_percent: int,
    source_label: str | None = None,
    poll_interval_minutes: int | None = None,
    display_format: str = DEFAULT_DISPLAY_FORMAT,
    weekly_workdays: int = 5,
    panel_icon: str = "brain",
) -> dict:
    local_reset = weekly_reset_at.astimezone()
    local_now = now.astimezone()
    used_percent = clamp_percent(weekly_used_percent)
    remaining_seconds = max(0, int((local_reset - local_now).total_seconds()))
    return {
        "ok": True,
        "status": "ok",
        "display": build_display(
            used_percent,
            local_reset,
            local_now,
            display_format=display_format,
        ),
        "weekly_percent": remaining_percent(used_percent),
        "weekly_used_percent": used_percent,
        "weekly_reset_at": local_reset.isoformat(timespec="seconds"),
        "weekly_reset_date_local": local_reset.strftime("%m.%d."),
        "source_label": source_label or "Codex usage API",
        "reset_at": local_reset.isoformat(timespec="seconds"),
        "reset_time_local": local_reset.strftime("%m.%d. %H:%M"),
        "remaining_seconds": remaining_seconds,
        "remaining_human_hu": format_remaining_hu(remaining_seconds),
        "last_updated": local_now.isoformat(timespec="seconds"),
        "source": source,
        "settings": {
            **({"poll_interval_minutes": poll_interval_minutes} if poll_interval_minutes is not None else {}),
            "display_format": display_format,
            "weekly_workdays": weekly_workdays,
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
    weekly_workdays: int = 5,
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
            "weekly_workdays": weekly_workdays,
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
