from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any


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
