from __future__ import annotations

import time
from datetime import datetime

import pytest

from codex_session_widget.formatters import build_display, error_payload, format_remaining_hu, ok_payload, remaining_percent


@pytest.fixture
def budapest_tz(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Budapest")
    time.tzset()
    yield
    time.tzset()


def test_remaining_percent_from_used_percent() -> None:
    assert remaining_percent(60) == 40
    assert remaining_percent(100) == 0


def test_hungarian_remaining_format() -> None:
    assert format_remaining_hu(6840) == "1ó 54p"
    assert format_remaining_hu(617580) == "7n 3ó 33p"
    assert format_remaining_hu(59 * 60) == "59p"
    assert format_remaining_hu(30) == "0p"


def test_remaining_format_switches_to_single_tag_under_one_hour() -> None:
    assert format_remaining_hu(3600) == "1ó 0p"
    assert format_remaining_hu(3599) == "59p"


def test_ok_payload_display_shape(budapest_tz) -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    weekly_reset_at = datetime.fromisoformat("2026-05-29T16:14:00+02:00")

    payload = ok_payload(weekly_reset_at, now, "test_source", weekly_used_percent=11)

    assert payload["ok"] is True
    assert payload["status"] == "ok"
    assert payload["display"] == "89% | 05.29."
    assert payload["weekly_used_percent"] == 11
    assert payload["weekly_percent"] == 89
    assert payload["weekly_reset_date_local"] == "05.29."
    assert payload["remaining_seconds"] == 617580
    assert payload["settings"]["panel_icon"] == "brain"
    assert payload["settings"]["show_session"] is True


def test_build_display_shows_the_weekly_quota(budapest_tz) -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    weekly_reset_at = datetime.fromisoformat("2026-05-29T16:14:00+02:00")

    assert build_display(11, weekly_reset_at, now) == "89% | 05.29."


def test_ok_payload_includes_session_window_when_present(budapest_tz) -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    weekly_reset_at = datetime.fromisoformat("2026-05-29T16:14:00+02:00")
    session_reset_at = datetime.fromisoformat("2026-05-22T16:41:00+02:00")

    payload = ok_payload(
        weekly_reset_at,
        now,
        "test_source",
        weekly_used_percent=11,
        session_used_percent=80,
        session_reset_at=session_reset_at,
    )

    assert payload["session_used_percent"] == 80
    assert payload["session_percent"] == 20
    assert payload["session_reset_at"] == "2026-05-22T16:41:00+02:00"
    assert payload["session_reset_time_local"] == "16:41"
    assert payload["session_remaining_seconds"] == 4 * 3600
    assert payload["session_remaining_human_hu"] == "4ó 0p"


def test_ok_payload_omits_session_fields_without_session_window(budapest_tz) -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    weekly_reset_at = datetime.fromisoformat("2026-05-29T16:14:00+02:00")

    payload = ok_payload(weekly_reset_at, now, "test_source", weekly_used_percent=11)

    assert payload["session_percent"] is None
    assert payload["session_used_percent"] is None
    assert payload["session_reset_at"] is None
    assert payload["session_reset_time_local"] is None
    assert payload["session_remaining_seconds"] is None
    assert payload["session_remaining_human_hu"] is None


def test_error_payload_auth_required_shape() -> None:
    payload = error_payload("auth_required", "Codex: bejelentkezés kell", "Open the page and sign in.")

    assert payload["ok"] is False
    assert payload["status"] == "auth_required"
    assert payload["display"] == "Codex: bejelentkezés kell"
    assert "login_url" not in payload
    assert payload["settings"]["show_weekly"] is True
    assert payload["source_label"] == "Codex CLI auth"


def test_error_payload_config_error_source_label() -> None:
    payload = error_payload("config_error", "Codex: hibás konfiguráció", "Invalid config.")

    assert payload["source_label"] == "Configuration"
