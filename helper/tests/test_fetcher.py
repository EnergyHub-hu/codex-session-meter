from __future__ import annotations

import logging
import os
import stat
from datetime import datetime, timedelta, timezone

from codex_session_widget import fetcher
from codex_session_widget import config


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


def test_setup_logging_uses_private_rotating_handler(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "widget.log"
    monkeypatch.setattr(config, "LOG_FILE", log_file)

    fetcher.setup_logging()

    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "_codex_session_meter_handler", False)
    ]
    assert len(handlers) == 1
    assert handlers[0].maxBytes == fetcher.LOG_MAX_BYTES
    assert handlers[0].backupCount == fetcher.LOG_BACKUP_COUNT
    assert stat.S_IMODE(log_file.stat().st_mode) == 0o600

    logging.getLogger().removeHandler(handlers[0])
    handlers[0].close()


def test_private_handler_creates_initial_log_with_mode_0600(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "widget.log"
    creation_modes = []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, *, dir_fd=None):
        if flags & os.O_CREAT:
            creation_modes.append(stat.S_IMODE(mode))
        if dir_fd is None:
            return real_open(path, flags, mode)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(fetcher.os, "open", recording_open)
    previous_umask = os.umask(0o002)
    try:
        handler = fetcher._PrivateRotatingFileHandler(log_file, encoding="utf-8")
        handler.close()
    finally:
        os.umask(previous_umask)

    assert creation_modes == [0o600]
    assert stat.S_IMODE(log_file.stat().st_mode) == 0o600


def test_private_handler_creates_rollover_log_with_mode_0600_and_retains_backups(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "widget.log"
    creation_modes = []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, *, dir_fd=None):
        if flags & os.O_CREAT:
            creation_modes.append(stat.S_IMODE(mode))
        if dir_fd is None:
            return real_open(path, flags, mode)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(fetcher.os, "open", recording_open)
    previous_umask = os.umask(0o002)
    try:
        handler = fetcher._PrivateRotatingFileHandler(
            log_file,
            maxBytes=1,
            backupCount=fetcher.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        for _ in range(4):
            handler.emit(logging.LogRecord("test", logging.INFO, __file__, 1, "x", (), None))
        handler.close()
    finally:
        os.umask(previous_umask)

    assert len(creation_modes) >= 2
    assert all(mode == 0o600 for mode in creation_modes)
    assert stat.S_IMODE(log_file.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "widget.log.1").stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "widget.log.2").stat().st_mode) == 0o600
