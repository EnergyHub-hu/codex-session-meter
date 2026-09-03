from __future__ import annotations

import os
import stat
from pathlib import Path

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
        "show_session": True,
        "show_daily": True,
        "show_weekly": True,
        "weekly_workdays": 5,
        "panel_icon": "brain",
        "display_mode": "pace",
    }


def test_write_settings_persists_menu_options(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    settings = write_settings(
        poll_interval_minutes=10,
        panel_icon="robot",
    )

    assert settings == {
        "poll_interval_minutes": 10,
        "show_session": True,
        "show_daily": True,
        "show_weekly": True,
        "weekly_workdays": 5,
        "panel_icon": "robot",
        "display_mode": "pace",
    }
    assert settings_file.read_text(encoding="utf-8") == (
        "poll_interval_minutes = 10\n"
        "show_session = true\n"
        "show_daily = true\n"
        "show_weekly = true\n"
        "weekly_workdays = 5\n"
        'panel_icon = "robot"\n'
        'display_mode = "pace"\n'
    )


def test_write_settings_atomically_creates_private_complete_file_under_permissive_umask(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    creation_observations = []
    replacement_observations = []
    real_mkstemp = config.tempfile.mkstemp
    real_replace = config.os.replace

    def recording_mkstemp(*args, **kwargs):
        file_descriptor, temporary_name = real_mkstemp(*args, **kwargs)
        temporary_file = Path(temporary_name)
        creation_observations.append(
            (temporary_file.parent, stat.S_IMODE(temporary_file.stat().st_mode))
        )
        return file_descriptor, temporary_name

    def recording_replace(source, destination):
        temporary_file = config_dir / source.name
        replacement_observations.append(
            (
                temporary_file.parent,
                stat.S_IMODE(temporary_file.stat().st_mode),
                temporary_file.read_text(encoding="utf-8"),
            )
        )
        real_replace(source, destination)

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(config.tempfile, "mkstemp", recording_mkstemp)
    monkeypatch.setattr(config.os, "replace", recording_replace)

    previous_umask = os.umask(0)
    try:
        write_settings(poll_interval_minutes=10, panel_icon="robot")
    finally:
        os.umask(previous_umask)

    assert creation_observations == [(config_dir, 0o600)]
    assert replacement_observations == [
        (
            config_dir,
            0o600,
            settings_file.read_text(encoding="utf-8"),
        )
    ]
    assert stat.S_IMODE(settings_file.stat().st_mode) == 0o600
    assert list(config_dir.iterdir()) == [settings_file]


def test_write_settings_replaces_existing_complete_file(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    settings_file.write_text('panel_icon = "brain"\n', encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    write_settings(panel_icon="robot")

    assert read_settings()["panel_icon"] == "robot"
    assert stat.S_IMODE(settings_file.stat().st_mode) == 0o600
    assert list(config_dir.iterdir()) == [settings_file]


def test_write_settings_failure_before_replace_preserves_destination_and_cleans_temp(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    old_content = 'panel_icon = "brain"\n'
    settings_file.write_text(old_content, encoding="utf-8")

    def failing_replace(source, destination):
        assert source.parent == config_dir
        assert stat.S_IMODE(source.stat().st_mode) == 0o600
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(config.os, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated replacement failure"):
        write_settings(panel_icon="robot")

    assert settings_file.read_text(encoding="utf-8") == old_content
    assert list(config_dir.iterdir()) == [settings_file]


def test_write_settings_persists_visibility_flags(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    settings = write_settings(show_session=False, show_weekly=False)

    assert settings["show_session"] is False
    assert settings["show_daily"] is True
    assert settings["show_weekly"] is False
    content = settings_file.read_text(encoding="utf-8")
    assert "show_session = false" in content
    assert "show_daily = true" in content
    assert "show_weekly = false" in content


def test_read_settings_rejects_invalid_visibility_values(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-meter"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    settings_file.write_text("show_daily = 1\n", encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    with pytest.raises(ConfigError):
        read_settings()


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
