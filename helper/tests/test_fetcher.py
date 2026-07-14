from __future__ import annotations

from datetime import datetime, timedelta, timezone

from codex_session_widget import fetcher


def test_refresh_status_uses_codex_cli_api(monkeypatch) -> None:
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
    reset_at = now + timedelta(days=7)

    monkeypatch.setattr(fetcher, "load_last_success", lambda: None)
    monkeypatch.setattr(fetcher, "save_success", lambda payload: None)
    monkeypatch.setattr(fetcher, "setup_logging", lambda: None)
    monkeypatch.setattr(fetcher, "read_settings", lambda: {})
    monkeypatch.setattr(fetcher, "_now", lambda: now)
    monkeypatch.setattr(
        fetcher.codex_api,
        "read_rate_limits",
        lambda: {
            "rateLimits": {
                "primary": {"usedPercent": 60, "windowDurationMins": 10080, "resetsAt": int(reset_at.timestamp())},
                "secondary": None,
                "rateLimitReachedType": None,
            }
        },
    )

    payload = fetcher.refresh_status()

    assert payload["ok"] is True
    assert payload["weekly_used_percent"] == 60
    assert payload["source_label"] == "Codex CLI API"


def test_refresh_status_requires_auth_when_codex_cli_api_fails_without_token(monkeypatch) -> None:
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(fetcher, "load_last_success", lambda: None)
    monkeypatch.setattr(fetcher, "setup_logging", lambda: None)
    monkeypatch.setattr(fetcher, "read_settings", lambda: {})
    monkeypatch.setattr(fetcher, "_now", lambda: now)
    monkeypatch.setattr(fetcher.codex_api, "read_rate_limits", lambda: (_ for _ in ()).throw(fetcher.codex_api.CodexApiUnavailable("offline")))
    monkeypatch.setattr(fetcher.auth, "codex_auth_summary", lambda: {"has_access_token": False})

    payload = fetcher.refresh_status()

    assert payload["ok"] is False
    assert payload["status"] == "auth_required"


def test_refresh_status_has_no_configured_source_after_codex_cli_failure(monkeypatch) -> None:
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(fetcher, "load_last_success", lambda: None)
    monkeypatch.setattr(fetcher, "setup_logging", lambda: None)
    monkeypatch.setattr(fetcher, "read_settings", lambda: {})
    monkeypatch.setattr(fetcher, "_now", lambda: now)
    monkeypatch.setattr(fetcher.codex_api, "read_rate_limits", lambda: (_ for _ in ()).throw(fetcher.codex_api.CodexApiUnavailable("offline")))
    monkeypatch.setattr(fetcher.auth, "codex_auth_summary", lambda: {"has_access_token": True})

    payload = fetcher.refresh_status()

    assert payload["ok"] is False
    assert payload["status"] == "parse_error"
    assert payload["message"] == "Codex CLI API did not return rate limit data."
