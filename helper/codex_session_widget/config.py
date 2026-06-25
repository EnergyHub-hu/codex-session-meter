from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib

APP_NAME = "codex-session-meter"
SESSION_SECONDS = 5 * 60 * 60
DEFAULT_POLL_INTERVAL_MINUTES = 1
DEFAULT_DISPLAY_FORMAT = "verbose"
DEFAULT_SHOW_WEEKLY_LIMITS = True
DEFAULT_PANEL_ICON = "brain"
ALLOWED_POLL_INTERVALS = (1, 5, 10, 15)
ALLOWED_DISPLAY_FORMATS = frozenset({"verbose", "compact"})
ALLOWED_PANEL_ICONS = frozenset({"brain", "robot", "chip", "circuit", "atom", "terminal", "fire", "boom", "star", "sparkle"})
class ConfigError(ValueError):
    pass


def _xdg_path(env_name: str, default: str) -> Path:
    return Path(os.environ.get(env_name, default)).expanduser()


CONFIG_DIR = _xdg_path("XDG_CONFIG_HOME", "~/.config") / APP_NAME
CACHE_DIR = _xdg_path("XDG_CACHE_HOME", "~/.cache") / APP_NAME
DATA_DIR = _xdg_path("XDG_DATA_HOME", "~/.local/share") / APP_NAME
SETTINGS_FILE = CONFIG_DIR / "settings.toml"

STATE_FILE = CACHE_DIR / "state.json"
LOG_FILE = CACHE_DIR / "widget.log"
CODEX_AUTH_FILE = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "auth.json"


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in (CONFIG_DIR, CACHE_DIR, DATA_DIR):
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
