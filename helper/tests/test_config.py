from __future__ import annotations

import pytest

from codex_session_widget import config
from codex_session_widget.config import ConfigError, read_settings, read_simple_config, write_settings, validate_json_endpoint, validate_sample_file


def test_read_simple_config_uses_tomllib(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-widget"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text(
        """
        # comment
        json_endpoint = "https://chatgpt.com/codex/cloud/settings/analytics"
        sample_file = "~/.config/codex-session-widget/samples/analytics_sample.html"
        ignored = 123
        [nested]
        value = "nope"
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "CONFIG_FILE", config_file)

    values = read_simple_config()

    assert values == {
        "json_endpoint": "https://chatgpt.com/codex/cloud/settings/analytics",
        "sample_file": "~/.config/codex-session-widget/samples/analytics_sample.html",
    }


def test_read_simple_config_rejects_invalid_toml(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-widget"
    config_dir.mkdir()
    config_file = config_dir / "config.toml"
    config_file.write_text("json_endpoint = \"https://chatgpt.com/\"\n[broken", encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_FILE", config_file)

    with pytest.raises(ConfigError):
        read_simple_config()


def test_read_settings_defaults_when_missing(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-widget"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    assert read_settings() == {
        "poll_interval_minutes": 1,
        "display_format": "verbose",
        "show_weekly_limits": True,
        "panel_icon": "brain",
    }


def test_write_settings_persists_menu_options(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-widget"
    config_dir.mkdir()
    sample_dir = config_dir / "samples"
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SAMPLE_DIR", sample_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    settings = write_settings(
        poll_interval_minutes=10,
        display_format="compact",
        show_weekly_limits=False,
        panel_icon="robot",
    )

    assert settings == {
        "poll_interval_minutes": 10,
        "display_format": "compact",
        "show_weekly_limits": False,
        "panel_icon": "robot",
    }
    assert settings_file.read_text(encoding="utf-8") == (
        "poll_interval_minutes = 10\n"
        'display_format = "compact"\n'
        "show_weekly_limits = false\n"
        'panel_icon = "robot"\n'
    )


def test_read_settings_rejects_invalid_values(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-widget"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    settings_file.write_text("poll_interval_minutes = 2\n", encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    with pytest.raises(ConfigError):
        read_settings()


def test_read_settings_rejects_invalid_icon_values(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-widget"
    config_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    settings_file.write_text('panel_icon = "lamp"\n', encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    with pytest.raises(ConfigError):
        read_settings()


def test_write_settings_accepts_tech_panel_icons(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-widget"
    config_dir.mkdir()
    sample_dir = config_dir / "samples"
    settings_file = config_dir / "settings.toml"

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SAMPLE_DIR", sample_dir)
    monkeypatch.setattr(config, "SETTINGS_FILE", settings_file)

    settings = write_settings(panel_icon="terminal")

    assert settings["panel_icon"] == "terminal"


@pytest.mark.parametrize(
    ("endpoint",),
    [
        ("http://chatgpt.com/codex/cloud/settings/analytics",),
        ("https://127.0.0.1/codex",),
        ("https://localhost/codex",),
        ("https://example.com/codex",),
        ("https://chatgpt.com:8443/codex",),
        ("https://chatgpt.com@evil.example/codex",),
    ],
)
def test_validate_json_endpoint_rejects_non_whitelisted_values(endpoint: str) -> None:
    with pytest.raises(ConfigError):
        validate_json_endpoint(endpoint)


def test_validate_json_endpoint_allows_whitelisted_hosts() -> None:
    assert validate_json_endpoint("https://chatgpt.com/codex/cloud/settings/analytics") == "https://chatgpt.com/codex/cloud/settings/analytics"
    assert validate_json_endpoint("https://api.openai.com/v1/usage") == "https://api.openai.com/v1/usage"


def test_validate_sample_file_requires_whitelisted_directory(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-widget"
    sample_dir = config_dir / "samples"
    sample_dir.mkdir(parents=True)
    allowed_file = sample_dir / "analytics_sample.html"
    allowed_file.write_text("<html></html>", encoding="utf-8")
    outside_file = tmp_path / "elsewhere.html"
    outside_file.write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SAMPLE_DIR", sample_dir)

    assert validate_sample_file(str(allowed_file)) == allowed_file

    with pytest.raises(ConfigError):
        validate_sample_file(str(outside_file))


def test_validate_sample_file_rejects_relative_path(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "codex-session-widget"
    sample_dir = config_dir / "samples"
    sample_dir.mkdir(parents=True)

    monkeypatch.setattr(config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config, "SAMPLE_DIR", sample_dir)

    with pytest.raises(ConfigError):
        validate_sample_file("relative/sample.html")
