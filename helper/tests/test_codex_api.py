from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime

import pytest

from codex_session_widget import codex_api


def test_rate_limits_payload_uses_primary_as_the_weekly_window() -> None:
    now = datetime.fromisoformat("2026-06-06T12:00:00+00:00")
    response = {
        "rateLimits": {
            "primary": {
                "usedPercent": 62,
                "windowDurationMins": 10080,
                "resetsAt": 1780754400,
            },
            "secondary": None,
            "rateLimitReachedType": None,
        },
        "individualLimit": None,
    }

    payload = codex_api.rate_limits_to_payload(
        response,
        now,
        poll_interval_minutes=1,
        display_format="verbose",
        weekly_workdays=5,
        panel_icon="brain",
    )

    assert payload["ok"] is True
    assert payload["weekly_used_percent"] == 62
    assert payload["weekly_percent"] == 38
    assert datetime.fromisoformat(payload["weekly_reset_at"]).timestamp() == 1780754400
    assert "Session" not in payload["display"]
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
        {
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "codex-session-meter",
                        "title": "Codex Session Meter",
                    "version": "0.3.0",
                }
            },
        },
        {"id": 2, "method": "account/rateLimits/read"},
    ]


def test_read_rate_limits_uses_local_bin_codex_when_path_lookup_fails(monkeypatch) -> None:
    popen_args: list[list[str]] = []
    responses = iter(
        [
            json.dumps({"id": 1, "result": {}}) + "\n",
            json.dumps({"id": 2, "result": {"rateLimits": {"primary": {"usedPercent": 25, "resetsAt": 1780754400}}}}) + "\n",
        ]
    )

    class FakeStdin:
        def write(self, value: str) -> None:
            pass

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

    def fake_popen(args: list[str], *args_: object, **kwargs: object) -> FakeProcess:
        popen_args.append(args)
        return FakeProcess()

    monkeypatch.setenv("HOME", "/home/tester")
    monkeypatch.setenv("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
    monkeypatch.setattr(codex_api.subprocess, "Popen", fake_popen)

    codex_api.read_rate_limits()

    assert popen_args == [["/home/tester/.local/bin/codex", "app-server", "--stdio"]]


def test_read_rate_limits_times_out_when_app_server_hangs(monkeypatch) -> None:
    read_fd, write_fd = os.pipe()
    stdout = os.fdopen(read_fd, "r", encoding="utf-8")

    class FakeStdin:
        def write(self, value: str) -> None:
            pass

        def flush(self) -> None:
            pass

        def close(self) -> None:
            os.close(write_fd)

    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = FakeStdin()
            self.stdout = stdout

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def kill(self) -> None:
            pass

    monkeypatch.setattr(codex_api.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    with pytest.raises(codex_api.CodexApiUnavailable, match="timed out"):
        codex_api.read_rate_limits(timeout_seconds=0.01)

    stdout.close()


def test_read_rate_limits_kills_process_when_terminate_times_out(monkeypatch) -> None:
    responses = iter(
        [
            json.dumps({"id": 1, "result": {}}) + "\n",
            json.dumps({"id": 2, "result": {"rateLimits": {"primary": {"usedPercent": 25, "resetsAt": 1780754400}}}}) + "\n",
        ]
    )
    calls: list[str] = []

    class FakeStdin:
        def write(self, value: str) -> None:
            pass

        def flush(self) -> None:
            pass

        def close(self) -> None:
            calls.append("close")

    class FakeStdout:
        def readline(self) -> str:
            return next(responses)

    class FakeProcess:
        stdin = FakeStdin()
        stdout = FakeStdout()

        def terminate(self) -> None:
            calls.append("terminate")

        def wait(self, timeout: float | None = None) -> int:
            calls.append("wait")
            if "kill" not in calls:
                raise subprocess.TimeoutExpired("codex", timeout)
            return 0

        def kill(self) -> None:
            calls.append("kill")

    monkeypatch.setattr(codex_api.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    codex_api.read_rate_limits()

    assert calls == ["close", "terminate", "wait", "kill", "wait"]


def test_read_rate_limits_rejects_invalid_json_without_leaking_payload(monkeypatch) -> None:
    payload = "partial-secret-access_token-payload"

    class FakeStdin:
        def write(self, value: str) -> None:
            pass

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeStdout:
        def readline(self) -> str:
            return payload + "\n"

    class FakeProcess:
        stdin = FakeStdin()
        stdout = FakeStdout()

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def kill(self) -> None:
            pass

    monkeypatch.setattr(codex_api.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    with pytest.raises(codex_api.CodexApiUnavailable) as exc_info:
        codex_api.read_rate_limits()

    assert "invalid JSON" in str(exc_info.value)
    assert payload not in str(exc_info.value)
