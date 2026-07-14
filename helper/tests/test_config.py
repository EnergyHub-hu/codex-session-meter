from __future__ import annotations

import pytest

from codex_session_widget import config
from codex_session_widget.config import ConfigError, read_settings, write_settings


def test_read_settings_defaults_when_missing(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    assert read_settings() == {
        "poll_interval_minutes": 1,
        "display_format": "verbose",
        "weekly_workdays": 5,
        "panel_icon": "brain",
    }


def test_write_settings_persists_menu_options(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    settings = write_settings(
        poll_interval_minutes=10,
        display_format="compact",
        panel_icon="robot",
    )

    assert settings == {
        "poll_interval_minutes": 10,
        "display_format": "compact",
        "weekly_workdays": 5,
        "panel_icon": "robot",
    }
    assert settings_file.read_text(encoding="utf-8") == (
        "poll_interval_minutes = 10\n"
        'display_format = "compact"\n'
        "weekly_workdays = 5\n"
        'panel_icon = "robot"\n'
    )


def test_read_settings_rejects_invalid_values(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    settings_file.write_text("poll_interval_minutes = 2\n", encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    with pytest.raises(ConfigError):
        read_settings()


def test_read_settings_rejects_invalid_icon_values(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    settings_file.write_text('panel_icon = "lamp"\n', encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    with pytest.raises(ConfigError):
        read_settings()


def test_write_settings_persists_weekly_workdays(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    settings = write_settings(weekly_workdays=4)

    assert settings["weekly_workdays"] == 4
    assert "weekly_workdays = 4" in settings_file.read_text(encoding="utf-8")


def test_read_settings_rejects_invalid_weekly_workdays(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    settings_file.write_text("weekly_workdays = 0\n", encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    with pytest.raises(ConfigError):
        read_settings()


def test_write_settings_accepts_tech_panel_icons(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    settings = write_settings(panel_icon="terminal")

    assert settings["panel_icon"] == "terminal"


def test_write_settings_accepts_no_panel_icon(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    settings = write_settings(panel_icon="none")

    assert settings["panel_icon"] == "none"
