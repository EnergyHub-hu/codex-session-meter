from __future__ import annotations

import time
from datetime import datetime

import pytest

from codex_session_widget.formatters import build_display, calculate_percent, error_payload, format_remaining_hu, ok_payload, remaining_percent


@pytest.fixture
def budapest_tz(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Budapest")
    time.tzset()
    yield
    time.tzset()


def test_percentage_calculation_for_five_hour_window() -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    reset_at = datetime.fromisoformat("2026-05-22T14:35:00+02:00")

    assert calculate_percent(reset_at, now) == 62


def test_remaining_percent_from_used_percent() -> None:
    assert remaining_percent(60) == 40
    assert remaining_percent(100) == 0


def test_hungarian_remaining_format() -> None:
    assert format_remaining_hu(6840) == "1ó 54p"
    assert format_remaining_hu(59 * 60) == "59p"
    assert format_remaining_hu(30) == "0p"


def test_remaining_format_switches_to_single_tag_under_one_hour() -> None:
    assert format_remaining_hu(3600) == "1ó 0p"
    assert format_remaining_hu(3599) == "59p"


def test_ok_payload_display_shape(budapest_tz) -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    reset_at = datetime.fromisoformat("2026-05-22T14:35:00+02:00")
    weekly_reset_at = datetime.fromisoformat("2026-05-29T16:14:00+02:00")

    payload = ok_payload(reset_at, now, "test_source", weekly_percent=11, weekly_reset_at=weekly_reset_at)

    assert payload["ok"] is True
    assert payload["status"] == "ok"
    assert payload["display"] == "Session 38% / 89% | Reset 14:35 (1ó 54p) / 05.29."
    assert payload["used_percent"] == 62
    assert payload["weekly_percent"] == 89
    assert payload["weekly_reset_date_local"] == "05.29."
    assert payload["remaining_seconds"] == 6840
    assert payload["settings"]["panel_icon"] == "brain"


def test_ok_payload_compact_display_omits_labels(budapest_tz) -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    reset_at = datetime.fromisoformat("2026-05-22T14:35:00+02:00")

    payload = ok_payload(reset_at, now, "test_source", weekly_percent=11, display_format="compact", show_weekly_limits=False)

    assert payload["display"] == "38% | 14:35 (1ó 54p)"


def test_build_display_hides_weekly_limits_when_disabled(budapest_tz) -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    reset_at = datetime.fromisoformat("2026-05-22T14:35:00+02:00")

    assert build_display(62, reset_at, now, weekly_percent=11, weekly_reset_at=reset_at, show_weekly_limits=False) == "Session 38% | Reset 14:35 (1ó 54p)"


def test_error_payload_auth_required_shape() -> None:
    payload = error_payload("auth_required", "Codex: bejelentkezés kell", "Open the page and sign in.")

    assert payload["ok"] is False
    assert payload["status"] == "auth_required"
    assert payload["display"] == "Codex: bejelentkezés kell"
    assert "login_url" in payload
    assert payload["settings"]["display_format"] == "verbose"
    assert payload["source_label"] == "Codex CLI auth"


def test_error_payload_config_error_source_label() -> None:
    payload = error_payload("config_error", "Codex: hibás konfiguráció", "Invalid config.")

    assert payload["source_label"] == "Configuration"
