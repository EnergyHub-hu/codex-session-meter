from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from codex_session_widget import fetcher
from codex_session_widget.config import ConfigError


def test_configured_endpoint_uses_codex_cli_bearer_token(monkeypatch) -> None:
    endpoint = "https://chatgpt.com/backend-api/codex/usage"
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
    reset_at = now + timedelta(hours=2)
    captured: dict[str, object] = {}

    def fake_fetch(endpoint_value: str, headers: dict[str, str]):
        captured["endpoint"] = endpoint_value
        captured["headers"] = headers
        return fetcher.AuthenticatedResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            text=f'{{"reset_at":"{reset_at.isoformat()}","used_percent":60}}',
        )

    monkeypatch.setattr(fetcher.auth, "codex_access_token", lambda: "codex-token")
    monkeypatch.setattr(fetcher.auth, "fetch_json_with_token", fake_fetch)

    payload = fetcher._fetch_configured_json_endpoint(
        endpoint,
        now,
        poll_interval_minutes=1,
        display_format="verbose",
        show_weekly_limits=True,
        panel_icon="brain",
    )

    assert payload["ok"] is True
    assert captured["endpoint"] == endpoint
    assert captured["headers"] == {
        "Accept": "application/json",
        "Authorization": "Bearer codex-token",
        "User-Agent": "codex-session-widget/0.1",
    }


def test_configured_endpoint_requires_codex_cli_token(monkeypatch) -> None:
    endpoint = "https://chatgpt.com/backend-api/codex/usage"
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(fetcher.auth, "codex_access_token", lambda: None)

    try:
        fetcher._fetch_configured_json_endpoint(
            endpoint,
            now,
            poll_interval_minutes=1,
            display_format="verbose",
            show_weekly_limits=True,
            panel_icon="brain",
        )
    except PermissionError as exc:
        assert "codex login" in str(exc)
    else:
        raise AssertionError("expected PermissionError")


def test_configured_endpoint_rejects_redirect_without_following(monkeypatch) -> None:
    endpoint = "https://chatgpt.com/backend-api/codex/usage"
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(fetcher.auth, "codex_access_token", lambda: "codex-token")
    monkeypatch.setattr(
        fetcher.auth,
        "fetch_json_with_token",
        lambda endpoint_value, headers: fetcher.AuthenticatedResponse(
            status_code=302,
            headers={"location": "https://chatgpt.com/redirected"},
            text="",
        ),
    )

    with pytest.raises(ConfigError, match="must not redirect"):
        fetcher._fetch_configured_json_endpoint(
            endpoint,
            now,
            poll_interval_minutes=1,
            display_format="verbose",
            show_weekly_limits=True,
            panel_icon="brain",
        )


def test_configured_endpoint_rejects_oversized_payload(monkeypatch) -> None:
    endpoint = "https://chatgpt.com/backend-api/codex/usage"
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(fetcher, "load_last_success", lambda: None)
    monkeypatch.setattr(fetcher, "save_success", lambda payload: None)
    monkeypatch.setattr(fetcher, "setup_logging", lambda: None)
    monkeypatch.setattr(fetcher, "read_simple_config", lambda: {"json_endpoint": endpoint})
    monkeypatch.setattr(fetcher, "read_settings", lambda: {})
    monkeypatch.setattr(fetcher, "_now", lambda: now)
    monkeypatch.setattr(fetcher.codex_api, "read_rate_limits", lambda: (_ for _ in ()).throw(fetcher.codex_api.CodexApiUnavailable("offline")))
    monkeypatch.setattr(fetcher.auth, "codex_access_token", lambda: "codex-token")
    monkeypatch.setattr(fetcher.auth, "fetch_json_with_token", lambda endpoint_value, headers: (_ for _ in ()).throw(RuntimeError("payload_too_large")))

    payload = fetcher.refresh_status()

    assert payload["ok"] is False
    assert payload["status"] == "parse_error"
    assert payload["message"] == "Could not parse the analytics response."


def test_refresh_status_uses_codex_cli_api_before_configured_sources(monkeypatch, tmp_path) -> None:
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
    reset_at = now + timedelta(hours=2)

    monkeypatch.setattr(fetcher, "load_last_success", lambda: None)
    monkeypatch.setattr(fetcher, "save_success", lambda payload: None)
    monkeypatch.setattr(fetcher, "setup_logging", lambda: None)
    monkeypatch.setattr(fetcher, "read_simple_config", lambda: {"sample_file": str(tmp_path / "unused.json")})
    monkeypatch.setattr(fetcher, "read_settings", lambda: {})
    monkeypatch.setattr(fetcher, "_now", lambda: now)
    monkeypatch.setattr(
        fetcher.codex_api,
        "read_rate_limits",
        lambda: {
            "rateLimits": {
                "primary": {"usedPercent": 60, "windowDurationMins": 300, "resetsAt": int(reset_at.timestamp())},
                "secondary": None,
                "rateLimitReachedType": None,
            }
        },
    )

    payload = fetcher.refresh_status()

    assert payload["ok"] is True
    assert payload["used_percent"] == 60
    assert payload["source_label"] == "Codex CLI API"
