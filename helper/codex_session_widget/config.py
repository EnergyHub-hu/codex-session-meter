from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib

APP_NAME = "codex-session-widget"
ANALYTICS_URL = "https://chatgpt.com/codex/cloud/settings/analytics"
ALT_ANALYTICS_URL = "https://chatgpt.com/codex/settings/usage"
SESSION_SECONDS = 5 * 60 * 60
DEFAULT_POLL_INTERVAL_MINUTES = 1
DEFAULT_DISPLAY_FORMAT = "verbose"
DEFAULT_SHOW_WEEKLY_LIMITS = True
DEFAULT_PANEL_ICON = "brain"
ALLOWED_POLL_INTERVALS = (1, 5, 10, 15)
ALLOWED_DISPLAY_FORMATS = frozenset({"verbose", "compact"})
ALLOWED_PANEL_ICONS = frozenset({"brain", "robot", "chip", "circuit", "atom", "terminal", "fire", "boom", "star", "sparkle"})
ALLOWED_ENDPOINT_HOSTS = frozenset({"chatgpt.com"})
ALLOWED_ENDPOINT_SUFFIXES = (".openai.com",)


class ConfigError(ValueError):
    pass


def _xdg_path(env_name: str, default: str) -> Path:
    return Path(os.environ.get(env_name, default)).expanduser()


CONFIG_DIR = _xdg_path("XDG_CONFIG_HOME", "~/.config") / APP_NAME
CACHE_DIR = _xdg_path("XDG_CACHE_HOME", "~/.cache") / APP_NAME
DATA_DIR = _xdg_path("XDG_DATA_HOME", "~/.local/share") / APP_NAME
SAMPLE_DIR = CONFIG_DIR / "samples"
SETTINGS_FILE = CONFIG_DIR / "settings.toml"

CONFIG_FILE = CONFIG_DIR / "config.toml"
STATE_FILE = CACHE_DIR / "state.json"
LOG_FILE = CACHE_DIR / "widget.log"
CODEX_AUTH_FILE = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "auth.json"


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    for path in (CONFIG_DIR, CACHE_DIR, DATA_DIR, SAMPLE_DIR):
        path.chmod(0o700)


def _load_toml_config(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            loaded = tomllib.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("Configuration file must be valid TOML.") from exc

    return loaded if isinstance(loaded, dict) else {}


def read_simple_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}

    loaded = _load_toml_config(CONFIG_FILE)
    values: dict[str, str] = {}
    for key in ("json_endpoint", "sample_file"):
        value = loaded.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                values[key] = stripped
    return values


def _is_allowed_endpoint_host(hostname: str) -> bool:
    hostname = hostname.rstrip(".").lower()
    if hostname in ALLOWED_ENDPOINT_HOSTS:
        return True
    return any(hostname.endswith(suffix) for suffix in ALLOWED_ENDPOINT_SUFFIXES)


def validate_json_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint.strip())
    if parsed.scheme != "https":
        raise ConfigError("json_endpoint must use https.")
    if not parsed.hostname:
        raise ConfigError("json_endpoint must include a hostname.")
    if parsed.username or parsed.password:
        raise ConfigError("json_endpoint must not include credentials.")
    if parsed.port not in (None, 443):
        raise ConfigError("json_endpoint must use the default https port.")

    hostname = parsed.hostname
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ConfigError("json_endpoint must use an allowed host, not an IP address.")

    if hostname.lower() == "localhost" or not _is_allowed_endpoint_host(hostname):
        raise ConfigError("json_endpoint must stay on chatgpt.com or a subdomain of openai.com.")

    return endpoint.strip()


def _default_settings() -> dict[str, object]:
    return {
        "poll_interval_minutes": DEFAULT_POLL_INTERVAL_MINUTES,
        "display_format": DEFAULT_DISPLAY_FORMAT,
        "show_weekly_limits": DEFAULT_SHOW_WEEKLY_LIMITS,
        "panel_icon": DEFAULT_PANEL_ICON,
    }


def _validate_settings(loaded: dict) -> dict[str, object]:
    settings = _default_settings()

    value = loaded.get("poll_interval_minutes")
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("poll_interval_minutes must be one of 1, 5, 10, or 15.")
        if value not in ALLOWED_POLL_INTERVALS:
            raise ConfigError("poll_interval_minutes must be one of 1, 5, 10, or 15.")
        settings["poll_interval_minutes"] = value

    value = loaded.get("display_format")
    if value is not None:
        if not isinstance(value, str):
            raise ConfigError("display_format must be 'verbose' or 'compact'.")
        normalized = value.strip().lower()
        if normalized not in ALLOWED_DISPLAY_FORMATS:
            raise ConfigError("display_format must be 'verbose' or 'compact'.")
        settings["display_format"] = normalized

    value = loaded.get("show_weekly_limits")
    if value is not None:
        if not isinstance(value, bool):
            raise ConfigError("show_weekly_limits must be a boolean.")
        settings["show_weekly_limits"] = value

    value = loaded.get("panel_icon")
    if value is not None:
        if not isinstance(value, str):
            raise ConfigError("panel_icon must be a supported icon name.")
        normalized = value.strip().lower()
        if normalized not in ALLOWED_PANEL_ICONS:
            raise ConfigError("panel_icon must be a supported icon name.")
        settings["panel_icon"] = normalized

    return settings


def read_settings() -> dict[str, object]:
    if not SETTINGS_FILE.exists():
        return _default_settings()

    loaded = _load_toml_config(SETTINGS_FILE)
    return _validate_settings(loaded)


def write_settings(
    *,
    poll_interval_minutes: int | None = None,
    display_format: str | None = None,
    show_weekly_limits: bool | None = None,
    panel_icon: str | None = None,
) -> dict[str, object]:
    try:
        settings = read_settings()
    except ConfigError:
        settings = _default_settings()

    if poll_interval_minutes is not None:
        if poll_interval_minutes not in ALLOWED_POLL_INTERVALS:
            raise ConfigError("poll_interval_minutes must be one of 1, 5, 10, or 15.")
        settings["poll_interval_minutes"] = poll_interval_minutes

    if display_format is not None:
        normalized = display_format.strip().lower()
        if normalized not in ALLOWED_DISPLAY_FORMATS:
            raise ConfigError("display_format must be 'verbose' or 'compact'.")
        settings["display_format"] = normalized

    if show_weekly_limits is not None:
        settings["show_weekly_limits"] = show_weekly_limits

    if panel_icon is not None:
        normalized = panel_icon.strip().lower()
        if normalized not in ALLOWED_PANEL_ICONS:
            raise ConfigError("panel_icon must be a supported icon name.")
        settings["panel_icon"] = normalized

    ensure_dirs()
    SETTINGS_FILE.write_text(
        "\n".join(
            (
                f'poll_interval_minutes = {settings["poll_interval_minutes"]}',
                f'display_format = {json.dumps(settings["display_format"], ensure_ascii=False)}',
                f'show_weekly_limits = {str(settings["show_weekly_limits"]).lower()}',
                f'panel_icon = {json.dumps(settings["panel_icon"], ensure_ascii=False)}',
                "",
            )
        ),
        encoding="utf-8",
    )
    SETTINGS_FILE.chmod(0o600)
    return settings


def validate_sample_file(path_value: str) -> Path:
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        raise ConfigError("sample_file must be an absolute path inside the samples directory.")

    allowed_root = SAMPLE_DIR.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    if not resolved_candidate.is_relative_to(allowed_root):
        raise ConfigError(f"sample_file must stay inside {allowed_root}.")
    if not candidate.is_file():
        raise ConfigError("sample_file must point to an existing readable file.")

    return candidate
