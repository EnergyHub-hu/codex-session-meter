from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any

from . import auth, codex_api
from .config import (
    STATE_FILE,
    ConfigError,
    _atomic_write_private_text,
    ensure_dirs,
    read_settings,
)
from .formatters import error_payload


LOG_MAX_BYTES = 64 * 1024
LOG_BACKUP_COUNT = 2


def _private_opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


class _PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        stream = self._builtin_open(
            self.baseFilename,
            self.mode,
            encoding=self.encoding,
            errors=self.errors,
            opener=_private_opener,
        )
        try:
            os.chmod(self.baseFilename, 0o600)
        except OSError:
            stream.close()
            raise
        return stream


def _now() -> datetime:
    return datetime.now().astimezone()


def setup_logging() -> None:
    from .config import LOG_FILE

    ensure_dirs()
    LOG_FILE.touch(mode=0o600, exist_ok=True)
    LOG_FILE.chmod(0o600)

    root_logger = logging.getLogger()
    log_path = os.path.abspath(LOG_FILE)
    for existing in root_logger.handlers:
        if not getattr(existing, "_codex_session_meter_handler", False):
            continue
        if getattr(existing, "baseFilename", None) == log_path:
            return
        root_logger.removeHandler(existing)
        existing.close()

    handler = _PrivateRotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    handler._codex_session_meter_handler = True
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


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
    _atomic_write_private_text(STATE_FILE, json.dumps(payload, ensure_ascii=False, indent=2))


def _settings_kwargs(settings: dict[str, object]) -> dict[str, object]:
    return {
        "show_session": bool(settings.get("show_session", True)),
        "show_daily": bool(settings.get("show_daily", True)),
        "show_weekly": bool(settings.get("show_weekly", True)),
        "weekly_workdays": int(settings.get("weekly_workdays", 5)),
        "poll_interval_minutes": int(settings.get("poll_interval_minutes", 1)),
        "panel_icon": str(settings.get("panel_icon", "brain")),
        "display_mode": str(settings.get("display_mode", "pace")),
    }


def refresh_status() -> dict[str, Any]:
    setup_logging()
    now = _now()
    last_success = load_last_success()
    settings = {
        "poll_interval_minutes": 1,
        "show_session": True,
        "show_daily": True,
        "show_weekly": True,
        "weekly_workdays": 5,
        "panel_icon": "brain",
        "display_mode": "pace",
    }

    try:
        settings = _settings_kwargs(read_settings())

        try:
            payload = codex_api.rate_limits_to_payload(
                codex_api.read_rate_limits(),
                now,
                poll_interval_minutes=settings["poll_interval_minutes"],
                show_session=settings["show_session"],
                show_daily=settings["show_daily"],
                show_weekly=settings["show_weekly"],
                weekly_workdays=settings["weekly_workdays"],
                panel_icon=settings["panel_icon"],
                display_mode=settings["display_mode"],
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
                "Run `codex-session-meter login` or `codex login` so the Codex CLI API can read account rate limits.",
                last_success=last_success,
                poll_interval_minutes=settings["poll_interval_minutes"],
                show_session=settings["show_session"],
                show_daily=settings["show_daily"],
                show_weekly=settings["show_weekly"],
                weekly_workdays=settings["weekly_workdays"],
                panel_icon=settings["panel_icon"],
                display_mode=settings["display_mode"],
            )

        return error_payload(
            "parse_error",
            "Codex: adatforrás kell",
            "Codex CLI API did not return rate limit data.",
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            show_session=settings["show_session"],
            show_daily=settings["show_daily"],
            show_weekly=settings["show_weekly"],
            weekly_workdays=settings["weekly_workdays"],
            panel_icon=settings["panel_icon"],
            display_mode=settings["display_mode"],
        )
    except ConfigError as exc:
        logging.info("config error: %s", exc)
        return error_payload(
            "config_error",
            "Codex: hibás konfiguráció",
            str(exc),
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            show_session=settings["show_session"],
            show_daily=settings["show_daily"],
            show_weekly=settings["show_weekly"],
            weekly_workdays=settings["weekly_workdays"],
            panel_icon=settings["panel_icon"],
            display_mode=settings["display_mode"],
        )
    except PermissionError as exc:
        logging.info("auth required")
        return error_payload(
            "auth_required",
            "Codex: bejelentkezés kell",
            str(exc),
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            show_session=settings["show_session"],
            show_daily=settings["show_daily"],
            show_weekly=settings["show_weekly"],
            weekly_workdays=settings["weekly_workdays"],
            panel_icon=settings["panel_icon"],
            display_mode=settings["display_mode"],
        )
    except RuntimeError as exc:
        logging.info("auth runtime error: %s", exc)
        return error_payload(
            "auth_required",
            "Codex: bejelentkezés kell",
            str(exc),
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            show_session=settings["show_session"],
            show_daily=settings["show_daily"],
            show_weekly=settings["show_weekly"],
            weekly_workdays=settings["weekly_workdays"],
            panel_icon=settings["panel_icon"],
            display_mode=settings["display_mode"],
        )
    except (OSError, json.JSONDecodeError) as exc:
        logging.info("parse error: %s", exc.__class__.__name__)
        return error_payload(
            "parse_error",
            "Codex: nem olvasható",
            "Could not parse the Codex CLI API response.",
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            show_session=settings["show_session"],
            show_daily=settings["show_daily"],
            show_weekly=settings["show_weekly"],
            weekly_workdays=settings["weekly_workdays"],
            panel_icon=settings["panel_icon"],
            display_mode=settings["display_mode"],
        )
    except Exception as exc:
        logging.info("network error: %s", exc.__class__.__name__)
        return error_payload(
            "network_error",
            "Codex: hálózati hiba",
            "Could not refresh Codex CLI API data.",
            last_success=last_success,
            poll_interval_minutes=settings["poll_interval_minutes"],
            show_session=settings["show_session"],
            show_daily=settings["show_daily"],
            show_weekly=settings["show_weekly"],
            weekly_workdays=settings["weekly_workdays"],
            panel_icon=settings["panel_icon"],
            display_mode=settings["display_mode"],
        )


def cached_status() -> dict[str, Any]:
    last_success = load_last_success()
    if last_success:
        return last_success
    return refresh_status()
