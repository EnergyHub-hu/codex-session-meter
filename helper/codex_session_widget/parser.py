from __future__ import annotations

import html
import json
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

MAX_ANALYTICS_PAYLOAD_CHARS = 2_000_000

RESET_KEY_RE = re.compile(
    r"(?i)(reset(?:s|At|_at|Time|_time|Timestamp|_timestamp)|window(?:Reset|_reset)|next(?:Reset|_reset)|resetsAt)"
)
ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})")
TIME_RE = re.compile(r"(?i)(?:reset(?:s)?|visszaáll|újraindul)[^\d]{0,40}(\d{1,2}:\d{2})")
PERCENT_KEY_RE = re.compile(r"(?i)(percent|percentage|usagePct|usage_percent|used_percent)")


class ParseError(ValueError):
    pass


def _ensure_payload_size(text: str) -> None:
    if len(text) > MAX_ANALYTICS_PAYLOAD_CHARS:
        raise ParseError("Analytics payload is too large to parse safely")


def parse_datetime(value: Any, now: datetime | None = None) -> datetime | None:
    if value is None:
        return None
    if now is None:
        now = datetime.now().astimezone()

    if isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number = number / 1000
        if number > 1_000_000_000:
            return datetime.fromtimestamp(number, tz=timezone.utc).astimezone()
        if 0 < number <= 24 * 60 * 60:
            return now + timedelta(seconds=number)
        return None

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return parse_datetime(int(text), now=now)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone()
    except ValueError:
        pass
    if re.fullmatch(r"\d{1,2}:\d{2}", text):
        hour, minute = [int(part) for part in text.split(":", 1)]
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate
    return None


def find_reset_in_json(data: Any, now: datetime | None = None) -> tuple[datetime, int | None, str]:
    percent: int | None = None
    queue: deque[tuple[Any, str]] = deque([(data, "$")])

    while queue:
        node, path = queue.popleft()
        if isinstance(node, dict):
            for key, value in node.items():
                key_path = f"{path}.{key}"
                if percent is None and PERCENT_KEY_RE.fullmatch(str(key)):
                    try:
                        percent = int(round(float(value)))
                    except (TypeError, ValueError):
                        pass
                if RESET_KEY_RE.search(str(key)):
                    parsed = parse_datetime(value, now=now)
                    if parsed:
                        return parsed, percent, key_path
                if isinstance(value, (dict, list)):
                    queue.append((value, key_path))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                if isinstance(value, (dict, list)):
                    queue.append((value, f"{path}[{index}]"))

    raise ParseError("No reset timestamp field found in JSON data")


def parse_json_text(text: str, now: datetime | None = None) -> tuple[datetime, int | None, str]:
    _ensure_payload_size(text)
    data = json.loads(text)
    return find_reset_in_json(data, now=now)


def _extract_next_data(text: str) -> list[str]:
    matches = re.findall(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return [html.unescape(match) for match in matches]


def parse_html_text(text: str, now: datetime | None = None) -> tuple[datetime, int | None, str]:
    _ensure_payload_size(text)
    for script_json in _extract_next_data(text):
        try:
            reset_at, percent, path = parse_json_text(script_json, now=now)
            return reset_at, percent, f"__NEXT_DATA__:{path}"
        except (json.JSONDecodeError, ParseError):
            continue

    for match in ISO_RE.finditer(text):
        parsed = parse_datetime(match.group(0), now=now)
        if parsed:
            return parsed, None, "html_iso_timestamp"

    visible = re.sub(r"<[^>]+>", " ", text)
    visible = html.unescape(re.sub(r"\s+", " ", visible))
    match = TIME_RE.search(visible)
    if match:
        parsed = parse_datetime(match.group(1), now=now)
        if parsed:
            return parsed, None, "html_visible_reset_time"

    raise ParseError("No reset timestamp found in HTML")


def parse_analytics_payload(text: str, content_type: str = "", now: datetime | None = None) -> tuple[datetime, int | None, str]:
    _ensure_payload_size(text)
    stripped = text.lstrip()
    if "json" in content_type.lower() or stripped.startswith(("{", "[")):
        return parse_json_text(text, now=now)
    return parse_html_text(text, now=now)
