from __future__ import annotations

import json
from datetime import datetime

from codex_session_widget import codex_api


def test_rate_limits_payload_uses_primary_and_secondary_windows() -> None:
    now = datetime.fromisoformat("2026-06-06T12:00:00+00:00")
    response = {
        "rateLimits": {
            "primary": {
                "usedPercent": 62,
                "windowDurationMins": 300,
                "resetsAt": 1780754400,
            },
            "secondary": {
                "usedPercent": 89,
                "windowDurationMins": 10080,
                "resetsAt": 1780963200,
            },
            "rateLimitReachedType": None,
        },
        "individualLimit": None,
    }

    payload = codex_api.rate_limits_to_payload(
        response,
        now,
        poll_interval_minutes=1,
        display_format="verbose",
        show_weekly_limits=True,
        panel_icon="brain",
    )

    assert payload["ok"] is True
    assert payload["used_percent"] == 62
    assert payload["percent"] == 38
    assert payload["weekly_percent"] == 11
    assert payload["source"] == "codex_app_server:account/rateLimits/read"
    assert payload["source_label"] == "Codex CLI API"


def test_read_rate_limits_sends_initialize_then_rate_limit_request(monkeypatch) -> None:
    writes: list[str] = []
    responses = iter(
        [
            json.dumps({"id": 1, "result": {}}) + "\n",
            json.dumps(
                {
                    "id": 2,
                    "result": {
                        "rateLimits": {
                            "primary": {"usedPercent": 25, "windowDurationMins": 300, "resetsAt": 1780754400},
                            "secondary": None,
                            "rateLimitReachedType": None,
                        }
                    },
                }
            )
            + "\n",
        ]
    )

    class FakeStdin:
        def write(self, value: str) -> None:
            writes.append(value)

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeStdout:
        def readline(self) -> str:
            return next(responses)

    class FakeProcess:
        stdin = FakeStdin()
        stdout = FakeStdout()

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            return 0

    monkeypatch.setattr(codex_api.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    result = codex_api.read_rate_limits()

    assert result["rateLimits"]["primary"]["usedPercent"] == 25
    messages = [json.loads(value) for value in writes]
    assert messages == [
        {"id": 1, "method": "initialize", "params": {"clientName": "codex-session-widget"}},
        {"id": 2, "method": "account/rateLimits/read"},
    ]
