from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib

APP_NAME = "codex-session-meter"
DEFAULT_POLL_INTERVAL_MINUTES = 1
DEFAULT_SHOW_SESSION = True
DEFAULT_SHOW_DAILY = True
DEFAULT_SHOW_WEEKLY = True
DEFAULT_WEEKLY_WORKDAYS = 5
DEFAULT_PANEL_ICON = "brain"
DEFAULT_DISPLAY_MODE = "pace"
ALLOWED_POLL_INTERVALS = (1, 5, 10, 15)
ALLOWED_WEEKLY_WORKDAYS = tuple(range(1, 8))
ALLOWED_PANEL_ICONS = frozenset({"none", "brain", "robot", "chip", "circuit", "atom", "terminal", "fire", "boom", "star", "sparkle"})
ALLOWED_DISPLAY_MODES = frozenset({"pace", "absolute"})
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


def _atomic_write_private_text(path: Path, content: str) -> None:
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _default_settings() -> dict[str, object]:
    return {
        "poll_interval_minutes": DEFAULT_POLL_INTERVAL_MINUTES,
        "show_session": DEFAULT_SHOW_SESSION,
        "show_daily": DEFAULT_SHOW_DAILY,
        "show_weekly": DEFAULT_SHOW_WEEKLY,
        "weekly_workdays": DEFAULT_WEEKLY_WORKDAYS,
        "panel_icon": DEFAULT_PANEL_ICON,
        "display_mode": DEFAULT_DISPLAY_MODE,
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

    for key in ("show_session", "show_daily", "show_weekly"):
        value = loaded.get(key)
        if value is not None:
            if not isinstance(value, bool):
                raise ConfigError(f"{key} must be a boolean.")
            settings[key] = value

    value = loaded.get("weekly_workdays")
    if value is not None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError("weekly_workdays must be an integer from 1 to 7.")
        if value not in ALLOWED_WEEKLY_WORKDAYS:
            raise ConfigError("weekly_workdays must be an integer from 1 to 7.")
        settings["weekly_workdays"] = value

    value = loaded.get("panel_icon")
    if value is not None:
        if not isinstance(value, str):
            raise ConfigError("panel_icon must be a supported icon name.")
        normalized = value.strip().lower()
        if normalized not in ALLOWED_PANEL_ICONS:
            raise ConfigError("panel_icon must be a supported icon name.")
        settings["panel_icon"] = normalized

    value = loaded.get("display_mode")
    if value is not None:
        if not isinstance(value, str):
            raise ConfigError("display_mode must be 'pace' or 'absolute'.")
        normalized = value.strip().lower()
        if normalized not in ALLOWED_DISPLAY_MODES:
            raise ConfigError("display_mode must be 'pace' or 'absolute'.")
        settings["display_mode"] = normalized

    return settings


def read_settings() -> dict[str, object]:
    if not SETTINGS_FILE.exists():
        return _default_settings()

    loaded = _load_toml_config(SETTINGS_FILE)
    return _validate_settings(loaded)


def write_settings(
    *,
    poll_interval_minutes: int | None = None,
    show_session: bool | None = None,
    show_daily: bool | None = None,
    show_weekly: bool | None = None,
    weekly_workdays: int | None = None,
    panel_icon: str | None = None,
    display_mode: str | None = None,
) -> dict[str, object]:
    try:
        settings = read_settings()
    except ConfigError:
        settings = _default_settings()

    if poll_interval_minutes is not None:
        if poll_interval_minutes not in ALLOWED_POLL_INTERVALS:
            raise ConfigError("poll_interval_minutes must be one of 1, 5, 10, or 15.")
        settings["poll_interval_minutes"] = poll_interval_minutes

    for key, value in (
        ("show_session", show_session),
        ("show_daily", show_daily),
        ("show_weekly", show_weekly),
    ):
        if value is not None:
            if not isinstance(value, bool):
                raise ConfigError(f"{key} must be a boolean.")
            settings[key] = value

    if weekly_workdays is not None:
        if weekly_workdays not in ALLOWED_WEEKLY_WORKDAYS:
            raise ConfigError("weekly_workdays must be an integer from 1 to 7.")
        settings["weekly_workdays"] = weekly_workdays

    if panel_icon is not None:
        normalized = panel_icon.strip().lower()
        if normalized not in ALLOWED_PANEL_ICONS:
            raise ConfigError("panel_icon must be a supported icon name.")
        settings["panel_icon"] = normalized

    if display_mode is not None:
        normalized = display_mode.strip().lower()
        if normalized not in ALLOWED_DISPLAY_MODES:
            raise ConfigError("display_mode must be 'pace' or 'absolute'.")
        settings["display_mode"] = normalized

    ensure_dirs()
    _atomic_write_private_text(
        SETTINGS_FILE,
        "\n".join(
            (
                f'poll_interval_minutes = {settings["poll_interval_minutes"]}',
                f'show_session = {json.dumps(settings["show_session"])}',
                f'show_daily = {json.dumps(settings["show_daily"])}',
                f'show_weekly = {json.dumps(settings["show_weekly"])}',
                f'weekly_workdays = {settings["weekly_workdays"]}',
                f'panel_icon = {json.dumps(settings["panel_icon"], ensure_ascii=False)}',
                f'display_mode = {json.dumps(settings["display_mode"], ensure_ascii=False)}',
                "",
            )
        ),
    )
    return settings
