from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from . import auth, codex_api
from .config import (
    STATE_FILE,
    ConfigError,
    ensure_dirs,
    read_settings,
)
from .formatters import error_payload


def _now() -> datetime:
    return datetime.now().astimezone()


def setup_logging() -> None:
    from .config import LOG_FILE

    ensure_dirs()
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def load_last_success() -> dict | None:
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if data.get("ok"):
                return data
    except (OSError, json.JSONDecodeError):
        return None
    return None


def save_success(payload: dict) -> None:
    ensure_dirs()
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    STATE_FILE.chmod(0o600)


def _settings_kwargs(settings: dict[str, object]) -> dict[str, object]:
    return {
        "display_format": str(settings.get("display_format", "verbose")),
        "show_weekly_limits": bool(settings.get("show_weekly_limits", True)),
        "poll_interval_minutes": int(settings.get("poll_interval_minutes", 1)),
        "panel_icon": str(settings.get("panel_icon", "brain")),
    }


def refresh_status() -> dict[str, Any]:
    setup_logging()
    now = _now()
    last_success = load_last_success()
    settings = {
        "poll_interval_minutes": 1,
        "display_format": "verbose",
        "show_weekly_limits": True,
        "panel_icon": "brain",
    }

    try:
        settings = _settings_kwargs(read_settings())

        try:
            payload = codex_api.rate_limits_to_payload(
                codex_api.read_rate_limits(),
                now,
                poll_interval_minutes=settings["poll_interval_minutes"],
                display_format=settings["display_format"],
                show_weekly_limits=settings["show_weekly_limits"],
                panel_icon=settings["panel_icon"],
            )
            save_success(payload)
            return payload
        except codex_api.CodexApiError as exc:
            logging.info("codex cli api unavailable: %s", exc)

        summary = auth.codex_auth_summary()
        if not summary["has_access_token"]:
            return error_payload(
                "auth_required",
                "Codex: bejelentkezés kell",
                "Run `codex-session-widget login` or `codex login` so the Codex CLI API can read account rate limits.",
                last_success=last_success,
                poll_interval_minutes=settings["poll_interval_minutes"],
                display_format=settings["display_format"],
                show_weekly_limits=settings["show_weekly_limits"],
                panel_icon=settings["panel_icon"],
            )

        return error_payload(
            "parse_error",
            "Codex: adatforrás kell",
            "Codex CLI API did not return rate limit data.",
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            display_format=settings["display_format"],
            show_weekly_limits=settings["show_weekly_limits"],
            panel_icon=settings["panel_icon"],
        )
    except ConfigError as exc:
        logging.info("config error: %s", exc)
        return error_payload(
            "config_error",
            "Codex: hibás konfiguráció",
            str(exc),
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            display_format=settings["display_format"],
            show_weekly_limits=settings["show_weekly_limits"],
            panel_icon=settings["panel_icon"],
        )
    except PermissionError as exc:
        logging.info("auth required")
        return error_payload(
            "auth_required",
            "Codex: bejelentkezés kell",
            str(exc),
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            display_format=settings["display_format"],
            show_weekly_limits=settings["show_weekly_limits"],
            panel_icon=settings["panel_icon"],
        )
    except RuntimeError as exc:
        logging.info("auth runtime error: %s", exc)
        return error_payload(
            "auth_required",
            "Codex: bejelentkezés kell",
            str(exc),
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            display_format=settings["display_format"],
            show_weekly_limits=settings["show_weekly_limits"],
            panel_icon=settings["panel_icon"],
        )
    except (OSError, json.JSONDecodeError) as exc:
        logging.info("parse error: %s", exc.__class__.__name__)
        return error_payload(
            "parse_error",
            "Codex: nem olvasható",
            "Could not parse the analytics response.",
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            display_format=settings["display_format"],
            show_weekly_limits=settings["show_weekly_limits"],
            panel_icon=settings["panel_icon"],
        )
    except Exception as exc:
        logging.info("network error: %s", exc.__class__.__name__)
        return error_payload(
            "network_error",
            "Codex: hálózati hiba",
            "Could not refresh Codex analytics data.",
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            display_format=settings["display_format"],
            show_weekly_limits=settings["show_weekly_limits"],
            panel_icon=settings["panel_icon"],
        )


def cached_status() -> dict[str, Any]:
    last_success = load_last_success()
    if last_success:
        return last_success
    return refresh_status()
