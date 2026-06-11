from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from codex_session_widget import parser
from codex_session_widget.parser import ParseError, parse_analytics_payload


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_reset_time_from_json_fixture() -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    expected = datetime.fromisoformat("2026-05-22T14:35:00+02:00")
    text = (FIXTURES / "analytics_sample.json").read_text(encoding="utf-8")

    reset_at, percent, source = parse_analytics_payload(text, "application/json", now=now)

    assert reset_at.timestamp() == expected.timestamp()
    assert percent == 62
    assert source.endswith("reset_at")


def test_parse_reset_time_from_next_data_html_fixture() -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    expected = datetime.fromisoformat("2026-05-22T14:35:00+02:00")
    text = (FIXTURES / "analytics_sample.html").read_text(encoding="utf-8")

    reset_at, percent, source = parse_analytics_payload(text, "text/html", now=now)

    assert reset_at.timestamp() == expected.timestamp()
    assert percent == 62
    assert source.startswith("__NEXT_DATA__")


def test_parse_visible_reset_time_from_html() -> None:
    now = datetime.fromisoformat("2026-05-22T12:41:00+02:00")
    text = "<html><body>Session resets at 14:35</body></html>"

    reset_at, percent, source = parse_analytics_payload(text, "text/html", now=now)

    assert reset_at.isoformat() == "2026-05-22T14:35:00+02:00"
    assert percent is None
    assert source == "html_visible_reset_time"


def test_parse_rate_limit_json_fixture_shape() -> None:
    now = datetime.fromisoformat("2026-06-05T15:45:00+02:00")
    expected = datetime.fromisoformat("2026-06-05T16:14:54+02:00")
    text = """
    {
      "rate_limit": {
        "primary_window": {
          "used_percent": 60,
          "reset_at": 1780668894
        }
      }
    }
    """

    reset_at, percent, source = parse_analytics_payload(text, "application/json", now=now)

    assert percent == 60
    assert source.endswith("reset_at")
    assert reset_at.timestamp() == expected.timestamp()


def test_parse_rejects_overly_large_payload(monkeypatch) -> None:
    monkeypatch.setattr(parser, "MAX_ANALYTICS_PAYLOAD_CHARS", 8)

    with pytest.raises(ParseError):
        parse_analytics_payload("123456789", "application/json")
