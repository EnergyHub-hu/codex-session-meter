from __future__ import annotations

from datetime import datetime

from codex_session_widget.parser import parse_datetime


def test_parse_datetime_accepts_codex_epoch_seconds() -> None:
    now = datetime.fromisoformat("2026-06-05T15:45:00+02:00")

    parsed = parse_datetime(1780668894, now=now)

    assert parsed is not None
    assert parsed.timestamp() == 1780668894


def test_parse_datetime_accepts_codex_iso_timestamp() -> None:
    parsed = parse_datetime("2026-06-05T16:14:54Z")

    assert parsed is not None
    assert parsed.timestamp() == datetime.fromisoformat("2026-06-05T16:14:54+00:00").timestamp()
