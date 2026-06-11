from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime
from typing import Any

from . import auth, codex_api
from .config import (
    CONFIG_FILE,
    STATE_FILE,
    ConfigError,
    ensure_dirs,
    read_simple_config,
    read_settings,
    validate_json_endpoint,
    validate_sample_file,
)
from .formatters import error_payload, ok_payload
from .parser import ParseError, parse_analytics_payload, parse_datetime

AuthenticatedResponse = auth.AuthenticatedResponse


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


def _extract_secondary_window(text: str, content_type: str) -> tuple[int | None, datetime | None]:
    if "json" not in content_type.lower() and not text.lstrip().startswith(("{", "[")):
        return None, None

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, None

    queue: deque[Any] = deque([data])
    while queue:
        node = queue.popleft()
        if isinstance(node, dict):
            secondary = node.get("secondary_window")
            if isinstance(secondary, dict):
                used_value = secondary.get("used_percent")
                try:
                    weekly_used_percent = int(round(float(used_value))) if used_value is not None else None
                except (TypeError, ValueError):
                    weekly_used_percent = None

                weekly_reset_at = parse_datetime(secondary.get("reset_at"))
                return weekly_used_percent, weekly_reset_at
            for value in node.values():
                if isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    queue.append(value)

    return None, None


def _read_sample(
    path_value: str,
    now: datetime,
    *,
    poll_interval_minutes: int,
    display_format: str,
    show_weekly_limits: bool,
    panel_icon: str,
) -> dict:
    path = validate_sample_file(path_value)
    text = path.read_text(encoding="utf-8")
    content_type = "application/json" if path.suffix == ".json" else "text/html"
    reset_at, percent, source = parse_analytics_payload(text, content_type, now=now)
    weekly_used_percent, weekly_reset_at = _extract_secondary_window(text, content_type)
    return ok_payload(
        reset_at,
        now,
        f"sample_file:{source}",
        percent=percent,
        weekly_percent=weekly_used_percent,
        weekly_reset_at=weekly_reset_at,
        source_label="Sample file",
        poll_interval_minutes=poll_interval_minutes,
        display_format=display_format,
        show_weekly_limits=show_weekly_limits,
        panel_icon=panel_icon,
    )


def _fetch_configured_json_endpoint(
    endpoint: str,
    now: datetime,
    *,
    poll_interval_minutes: int,
    display_format: str,
    show_weekly_limits: bool,
    panel_icon: str,
) -> dict:
    endpoint = validate_json_endpoint(endpoint)
    access_token = auth.codex_access_token()
    if access_token is None:
        raise PermissionError("Run `codex login` to create Codex CLI auth at ~/.codex/auth.json.")

    headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}", "User-Agent": "codex-session-widget/0.1"}
    response = auth.fetch_json_with_token(endpoint, headers)
    if 300 <= response.status_code < 400:
        raise ConfigError("Configured endpoint must not redirect.")
    if response.status_code in {401, 403}:
        raise PermissionError("Authentication required for configured endpoint")
    if response.status_code == 429:
        raise RuntimeError("rate_limited")
    if response.status_code >= 400:
        raise RuntimeError("network_error")
    content_type = response.headers.get("content-type", "")
    reset_at, percent, source = parse_analytics_payload(response.text, content_type, now=now)
    weekly_used_percent, weekly_reset_at = _extract_secondary_window(response.text, content_type)
    return ok_payload(
        reset_at,
        now,
        f"configured_endpoint:{source}",
        percent=percent,
        weekly_percent=weekly_used_percent,
        weekly_reset_at=weekly_reset_at,
        source_label="Codex usage API",
        poll_interval_minutes=poll_interval_minutes,
        display_format=display_format,
        show_weekly_limits=show_weekly_limits,
        panel_icon=panel_icon,
    )


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
        config = read_simple_config()
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

        if sample_file := config.get("sample_file"):
            payload = _read_sample(
                sample_file,
                now,
                poll_interval_minutes=settings["poll_interval_minutes"],
                display_format=settings["display_format"],
                show_weekly_limits=settings["show_weekly_limits"],
                panel_icon=settings["panel_icon"],
            )
            save_success(payload)
            return payload

        if json_endpoint := config.get("json_endpoint"):
            payload = _fetch_configured_json_endpoint(
                json_endpoint,
                now,
                poll_interval_minutes=settings["poll_interval_minutes"],
                display_format=settings["display_format"],
                show_weekly_limits=settings["show_weekly_limits"],
                panel_icon=settings["panel_icon"],
            )
            save_success(payload)
            return payload

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
            f"Codex CLI API did not return rate limit data. Optional fallback sources can still be configured with json_endpoint or sample_file in {CONFIG_FILE}.",
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
        if str(exc) == "rate_limited":
            return error_payload(
                "rate_limited",
                "Codex: rate limit",
                "The analytics endpoint returned HTTP 429.",
                last_success=last_success,
                poll_interval_minutes=settings["poll_interval_minutes"],
                display_format=settings["display_format"],
                show_weekly_limits=settings["show_weekly_limits"],
                panel_icon=settings["panel_icon"],
            )
        if str(exc) == "network_error":
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
    except (OSError, ParseError, json.JSONDecodeError) as exc:
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
