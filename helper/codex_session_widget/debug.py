from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEBUG_INTERVAL_SECONDS = 60

# ---------------------------------------------------------------------------
# ANSI / terminal helpers (B terv)
# ---------------------------------------------------------------------------

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_ITALIC = "\033[3m"
ANSI_REV = "\033[7m"
ANSI_CYAN = "\033[36m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED = "\033[31m"
ANSI_MAGENTA = "\033[35m"
ANSI_BLUE = "\033[34m"
ANSI_GRAY = "\033[90m"
ANSI_WHITE = "\033[97m"

def _term_width(fallback: int = 100, explicit: int | None = None) -> int:
    if explicit is not None:
        try:
            return max(60, min(160, int(explicit)))
        except Exception:
            pass
    # First try actual terminal size (most reliable in zsh/gnome-terminal)
    try:
        w = shutil.get_terminal_size((fallback, 24)).columns
        # If we got a real tty size (not fallback), use it even if COLUMNS is stale
        # Detect fallback by checking if env COLUMNS differs hugely? Instead prefer tty size
        # when stdout is a tty.
        if sys.stdout.isatty() and w != fallback:
            return max(60, min(160, int(w)))
    except Exception:
        pass
    # COLUMNS env: fallback for non-tty / piping / tests
    cols_env = os.environ.get("COLUMNS")
    if cols_env is not None:
        try:
            return max(60, min(160, int(cols_env)))
        except Exception:
            pass
    try:
        w = shutil.get_terminal_size((fallback, 24)).columns
    except Exception:
        w = fallback
    # clamp to avoid extreme values
    return max(60, min(160, int(w)))

def _supports_color(no_color_flag: bool = False) -> bool:
    if no_color_flag:
        return False
    # NO_COLOR spec: https://no-color.org/
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR") is not None:
        return True
    # Only emit colors when stdout is a tty
    try:
        return sys.stdout.isatty()
    except Exception:
        return False

def _c(text: str, *codes: str, use_color: bool = False) -> str:
    if not use_color or not codes or not text:
        return text
    return f"{''.join(codes)}{text}{ANSI_RESET}"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)

def _visible_len(s: str) -> int:
    return len(_strip_ansi(s))

def _hr(width: int, char: str = "─", use_color: bool = False) -> str:
    # width is visible width
    line = char * max(1, width)
    return _c(line, ANSI_DIM, use_color=use_color)

def _wrap_text(text: str, width: int, initial_indent: str = "", subsequent_indent: str = "") -> list[str]:
    """Wrap plain text to width, preserving indent. Returns list of lines."""
    if _visible_len(text) <= width:
        return [text]
    # textwrap counts raw len, but we pass plain text without ANSI so ok
    wrapped = textwrap.wrap(
        text,
        width=width,
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped if wrapped else [text]

def _emit(lines: list[str], text: str, width: int, use_color: bool = False, style: str | None = None, wrap: bool = True, subsequent_indent: str = "") -> None:
    """Append (possibly wrapped) text to lines, with optional color."""
    # Apply style after wrapping to avoid ANSI length issues: wrap plain then color each chunk
    plain = text
    if wrap and len(plain) > width:
        chunks = _wrap_text(plain, width, subsequent_indent=subsequent_indent)
        for ch in chunks:
            if style and use_color:
                lines.append(_c(ch, style, use_color=use_color))
            else:
                lines.append(ch)
    else:
        if style and use_color:
            lines.append(_c(text, style, use_color=use_color))
        else:
            lines.append(text)

def _kv(label: str, value: str, width: int, use_color: bool = False, label_width: int = 18) -> str:
    """Format 'label: value' with adaptive spacing, truncated/wrapped if needed."""
    # label is padded to label_width unless narrow
    if width < 80:
        # narrow: stack label and value
        return f"{label}: {value}"
    # normal: pad label
    padded = f"{label + ':':<{label_width}}"
    line = f"{padded} {value}"
    if len(line) > width:
        # wrap value on next line indented
        first = f"{padded} {value}"
        if len(first) <= width:
            return first
        # split value
        indent = " " * (label_width + 1)
        wrapped = _wrap_text(value, width - label_width - 1)
        if not wrapped:
            return f"{padded} {value}"
        out = f"{padded} {wrapped[0]}"
        # caller should handle multi-line; for simplicity return first + continuation handled by _emit
        # So we return single line and let _emit wrap; we just return first line here
        return out
    return line

# ---------------------------------------------------------------------------
# Node trace helpers
# ---------------------------------------------------------------------------

def _extension_dir() -> Path:
    # helper/codex_session_widget/debug.py -> repo root -> extension/
    return Path(__file__).resolve().parents[2] / "extension"

def _debug_calc_script() -> Path:
    return _extension_dir() / "debug-calc.js"

def _decode_trace_json(text: str) -> dict:
    def _hook(obj: Any) -> Any:
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if v == "__INFINITY__":
                    obj[k] = math.inf
                elif v == "__NEG_INFINITY__":
                    obj[k] = -math.inf
                elif v == "__NAN__":
                    obj[k] = float("nan")
        return obj
    return json.loads(text, object_hook=_hook)

def get_trace(payload: dict) -> dict:
    script = _debug_calc_script()
    node = shutil.which("node") or shutil.which("nodejs") or "node"
    inp = json.dumps(payload, ensure_ascii=False)
    try:
        proc = subprocess.run(
            [node, str(script)],
            input=inp.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except FileNotFoundError:
        return {"_error": "node not found", "payload": payload}
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")[:500]
        return {"_error": f"debug-calc failed: {stderr}", "payload": payload}
    try:
        return _decode_trace_json(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return {"_error": f"invalid trace JSON: {exc}", "payload": payload}

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_percent(v: Any, decimals: int = 2) -> str:
    if v is None or (isinstance(v, float) and (math.isinf(v) or math.isnan(v))):
        if v is math.inf:
            return "∞"
        if v == -math.inf:
            return "-∞"
        if isinstance(v, float) and math.isnan(v):
            return "NaN"
        return "n/a"
    if not isinstance(v, (int, float)):
        return "n/a"
    return f"{v:.{decimals}f} %"

def _fmt_number(v: Any, decimals: int = 4) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float) and math.isinf(v):
        return "∞" if v > 0 else "-∞"
    if isinstance(v, float) and math.isnan(v):
        return "NaN"
    if not isinstance(v, (int, float)):
        return "n/a"
    if isinstance(v, int):
        return str(v)
    return f"{v:.{decimals}f}"

def _fmt_millis(ms: Any) -> str:
    if ms is None or not isinstance(ms, (int, float)):
        return "n/a"
    if math.isnan(ms) or math.isinf(ms):
        return "n/a"
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone()
        return f"{dt.isoformat(timespec='seconds')}  (epoch: {int(ms)} ms)"
    except Exception:
        return str(ms)

def _fmt_millis_compact(ms: Any, width: int) -> list[str]:
    """Return 1 or 2 lines for millis depending on width."""
    if ms is None or not isinstance(ms, (int, float)) or (isinstance(ms, float) and (math.isnan(ms) or math.isinf(ms))):
        return ["n/a"]
    try:
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone()
        iso = dt.isoformat(timespec="seconds")
        epoch = f"epoch: {int(ms)} ms"
        full = f"{iso}  ({epoch})"
        if len(full) <= width - 2:
            return [full]
        # narrow: split
        return [iso, f"  ({epoch})"]
    except Exception:
        return [str(ms)]

def _fmt_iso_short(iso: Any) -> str:
    if not iso:
        return "n/a"
    return str(iso)

def _fmt_bool(v: Any) -> str:
    if v is None:
        return "n/a"
    return str(v)

def _fmt_color(c: Any) -> str:
    if c is None:
        return "nincs (null)"
    return str(c)

def _safe(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float) and math.isinf(v):
        return "∞"
    if isinstance(v, float) and math.isnan(v):
        return "NaN"
    return str(v)

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_header(payload: dict, trace: dict, refresh_time: datetime, reason: str, next_time: datetime, width: int | None = None, use_color: bool | None = None) -> str:
    if width is None:
        width = _term_width()
    if use_color is None:
        use_color = _supports_color()
    lines: list[str] = []
    title = "Codex Session Meter — Calculation Debug"
    lines.append(_c(title, ANSI_BOLD, ANSI_CYAN, use_color=use_color))
    lines.append(_c("═" * min(len(title), width), ANSI_DIM, ANSI_CYAN, use_color=use_color))
    lines.append("")
    # Determine data status
    ok = payload.get("ok")
    has_last = payload.get("last_success") is not None or (trace.get("_meta", {}).get("hasLastSuccess"))
    is_stale = trace.get("_meta", {}).get("isStale") or (not ok and has_last)
    source_label = trace.get("_meta", {}).get("sourceLabel") or payload.get("source_label") or "n/a"
    status = payload.get("status") or trace.get("_meta", {}).get("status") or "unknown"

    if ok:
        data_status = "LIVE"
        data_status_colored = _c(data_status, ANSI_BOLD, ANSI_GREEN, use_color=use_color)
    elif is_stale:
        data_status = "CACHED / STALE — Live refresh: FAILED"
        data_status_colored = _c(data_status, ANSI_BOLD, ANSI_YELLOW, use_color=use_color)
    else:
        data_status = f"CACHED / STALE — {status}"
        data_status_colored = _c(data_status, ANSI_YELLOW, use_color=use_color)

    # Use adaptive layout: narrow -> stacked, wide -> padded
    def kv_line(label: str, value: str, value_colored: str | None = None) -> None:
        plain = f"{label}: {value}"
        colored = f"{label}: {value_colored if value_colored is not None else value}"
        # For narrow, just emit plain with color
        if width < 78:
            # label bold dim
            label_c = _c(label + ":", ANSI_DIM, ANSI_BOLD, use_color=use_color)
            val = value_colored if value_colored is not None else value
            line = f"{label_c} {val}"
            # wrap if needed
            if _visible_len(_strip_ansi(line)) > width:
                # fallback to wrapped plain lines
                for w in _wrap_text(plain, width):
                    # re-apply color on first?
                    lines.append(w)
            else:
                lines.append(line)
            return
        # wide: padded label
        label_padded = f"{label + ':':<16}"
        label_c = _c(label_padded, ANSI_DIM, use_color=use_color)
        val = value_colored if value_colored is not None else value
        line_plain = f"{label_padded} {value}"
        line_colored = f"{label_c} {val}"
        if len(line_plain) > width:
            for w in _wrap_text(line_plain, width, subsequent_indent=" " * 16):
                lines.append(w)
        else:
            lines.append(line_colored)

    kv_line("Frissítés", refresh_time.isoformat(timespec="seconds"))
    kv_line("Frissítés oka", reason)
    kv_line("Következő", f"{next_time.strftime('%H:%M:%S')}  (60 s)")
    kv_line("Adatforrás", source_label)
    kv_line("Állapot", f"{data_status}  (status: {status})", value_colored=f"{data_status_colored}  {_c(f'(status: {status})', ANSI_DIM, use_color=use_color)}")
    if not ok:
        msg = payload.get("message") or ""
        if msg:
            # wrap message
            for w in _wrap_text(f"Üzenet: {msg[:200]}", width, subsequent_indent="  "):
                if w.startswith("Üzenet:"):
                    lines.append(_c("Üzenet:", ANSI_DIM, use_color=use_color) + w[len("Üzenet:"):])
                else:
                    lines.append(w)
        ls = payload.get("last_success") or {}
        cached_ts = ls.get("last_updated") or (trace.get("payload", {}).get("last_success", {}) or {}).get("last_updated")
        if cached_ts:
            kv_line("Cached időpont", str(cached_ts))
        if trace.get("_error"):
            for w in _wrap_text(f"Hiba: {trace['_error'][:200]}", width, subsequent_indent="  "):
                if w.startswith("Hiba:"):
                    lines.append(_c("Hiba:", ANSI_RED, use_color=use_color) + w[len("Hiba:"):])
                else:
                    lines.append(w)
    lines.append("")
    # Beállítások box
    lines.append(_c("Beállítások", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(28, width), "─", use_color=use_color))
    ww = trace.get("_meta", {}).get("weeklyWorkdays", "n/a")
    # show pill for workdays
    ww_str = str(ww) if ww != "n/a" else _c("n/a", ANSI_DIM, use_color=use_color)
    kv_line("Heti munkanapok", ww_str)
    kv_line("Debug frissítés", f"{DEBUG_INTERVAL_SECONDS} s")
    # Terminál diagnosztika – segít zsh-ben ha szétesik
    term_src = ""
    if os.environ.get("COLUMNS"):
        try:
            if int(os.environ["COLUMNS"]) == width:
                term_src = " (COLUMNS)"
        except Exception:
            pass
    kv_line("Terminál", f"{width} oszlop{term_src}" + (f"  {_c('✓', ANSI_GREEN, use_color=use_color)}" if 78 <= width <= 120 else ""))
    kv_line("Színek", "be" if use_color else "ki  (NO_COLOR=1 tiltja)")
    lines.append("")
    # Help line with reverse – wrap for narrow zsh windows
    help_plain = "[R] frissítés most    [Q] kilépés"
    if use_color:
        base = f"{_c('[R]', ANSI_REV, ANSI_BOLD, use_color=use_color)} frissítés most    {_c('[Q]', ANSI_REV, ANSI_BOLD, use_color=use_color)} kilépés"
        hint = _c("│  tipp: --width 80 / COLUMNS=80 igazítja", ANSI_DIM, use_color=use_color)
        hint_plain = "│  tipp: --width 80 / COLUMNS=80 igazítja"
        full_plain = f"{help_plain}  {hint_plain}"
        if len(full_plain) > width:
            lines.append(base)
            # indent hint
            for w in _wrap_text(hint_plain, width, subsequent_indent="   "):
                if w.startswith("│"):
                    lines.append(_c(w, ANSI_DIM, use_color=use_color))
                else:
                    lines.append(_c(w, ANSI_DIM, use_color=use_color))
        else:
            lines.append(f"{base}  {hint}")
    else:
        if len(help_plain + "  │  tipp: --width 80 / COLUMNS=80 igazítja") > width:
            lines.append(help_plain)
            for w in _wrap_text("│  tipp: --width 80 / COLUMNS=80 igazítja", width, subsequent_indent="   "):
                lines.append(w)
        else:
            lines.append(f"{help_plain}  │  tipp: --width 80 / COLUMNS=80 igazítja")
    lines.append("")
    return "\n".join(lines)


def _render_session(trace: dict, width: int | None = None, use_color: bool | None = None) -> str:
    if width is None:
        width = _term_width()
    if use_color is None:
        use_color = _supports_color()
    s = trace.get("session", {})
    inp = s.get("input", {})
    pace = s.get("pace", {})
    pt = pace.get("trace") or {}
    remaining = s.get("remaining", {})
    pcolor = s.get("paceColor", {})
    level = s.get("indicatorLevel", {})

    session_percent = inp.get("sessionPercent")
    session_used = inp.get("sessionUsedPercent")
    session_reset_at = inp.get("sessionResetAt")
    session_window_mins = inp.get("sessionWindowMins")
    last_updated = inp.get("lastUpdated")

    lines: list[str] = []
    lines.append(_c("1. 5 ÓRÁS SESSION", ANSI_BOLD, ANSI_WHITE, use_color=use_color))
    lines.append(_c("═" * min(18, width), ANSI_DIM, use_color=use_color))
    lines.append("")
    lines.append(_c("INPUT", ANSI_BOLD, ANSI_CYAN, use_color=use_color))
    lines.append(_hr(min(24, width), "─", use_color=use_color))
    # Show both used and remaining if available
    if session_used is not None:
        _emit(lines, f"Codex session usedPercent (helper, kerekített, clampelt): {_fmt_percent(session_used, 2)}", width)
        _emit(lines, f"  → remaining (100 - used) = {_fmt_percent(session_percent, 2) if session_percent is not None else 'n/a'}", width, subsequent_indent="    ")
    else:
        # nicer empty state
        _emit(lines, f"Codex session usedPercent: {_c('n/a', ANSI_DIM, use_color=use_color)}", width)
        _emit(lines, f"Session remaining (payload session_percent): {_fmt_percent(session_percent, 2)}", width)
    # Session window + reset
    win_str = f"{_safe(session_window_mins)} min" + (f"  ({session_window_mins * 60} s)" if isinstance(session_window_mins, (int, float)) else "")
    _emit(lines, f"Session window: {win_str}", width)
    _emit(lines, f"Reset timestamp (session_reset_at): {_fmt_iso_short(session_reset_at)}", width)
    if pt.get("resetAtMillis") is not None:
        for part in _fmt_millis_compact(pt.get('resetAtMillis'), width - 2):
            _emit(lines, f"  epoch: {part}", width, subsequent_indent="         ")
    _emit(lines, f"Current / lastUpdated: {_fmt_iso_short(last_updated)}", width)
    if pt.get("lastUpdatedMillis") is not None:
        for part in _fmt_millis_compact(pt.get('lastUpdatedMillis'), width - 2):
            _emit(lines, f"  epoch: {part}", width, subsequent_indent="         ")

    # Detect missing/invalid
    has_valid = pt.get("isSessionPercentFinite") and pt.get("isWindowValid") and pt.get("isResetFinite") and pt.get("isLastUpdatedFinite")
    if not has_valid and session_percent is None:
        lines.append("")
        lines.append(_c("REMAINING % SZÁMÍTÁS", ANSI_BOLD, use_color=use_color))
        lines.append(_hr(min(28, width), "─", use_color=use_color))
        # Friendly box
        box_w = min(width, 72)
        lines.append(_c("┌" + "─" * (box_w - 2) + "┐", ANSI_YELLOW, use_color=use_color))
        msg1 = " Session adat nem elérhető (session_percent = n/a). "
        msg2 = " A widget ebben az állapotban nem jelenít meg session értéket. "
        # center within box
        for m in [msg1, msg2]:
            padded = m.ljust(box_w - 2)
            lines.append(_c("│", ANSI_YELLOW, use_color=use_color) + padded + _c("│", ANSI_YELLOW, use_color=use_color))
        lines.append(_c("└" + "─" * (box_w - 2) + "┘", ANSI_YELLOW, use_color=use_color))
        # hint
        _emit(lines, _c("Tipp:", ANSI_BOLD, use_color=use_color) + " a Codex CLI API most nem adott 5 órás ablakot — ez normális, ha nincs aktív session. Próbáld: " + _c("codex app-server --stdio", ANSI_DIM, use_color=use_color), width)
        lines.append("")
        lines.append(_c("PACE SZÁMÍTÁS", ANSI_BOLD, use_color=use_color))
        lines.append(_hr(min(24, width), "─", use_color=use_color))
        _emit(lines, _c("Pace nem számítható (hiányzó bemenet).", ANSI_DIM, use_color=use_color), width)
        if pt.get("isSessionPercentFinite") is False:
            _emit(lines, "  • sessionPercent nem véges / hiányzik", width)
        if pt.get("isWindowValid") is False:
            _emit(lines, "  • sessionWindowMins hiányzik vagy ≤ 0", width)
        if pt.get("isResetFinite") is False:
            _emit(lines, "  • sessionResetAt érvénytelen timestamp", width)
        if pt.get("isLastUpdatedFinite") is False:
            _emit(lines, "  • lastUpdated érvénytelen timestamp", width)
        lines.append("")
        lines.append(_c("COLOR / DISPLAY", ANSI_BOLD, use_color=use_color))
        lines.append(_hr(min(24, width), "─", use_color=use_color))
        _emit(lines, f"Indicator level: {level.get('result', 'n/a')}", width)
        _emit(lines, f"Indicator class: codex-session-daily-limit-{level.get('result', 'n/a')}", width)
        fallback = pcolor.get('fallback', {}).get('result') if isinstance(pcolor.get('fallback'), dict) else pcolor.get('effective')
        _emit(lines, f"Color (fallback, limitIndicatorColor): {_fmt_color(fallback)}", width)
        _emit(lines, f"Effective dot color: {_fmt_color(pcolor.get('effective'))}", width)
        return "\n".join(lines)

    lines.append("")
    lines.append(_c("REMAINING % SZÁMÍTÁS", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(28, width), "─", use_color=use_color))
    if session_used is not None and session_percent is not None:
        _emit(lines, f"Raw used (Codex API usedPercent, helper kerekítve): {_fmt_percent(session_used, 2)}", width)
        _emit(lines, f"Bounded used (clamp [0,100]): {_fmt_percent(max(0, min(100, session_used)), 2) if isinstance(session_used, (int, float)) else 'n/a'}", width)
        _emit(lines, "remaining = 100 - bounded_used", width)
        if isinstance(session_used, (int, float)):
            bounded = max(0, min(100, round(session_used)))
            rem = 100 - bounded
            _emit(lines, f"         = 100 - {bounded:.2f}", width)
            _emit(lines, f"         = {rem:.2f} %", width)
        _emit(lines, f"Eredmény (payload session_percent): {_fmt_percent(remaining.get('raw'), 2)}", width)
        _emit(lines, f"Widget kijelzés (kerekítve): {remaining.get('rounded') if remaining.get('rounded') is not None else 'n/a'} %", width)
    else:
        _emit(lines, f"Remaining (payload): {_fmt_percent(remaining.get('raw'), 2)}", width)
        _emit(lines, f"  clamped [0,100]: {_fmt_percent(remaining.get('clamped'), 2)}", width)
        _emit(lines, f"  kerekítve (widget): {remaining.get('rounded') if remaining.get('rounded') is not None else 'n/a'} %", width)

    lines.append("")
    lines.append(_c("PACE SZÁMÍTÁS  —  calculateSessionPace()", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(42, width), "─", use_color=use_color))
    if pace.get("result") is None:
        _emit(lines, "Eredmény: n/a (null)", width)
        _emit(lines, "Ok: hiányzó vagy érvénytelen bemenet", width)
        if pt.get("isSessionPercentFinite") is False:
            _emit(lines, "  • sessionPercent nem véges", width)
        if pt.get("isWindowValid") is False:
            _emit(lines, "  • sessionWindowMins érvénytelen", width)
        if pt.get("isResetFinite") is False:
            _emit(lines, "  • sessionResetAt érvénytelen timestamp", width)
        if pt.get("isLastUpdatedFinite") is False:
            _emit(lines, "  • lastUpdated érvénytelen timestamp", width)
    else:
        total_millis = pt.get("sessionTotalMillis")
        start_millis = pt.get("sessionStartMillis")
        elapsed_millis = pt.get("elapsedMillis")
        elapsed_mins = pt.get("elapsedMinutes")
        raw_pct = pt.get("timeElapsedPercentRaw")
        clamped_pct = pt.get("timeElapsedPercentClamped")
        raw_pace = pt.get("rawPace")
        clamped_pace = pt.get("clampedPace")

        _emit(lines, "Session teljes idő (sessionWindowMins × 60 × 1000):", width)
        _emit(lines, f"  {session_window_mins} min × 60 × 1000 = {_safe(total_millis)} ms  ({_fmt_number(total_millis / 60000 if isinstance(total_millis, (int, float)) else None, 2)} min)", width, subsequent_indent="    ")
        lines.append("")
        _emit(lines, "Session kezdete = reset − duration:", width)
        if start_millis is not None:
            _emit(lines, f"  {pt.get('resetAtMillis')} − {total_millis} = {start_millis} ms", width, subsequent_indent="    ")
            for part in _fmt_millis_compact(start_millis, width - 2):
                _emit(lines, f"  {part}", width)
        else:
            _emit(lines, "  n/a", width)
        lines.append("")
        _emit(lines, "Eltelt idő = lastUpdated − sessionStart:", width)
        if elapsed_millis is not None:
            _emit(lines, f"  {pt.get('lastUpdatedMillis')} − {start_millis} = {elapsed_millis} ms", width, subsequent_indent="    ")
            if isinstance(elapsed_millis, (int, float)):
                hrs = int(elapsed_millis // 3600000)
                mins = int((elapsed_millis % 3600000) // 60000)
                secs = int((elapsed_millis % 60000) // 1000)
                _emit(lines, f"  = {hrs}ó {mins}p {secs}mp  ({_fmt_number(elapsed_mins, 2)} min)", width, subsequent_indent="    ")
        lines.append("")
        _emit(lines, "Eltelt idő aránya:", width)
        _emit(lines, "  elapsed / total × 100", width)
        if raw_pct is not None:
            _emit(lines, f"  = {elapsed_millis} / {total_millis} × 100", width, subsequent_indent="    ")
            _emit(lines, f"  = {_fmt_number(raw_pct, 6)} %  (raw)", width, subsequent_indent="    ")
            _emit(lines, f"  clamp [0,100] → {_fmt_percent(clamped_pct, 4)}", width, subsequent_indent="    ")
        lines.append("")
        _emit(lines, f"Remaining: {_fmt_percent(session_percent, 2)}", width)
        _emit(lines, "Raw pace = remaining − elapsedPct:", width)
        if raw_pace is not None:
            _emit(lines, f"        = {_fmt_number(session_percent, 2)} − {_fmt_number(clamped_pct, 4)}", width, subsequent_indent="          ")
            _emit(lines, f"        = {_fmt_number(raw_pace, 4)}", width)
            _emit(lines, f"Clamp [−100, +100] → {_fmt_number(clamped_pace, 2)}", width)
        _emit(lines, f"Final pace: {_fmt_number(pace.get('result'), 2)}", width)

    lines.append("")
    lines.append(_c("COLOR / DISPLAY", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(24, width), "─", use_color=use_color))
    pcolor_trace = pcolor.get("trace") or {}
    fallback = pcolor.get("fallback") if isinstance(pcolor.get("fallback"), dict) else {}
    if pace.get("result") is not None:
        _emit(lines, f"Pace input: {_fmt_number(pace.get('result'), 2)}", width)
        _emit(lines, "Color normalization (paceColor, min=−100, max=+100):", width)
        clamped_n = pcolor_trace.get('normalizeTrace', {}).get('clamped') if isinstance(pcolor_trace.get('normalizeTrace'), dict) else 'n/a'
        _emit(lines, f"  clamp [−100, 100] → {_fmt_number(clamped_n, 2) if isinstance(clamped_n, (int,float)) else 'n/a'}", width, subsequent_indent="    ")
        _emit(lines, f"  normalized = (clamped − min)/(max−min)×100 = {_fmt_number(pcolor_trace.get('normalized'), 4)} %", width, subsequent_indent="    ")
        if pcolor_trace.get("selectedIndex") is not None:
            _emit(lines, f"  PACE_COLOR_STOPS intervallum: index {pcolor_trace.get('selectedIndex')}  [{pcolor_trace.get('lowerPercent')}%, {pcolor_trace.get('upperPercent')}%]", width, subsequent_indent="    ")
            _emit(lines, f"  Alsó szín: {_fmt_color(pcolor_trace.get('lowerColor'))}  Felső szín: {_fmt_color(pcolor_trace.get('upperColor'))}", width, subsequent_indent="    ")
            _emit(lines, f"  ratio = (norm − lower)/(upper−lower) = {_fmt_number(pcolor_trace.get('ratio'), 6)}", width, subsequent_indent="    ")
            _emit(lines, f"  Interpolált RGB: {pcolor_trace.get('interpolatedRgb')}", width, subsequent_indent="    ")
        _emit(lines, f"Selected / interpolated: {_fmt_color(pcolor.get('result'))}", width)
        _emit(lines, f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else 'n/a')}", width)
        _emit(lines, f"Effective dot color: {_fmt_color(pcolor.get('effective'))}", width)
    else:
        _emit(lines, "Pace: n/a (null)", width)
        _emit(lines, f"Fallback color (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else _fmt_color(pcolor.get('effective')))}", width)
        _emit(lines, f"Effective dot color: {_fmt_color(pcolor.get('effective'))}", width)
    _emit(lines, f"Indicator remaining: {_fmt_percent(session_percent, 2)}", width)
    _emit(lines, f"Indicator class: codex-session-daily-limit-{level.get('result', 'n/a')}", width)
    if level.get("trace"):
        lt = level["trace"]
        _emit(lines, f"  input={_fmt_percent(lt.get('input'),2)}, isOver100={lt.get('isOver100')}, clamped={_safe(lt.get('clamped'))}, rounded={_safe(lt.get('rounded'))}", width, subsequent_indent="    ")

    return "\n".join(lines)


def _render_daily(trace: dict, width: int | None = None, use_color: bool | None = None) -> str:
    if width is None:
        width = _term_width()
    if use_color is None:
        use_color = _supports_color()
    d = trace.get("daily", {})
    inp = d.get("input", {})
    wpr = d.get("weeklyPaceResult", {})
    wpr_trace = wpr.get("trace") or {}
    pace = d.get("pace", {})
    pcolor = d.get("paceColor", {})
    level = d.get("indicatorLevel", {})

    weekly_percent = inp.get("weeklyPercent")
    weekly_used = inp.get("weeklyUsedPercent")
    weekly_reset_at = inp.get("weeklyResetAt")
    last_updated = inp.get("lastUpdated")
    workdays = inp.get("weeklyWorkdays")

    daily_remaining = d.get("remaining", {}).get("result")
    wt = wpr_trace

    lines: list[str] = []
    lines.append(_c("2. NAPI KERET", ANSI_BOLD, ANSI_WHITE, use_color=use_color))
    lines.append(_c("═" * min(14, width), ANSI_DIM, use_color=use_color))
    lines.append("")
    lines.append(_c("INPUT", ANSI_BOLD, ANSI_CYAN, use_color=use_color))
    lines.append(_hr(min(24, width), "─", use_color=use_color))
    _emit(lines, f"Weekly remaining (payload weekly_percent): {_fmt_percent(weekly_percent, 2)}", width)
    if weekly_used is not None:
        _emit(lines, f"Weekly used (helper clamped): {_fmt_percent(weekly_used, 2)}", width)
    _emit(lines, f"Configured workdays (weekly_workdays): {_safe(workdays)}", width)
    _emit(lines, f"Weekly reset (weekly_reset_at): {_fmt_iso_short(weekly_reset_at)}", width)
    if wt.get("resetAtMillis") is not None:
        for part in _fmt_millis_compact(wt.get('resetAtMillis'), width - 2):
            _emit(lines, f"  epoch: {part}", width)
    _emit(lines, f"Current / lastUpdated: {_fmt_iso_short(last_updated)}", width)
    if wt.get("lastUpdatedMillis") is not None:
        for part in _fmt_millis_compact(wt.get('lastUpdatedMillis'), width - 2):
            _emit(lines, f"  epoch: {part}", width)
    _emit(lines, f"Budget / workday = 100 / workdays: {_fmt_number(wt.get('fullDayBudget'), 4) if wt.get('fullDayBudget') is not None else 'n/a'} pp", width)
    if wt.get("isIncomplete"):
        lines.append("")
        lines.append(_c("REMAINING % SZÁMÍTÁS", ANSI_BOLD, use_color=use_color))
        lines.append(_hr(min(28, width), "─", use_color=use_color))
        _emit(lines, "Napi keret nem számítható (hiányzó bemenet).", width)
        _emit(lines, f"  isQuotaFinite={wt.get('isQuotaFinite')}, isResetFinite={wt.get('isResetFinite')}, isLastUpdatedFinite={wt.get('isLastUpdatedFinite')}", width)
        lines.append("")
        lines.append(_c("PACE SZÁMÍTÁS", ANSI_BOLD, use_color=use_color))
        lines.append(_hr(min(24, width), "─", use_color=use_color))
        _emit(lines, "Pace nem számítható (hiányzó daily elapsedFraction).", width)
        lines.append("")
        lines.append(_c("COLOR / DISPLAY", ANSI_BOLD, use_color=use_color))
        lines.append(_hr(min(24, width), "─", use_color=use_color))
        _emit(lines, f"Indicator level: {level.get('result', 'n/a')}", width)
        _emit(lines, f"Effective color: {_fmt_color(pcolor.get('effective'))}", width)
        return "\n".join(lines)

    lines.append("")
    lines.append(_c("Idő-számítás részletei (calculateWeeklyPace belső):", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(48, width), "─", use_color=use_color))
    _emit(lines, "WeeklyStart = reset − 7 nap:", width)
    if wt.get("weeklyStartMillis") is not None:
        _emit(lines, f"  {wt.get('resetAtMillis')} − 7×86400000 = {wt.get('weeklyStartMillis')} ms", width, subsequent_indent="    ")
        for part in _fmt_millis_compact(wt.get('weeklyStartMillis'), width - 2):
            _emit(lines, f"  {part}", width)
    _emit(lines, "Consumption horizon = weeklyStart + workdays × 24h:", width)
    if wt.get("consumptionHorizonMillis") is not None:
        _emit(lines, f"  {wt.get('weeklyStartMillis')} + {workdays}×86400000 = {wt.get('consumptionHorizonMillis')} ms", width, subsequent_indent="    ")
        for part in _fmt_millis_compact(wt.get('consumptionHorizonMillis'), width - 2):
            _emit(lines, f"  {part}", width)
    _emit(lines, f"FullDayBudget = 100 / {workdays} = {_fmt_number(wt.get('fullDayBudget'), 4)} pp", width)
    lines.append("")
    _emit(lines, f"lastUpdatedDate: {_safe(wt.get('lastUpdatedDate'))}", width)
    if wt.get("localToday00") is not None:
        for part in _fmt_millis_compact(wt.get('localToday00'), width - 2):
            # first line with label
            if part == _fmt_millis_compact(wt.get('localToday00'), width - 2)[0]:
                _emit(lines, f"localToday00 (helyi éjfél): {part}", width)
            else:
                _emit(lines, f"  {part}", width)
    if wt.get("localNextDay00") is not None:
        for part in _fmt_millis_compact(wt.get('localNextDay00'), width - 2):
            if part == _fmt_millis_compact(wt.get('localNextDay00'), width - 2)[0]:
                _emit(lines, f"localNextDay00 (következő éjfél): {part}", width)
            else:
                _emit(lines, f"  {part}", width)
    if wt.get("effectiveDayStart") is not None:
        _emit(lines, f"effectiveDayStart = max(localToday00, weeklyStart) = {wt.get('effectiveDayStart')} ms", width, subsequent_indent="  ")
        for part in _fmt_millis_compact(wt.get('effectiveDayStart'), width - 2):
            _emit(lines, f"  {part}", width)
    if wt.get("effectiveDayEnd") is not None:
        _emit(lines, f"effectiveDayEnd = min(localNextDay00, horizon) = {wt.get('effectiveDayEnd')} ms", width, subsequent_indent="  ")
        for part in _fmt_millis_compact(wt.get('effectiveDayEnd'), width - 2):
            _emit(lines, f"  {part}", width)
    if wt.get("todayDuration") is not None:
        _emit(lines, f"todayDuration = max(0, end − start) = {wt.get('todayDuration')} ms  ({_fmt_number(wt.get('todayDurationHours'), 4)} h)", width, subsequent_indent="  ")
    if wt.get("todayBudget") is not None:
        _emit(lines, f"todayBudget = todayDuration/DAY × fullDayBudget = {_fmt_number(wt.get('todayDuration'), 2)} / 86400000 × {_fmt_number(wt.get('fullDayBudget'), 4)} = {_fmt_number(wt.get('todayBudget'), 6)} pp", width, subsequent_indent="  ")

    lines.append("")
    lines.append(_c("REMAINING % SZÁMÍTÁS  —  EOD-normalizált napi maradék", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(52, width), "─", use_color=use_color))
    _emit(lines, f"Weekly bounded remaining (clamp [0,100]): {_fmt_percent(wt.get('boundedQuotaRemainingPercent'), 2)}", width)
    if wt.get("nextDayCapped") is not None:
        _emit(lines, f"nextDayCapped = min(localNextDay00, horizon) = {wt.get('nextDayCapped')} ms", width, subsequent_indent="  ")
    if wt.get("allowedByEOD") is not None:
        _emit(lines, "allowedByEOD = (nextDayCapped − weeklyStart)/(workdays×DAY)×100", width)
        if wt.get("weeklyStartMillis") is not None and wt.get("nextDayCapped") is not None:
            _emit(lines, f"  = ({wt.get('nextDayCapped')} − {wt.get('weeklyStartMillis')}) / ({workdays}×86400000) × 100", width, subsequent_indent="    ")
            _emit(lines, f"  = {_fmt_percent(wt.get('allowedByEOD'), 4)}", width, subsequent_indent="    ")
    if wt.get("actualUsage") is not None:
        _emit(lines, f"actualUsage = 100 − boundedRemaining = 100 − {_fmt_number(wt.get('boundedQuotaRemainingPercent'), 2)} = {_fmt_number(wt.get('actualUsage'), 4)} pp", width, subsequent_indent="  ")
    if wt.get("available") is not None:
        _emit(lines, f"available = allowedByEOD − actualUsage = {_fmt_number(wt.get('allowedByEOD'), 4)} − {_fmt_number(wt.get('actualUsage'), 4)} = {_fmt_number(wt.get('available'), 4)} pp", width, subsequent_indent="  ")
    if wt.get("divisor") is not None:
        _emit(lines, f"divisor = todayBudget > 0 ? todayBudget : fullDayBudget = {_fmt_number(wt.get('divisor'), 6)} pp", width, subsequent_indent="  ")
    _emit(lines, "dailyRemainingPercent = available / divisor × 100", width)
    if daily_remaining is not None:
        _emit(lines, f"  = {_fmt_number(wt.get('available'), 4)} / {_fmt_number(wt.get('divisor'), 6)} × 100", width, subsequent_indent="    ")
        _emit(lines, f"  = {_fmt_number(daily_remaining, 4)} %  (raw, nincs clamp!)", width, subsequent_indent="    ")
        if daily_remaining > 100:
            _emit(lines, _c("  → >100 % : előtakarékosság (kevesebb fogyott, mint tervezett)", ANSI_GREEN, use_color=use_color), width, subsequent_indent="    ")
        elif daily_remaining < 0:
            _emit(lines, _c("  → <0 % : túlfogyasztás (több fogyott, mint az EOD-keret)", ANSI_RED, use_color=use_color), width, subsequent_indent="    ")
    else:
        _emit(lines, "  = n/a", width)
    _emit(lines, f"Eredmény (dailyRemainingPercent): {_fmt_number(daily_remaining, 4) if daily_remaining is not None else 'n/a'} %", width)
    if daily_remaining is not None:
        _emit(lines, f"Widget kijelzés (kerekítve): {round(daily_remaining)} %", width)
        _emit(lines, f"Indicator-level input (raw): {_fmt_percent(daily_remaining, 2)}", width)
        _emit(lines, f"Indicator class: codex-session-daily-limit-{level.get('result', 'n/a')}", width)
    if wt.get("elapsedFraction") is not None:
        _emit(lines, f"elapsedMillis = max(0, lastUpdated − weeklyStart) = {wt.get('elapsedMillis')} ms", width, subsequent_indent="  ")
        _emit(lines, f"elapsedFraction = min(1, elapsedMillis/(workdays×DAY)) = {_fmt_number(wt.get('elapsedFraction'), 6)}", width, subsequent_indent="  ")
        _emit(lines, f"  = {wt.get('elapsedMillis')} / {workdays * 86400000} = {_fmt_number(wt.get('elapsedFraction'), 6)}", width, subsequent_indent="    ")
        _emit(lines, f"elapsedWorkdays = elapsedFraction × workdays = {_fmt_number(wt.get('elapsedWorkdays'), 4)}", width, subsequent_indent="  ")
        _emit(lines, f"todayMinimumRemainingPercent = max(0, 100 − elapsedWorkdays×fullDayBudget) = {_fmt_number(wt.get('todayMinimumRemainingPercent'), 4)} %", width, subsequent_indent="  ")

    lines.append("")
    lines.append(_c("PACE SZÁMÍTÁS  —  dailyConsumptionPace()  [napi pont színe]", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(58, width), "─", use_color=use_color))
    _emit(lines, "A napi pont színe NEM a napi remaining-ből jön, hanem külön pace-ből:", width)
    _emit(lines, "  dailyPace = actualUsage / expectedUsage", width)
    _emit(lines, "  actualUsage   = 100 − weeklyPercent", width)
    _emit(lines, "  expectedUsage = elapsedFraction(daily) × 100", width)
    pt = pace.get("trace") or {}
    if pace.get("result") is None:
        _emit(lines, "Eredmény: n/a (null)", width)
        if pt.get("reason"):
            _emit(lines, f"Ok: {pt.get('reason')}", width)
        elif pt.get("isActualFinite") is False or pt.get("isExpectedFinite") is False:
            _emit(lines, "Ok: nem véges bemenet", width)
    else:
        _emit(lines, f"actualUsage   = 100 − {_fmt_number(weekly_percent, 2)} = {_fmt_number(pt.get('actualUsage'), 4)} pp", width, subsequent_indent="  ")
        _emit(lines, f"expectedUsage = elapsedFraction × 100 = {_fmt_number(wt.get('elapsedFraction'), 6)} × 100 = {_fmt_number(pt.get('expectedUsage'), 4)} pp", width, subsequent_indent="  ")
        if pt.get("isZeroZero"):
            _emit(lines, "Speciális: expected=0 és actual=0  → pace = 1.0 (pontosan terv szerint)", width)
        elif pt.get("isInfiniteCase"):
            _emit(lines, "Speciális: expected=0 de actual>0  → pace = ∞ (idő előtt fogyott)", width)
            _emit(lines, f"  actualUsage={_fmt_number(pt.get('actualUsage'),4)} > 0, expectedUsage=0", width)
        else:
            _emit(lines, f"Raw pace = actual / expected = {_fmt_number(pt.get('actualUsage'), 4)} / {_fmt_number(pt.get('expectedUsage'), 4)} = {_fmt_number(pt.get('ratio'), 6)}", width, subsequent_indent="  ")
        _emit(lines, f"Final pace: {_fmt_number(pace.get('result'), 6)}×", width)
        _emit(lines, "  1.00 = terv szerinti ütem", width)
        _emit(lines, "  <1.00 = lassabb a tervnél (kíméled a keretet)", width)
        _emit(lines, "  >1.00 = gyorsabb a tervnél (gyorsabban fogy)", width)
        if isinstance(pace.get("result"), float) and math.isinf(pace.get("result")):
            _emit(lines, "  ∞ = végtelen: nulla idő alatt már fogyott", width)
    lines.append("")
    lines.append(_c("COLOR / DISPLAY  —  paceToColor()  küszöbök", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(52, width), "─", use_color=use_color))
    pct = pcolor.get("trace") or {}
    fallback = pcolor.get("fallback") if isinstance(pcolor.get("fallback"), dict) else {}
    if pace.get("result") is None:
        _emit(lines, "Pace: n/a", width)
        _emit(lines, f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else pcolor.get('effective'))}", width)
    else:
        _emit(lines, f"Pace input: {_fmt_number(pace.get('result'), 6)}", width)
        if pct.get("selectedThreshold") is not None:
            thr = pct.get("selectedThreshold")
            bands = [
                (0.80, "#15803D", "zöld (lassú / takarékos)"),
                (0.94, "#84CC16", "világoszöld"),
                (1.05, "#FACC15", "sárga (terv közelében)"),
                (1.25, "#EA580C", "narancs (gyors)"),
                (float("inf"), "#B91C1C", "piros (kritikus)"),
            ]
            _emit(lines, "Threshold értékelés:", width)
            for b_thr, b_col, b_label in bands:
                marker = " ← kiválasztott" if b_col == pct.get("selectedColor") else ""
                thr_str = "∞" if math.isinf(b_thr) else f"{b_thr:.2f}"
                # color dot
                dot = _c("●", ANSI_BOLD, use_color=use_color) if marker else "○"
                _emit(lines, f"  {dot} pace ≤ {thr_str}  → {b_col}  {b_label}{marker}", width, subsequent_indent="    ")
            _emit(lines, f"Selected band küszöb: {thr if not math.isinf(thr) else '∞'}", width)
        _emit(lines, f"Selected color: {_fmt_color(pcolor.get('result'))}", width)
        _emit(lines, f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else 'n/a')}", width)
        _emit(lines, f"Effective dot color: {_fmt_color(pcolor.get('effective'))}", width)
        if isinstance(pace.get("result"), float) and math.isinf(pace.get("result")):
            _emit(lines, "Megjegyzés: pace=∞ → paceToColor(null) → fallback szín érvényesül", width)
    _emit(lines, f"Indicator remaining: {_fmt_percent(daily_remaining, 2) if daily_remaining is not None else 'n/a'}", width)
    _emit(lines, f"Indicator class: codex-session-daily-limit-{level.get('result', 'n/a')}", width)

    return "\n".join(lines)


def _render_weekly(trace: dict, width: int | None = None, use_color: bool | None = None) -> str:
    if width is None:
        width = _term_width()
    if use_color is None:
        use_color = _supports_color()
    w = trace.get("weekly", {})
    inp = w.get("input", {})
    elapsed = w.get("elapsedFraction", {})
    pace = w.get("pace", {})
    pcolor = w.get("paceColor", {})
    level = w.get("indicatorLevel", {})
    remaining = w.get("remaining", {})

    weekly_percent = inp.get("weeklyPercent")
    weekly_used = inp.get("weeklyUsedPercent")
    weekly_reset_at = inp.get("weeklyResetAt")
    last_updated = inp.get("lastUpdated")

    et = elapsed.get("trace") or {}
    pt = pace.get("trace") or {}

    lines: list[str] = []
    lines.append(_c("3. HETI KERET", ANSI_BOLD, ANSI_WHITE, use_color=use_color))
    lines.append(_c("═" * min(14, width), ANSI_DIM, use_color=use_color))
    lines.append("")
    lines.append(_c("INPUT", ANSI_BOLD, ANSI_CYAN, use_color=use_color))
    lines.append(_hr(min(24, width), "─", use_color=use_color))
    if weekly_used is not None:
        _emit(lines, f"Codex weekly usedPercent (helper, kerekített, clampelt): {_fmt_percent(weekly_used, 2)}", width)
        _emit(lines, f"  → remaining (100 − used) = {_fmt_percent(weekly_percent, 2) if weekly_percent is not None else 'n/a'}", width)
    else:
        _emit(lines, f"Weekly remaining (payload weekly_percent): {_fmt_percent(weekly_percent, 2)}", width)
    _emit(lines, f"Weekly reset (weekly_reset_at): {_fmt_iso_short(weekly_reset_at)}", width)
    if et.get("resetAtMillis") is not None:
        for part in _fmt_millis_compact(et.get('resetAtMillis'), width - 2):
            _emit(lines, f"  epoch: {part}", width)
    _emit(lines, f"Current / lastUpdated: {_fmt_iso_short(last_updated)}", width)
    if et.get("lastUpdatedMillis") is not None:
        for part in _fmt_millis_compact(et.get('lastUpdatedMillis'), width - 2):
            _emit(lines, f"  epoch: {part}", width)

    lines.append("")
    lines.append(_c("REMAINING % SZÁMÍTÁS", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(28, width), "─", use_color=use_color))
    if weekly_percent is None or not isinstance(weekly_percent, (int, float)):
        _emit(lines, "Weekly remaining: n/a (weeklyPercent nem véges)", width)
    else:
        if weekly_used is not None:
            _emit(lines, f"API usedPercent (helper kerekítve/clampelve): {_fmt_percent(weekly_used, 2)}", width)
            bounded = max(0, min(100, round(weekly_used)) if isinstance(weekly_used, (int, float)) else weekly_used)
            _emit(lines, f"  rounded: {_safe(round(weekly_used)) if isinstance(weekly_used, (int,float)) else 'n/a'}, clamped [0,100]: {_fmt_percent(bounded,2) if isinstance(bounded,(int,float)) else 'n/a'}", width, subsequent_indent="    ")
            _emit(lines, f"remaining = 100 − bounded_used = 100 − {_safe(bounded)} = {_fmt_percent(remaining.get('raw'), 2)}", width, subsequent_indent="  ")
        else:
            _emit(lines, f"remaining = 100 − used (közvetlen payload weekly_percent): {_fmt_percent(remaining.get('raw'), 2)}", width)
        _emit(lines, f"Raw remaining: {_fmt_percent(remaining.get('raw'), 2)}", width)
        _emit(lines, f"Clamped [0,100]: {_fmt_percent(remaining.get('clamped'), 2)}", width)
        _emit(lines, f"Rounded / widget kijelzés: {remaining.get('rounded') if remaining.get('rounded') is not None else 'n/a'} %", width)
        _emit(lines, f"Widget panel: {remaining.get('rounded') if remaining.get('rounded') is not None else 'n/a'}%", width)

    lines.append("")
    lines.append(_c("PACE SZÁMÍTÁS  —  weeklyConsumptionPace() / elapsedFractionOfWeek()", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(62, width), "─", use_color=use_color))
    _emit(lines, "Heti pace = actualUsage / expectedUsage", width)
    _emit(lines, "  actualUsage   = 100 − weeklyPercent", width)
    _emit(lines, "  expectedUsage = elapsedFractionOfWeek × 100", width)
    _emit(lines, "  elapsedFractionOfWeek = elapsedMillis / (7×DAY)  [7 napos ablak]", width)
    lines.append("")
    if et.get("isResetFinite") is False or et.get("isLastUpdatedFinite") is False:
        _emit(lines, "elapsedFraction: n/a (érvénytelen timestamp)", width)
        _emit(lines, f"  resetAtMillis finite={et.get('isResetFinite')}, lastUpdatedMillis finite={et.get('isLastUpdatedFinite')}", width)
    elif elapsed.get("result") is None:
        _emit(lines, "elapsedFraction: n/a", width)
        if et.get("reason"):
            _emit(lines, f"  ok: {et.get('reason')}", width)
    else:
        _emit(lines, "elapsedFraction számítás (elapsedFractionOfWeek):", width)
        _emit(lines, f"  resetAtMillis: {et.get('resetAtMillis')}  ({_fmt_millis(et.get('resetAtMillis'))})", width, subsequent_indent="    ")
        # split long millis lines for narrow
        ws_line = f"  windowStart = reset − 7 nap = {et.get('windowStartMillis')} ms"
        _emit(lines, ws_line, width, subsequent_indent="    ")
        for part in _fmt_millis_compact(et.get('windowStartMillis'), width - 4):
            if part not in ws_line:
                _emit(lines, f"    {part}", width)
        _emit(lines, f"  elapsedMillis = max(0, lastUpdated − windowStart) = {et.get('elapsedMillis')} ms", width, subsequent_indent="    ")
        if isinstance(et.get('elapsedMillis'), (int, float)):
            hrs = et.get('elapsedMillis') / 3600000
            days = et.get('elapsedMillis') / 86400000
            _emit(lines, f"    = {_fmt_number(hrs, 2)} h  ({_fmt_number(days, 4)} nap)", width)
        _emit(lines, f"  weekMillis = 7 × 86400000 = {et.get('weekMillis')} ms", width)
        _emit(lines, f"  rawFraction = elapsed / weekMillis = {_fmt_number(et.get('rawFraction'), 6)}", width, subsequent_indent="    ")
        _emit(lines, f"  clamped [0,1] = min(1, raw) = {_fmt_number(et.get('clampedFraction'), 6)}", width, subsequent_indent="    ")
        _emit(lines, f"  Final elapsedFraction: {_fmt_number(elapsed.get('result'), 6)}  ({_fmt_percent(elapsed.get('result') * 100 if isinstance(elapsed.get('result'), (int,float)) else None, 2)})", width, subsequent_indent="    ")
        lines.append("")
        if pace.get("result") is None:
            _emit(lines, "weeklyConsumptionPace: n/a", width)
            if pt.get("reason"):
                _emit(lines, f"  ok: {pt.get('reason')}", width)
        else:
            _emit(lines, f"actualUsage   = 100 − {_fmt_number(weekly_percent,2)} = {_fmt_number(pt.get('actualUsage'), 4)} pp", width, subsequent_indent="  ")
            _emit(lines, f"expectedUsage = elapsedFraction × 100 = {_fmt_number(elapsed.get('result'),6)} × 100 = {_fmt_number(pt.get('expectedUsage'), 4)} pp", width, subsequent_indent="  ")
            dpt = pt.get("dailyPaceTrace") or {}
            if dpt.get("isZeroZero"):
                _emit(lines, "Speciális: expected=0 és actual=0 → pace=1.0", width)
            elif dpt.get("isInfiniteCase"):
                _emit(lines, "Speciális: expected=0 de actual>0 → pace=∞", width)
                _emit(lines, f"  actualUsage={_fmt_number(pt.get('actualUsage'),4)} > 0, expectedUsage=0", width)
            else:
                _emit(lines, f"Raw pace = actual / expected = {_fmt_number(pt.get('actualUsage'),4)} / {_fmt_number(pt.get('expectedUsage'),4)} = {_fmt_number(pt.get('ratio') if 'ratio' in dpt else pace.get('result'), 6)}", width, subsequent_indent="  ")
            _emit(lines, f"Final weekly pace: {_fmt_number(pace.get('result'), 6)}×", width)
            if isinstance(pace.get("result"), float) and math.isinf(pace.get("result")):
                _emit(lines, "  ∞ = végtelen: a hét elején már fogyott a keret", width)
            else:
                _emit(lines, "  1.00 = terv szerinti ütem (7 napos ablak)", width)
                _emit(lines, "  <1.00 = lassabb a tervnél", width)
                _emit(lines, "  >1.00 = gyorsabb a tervnél", width)

    lines.append("")
    lines.append(_c("COLOR / DISPLAY  —  paceToColor()  küszöbök", ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(52, width), "─", use_color=use_color))
    pct = pcolor.get("trace") or {}
    fallback = pcolor.get("fallback") if isinstance(pcolor.get("fallback"), dict) else {}
    if pace.get("result") is None:
        _emit(lines, "Pace: n/a", width)
        _emit(lines, f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else pcolor.get('effective'))}", width)
    else:
        if isinstance(pace.get("result"), float) and math.isinf(pace.get("result")):
            _emit(lines, "Pace input: ∞", width)
            _emit(lines, "paceToColor(∞) → null (nem véges) → fallback szín érvényesül", width)
            _emit(lines, f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else 'n/a')}", width)
            _emit(lines, f"Effective dot color: {_fmt_color(pcolor.get('effective'))}", width)
        else:
            _emit(lines, f"Pace input: {_fmt_number(pace.get('result'),6)}", width)
            if pct.get("selectedThreshold") is not None:
                thr = pct.get("selectedThreshold")
                bands = [
                    (0.80, "#15803D", "zöld (lassú / takarékos)"),
                    (0.94, "#84CC16", "világoszöld"),
                    (1.05, "#FACC15", "sárga (terv közelében)"),
                    (1.25, "#EA580C", "narancs (gyors)"),
                    (float("inf"), "#B91C1C", "piros (kritikus)"),
                ]
                _emit(lines, "Threshold értékelés:", width)
                for b_thr, b_col, b_label in bands:
                    marker = " ← kiválasztott" if b_col == pct.get("selectedColor") else ""
                    thr_str = "∞" if math.isinf(b_thr) else f"{b_thr:.2f}"
                    dot = _c("●", ANSI_BOLD, use_color=use_color) if marker else "○"
                    _emit(lines, f"  {dot} pace ≤ {thr_str}  → {b_col}  {b_label}{marker}", width, subsequent_indent="    ")
                _emit(lines, f"Selected band küszöb: {thr if not math.isinf(thr) else '∞'}", width)
            _emit(lines, f"Selected color: {_fmt_color(pcolor.get('result'))}", width)
            _emit(lines, f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else 'n/a')}", width)
            _emit(lines, f"Effective dot color: {_fmt_color(pcolor.get('effective'))}", width)
    _emit(lines, f"Indicator remaining: {_fmt_percent(weekly_percent,2) if weekly_percent is not None else 'n/a'}", width)
    _emit(lines, f"Indicator class: codex-session-daily-limit-{level.get('result', 'n/a')}", width)

    return "\n".join(lines)


def _render_summary(trace: dict, width: int | None = None, use_color: bool | None = None) -> str:
    if width is None:
        width = _term_width()
    if use_color is None:
        use_color = _supports_color()
    s = trace.get("session", {})
    d = trace.get("daily", {})
    w = trace.get("weekly", {})

    s_rem = s.get("remaining", {}).get("rounded")
    s_pace = s.get("pace", {}).get("result")
    s_color = s.get("paceColor", {}).get("effective")

    d_rem = d.get("remaining", {}).get("result")
    d_pace = d.get("pace", {}).get("result")
    d_color = d.get("paceColor", {}).get("effective")

    w_rem = w.get("remaining", {}).get("rounded")
    w_pace = w.get("pace", {}).get("result")
    w_color = w.get("paceColor", {}).get("effective")

    def fmt_rem(v: Any) -> str:
        if v is None:
            return "n/a"
        if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
            return "∞"
        try:
            return f"{round(v)}%"
        except Exception:
            return str(v)

    def fmt_pace(v: Any) -> str:
        if v is None:
            return "n/a"
        if isinstance(v, float) and math.isinf(v):
            return "∞"
        if isinstance(v, float) and math.isnan(v):
            return "NaN"
        return f"{v:.2f}×" if abs(v) >= 0.01 else f"{v:.4f}×"

    def fmt_pace_session(v: Any) -> str:
        if v is None:
            return "n/a"
        if isinstance(v, float) and math.isinf(v):
            return "∞"
        return f"{v:+.2f}"

    lines: list[str] = []
    lines.append(_c("ÖSSZEFOGLALÓ", ANSI_BOLD, ANSI_WHITE, use_color=use_color))
    lines.append(_c("═" * min(12, width), ANSI_DIM, use_color=use_color))
    lines.append("")
    # Header row
    header = f"{'':<22} {'Remaining':<14} {'Pace':<14} {'Color'}"
    lines.append(_c(header, ANSI_DIM, ANSI_BOLD, use_color=use_color))
    lines.append(_hr(min(len(header), width), "─", use_color=use_color))
    # Use color dots for remaining
    def dot_color(hexc: str | None) -> str:
        if not hexc or not use_color:
            return ""
        # approximate with colored dot
        return _c("●", use_color=use_color) + " "

    lines.append(f"{'5 órás session':<22} {fmt_rem(s_rem):<14} {fmt_pace_session(s_pace):<14} {s_color or 'n/a'}")
    d_rem_str = fmt_rem(d_rem) if d_rem is not None else "n/a"
    lines.append(f"{'Napi keret':<22} {d_rem_str:<14} {fmt_pace(d_pace):<14} {d_color or 'n/a'}")
    lines.append(f"{'Heti keret':<22} {fmt_rem(w_rem):<14} {fmt_pace(w_pace):<14} {w_color or 'n/a'}")
    lines.append("")
    w_reset = w.get("input", {}).get("weeklyResetAt") or ""
    weekly_date = ""
    if w_reset:
        try:
            dt = datetime.fromisoformat(w_reset.replace("Z", "+00:00"))
            weekly_date = dt.strftime("%m.%d.")
        except Exception:
            weekly_date = ""
    session_comp = f"{round(s_rem)}% ({s.get('input', {}).get('sessionResetAt', '')[11:16]})" if s_rem is not None and s.get("input", {}).get("sessionResetAt") else (f"{round(s_rem)}%" if s_rem is not None else "–")
    daily_comp = f"{round(d_rem)}%" if d_rem is not None else "–"
    weekly_comp = f"{round(w_rem)}% ({weekly_date})" if w_rem is not None and weekly_date else (f"{round(w_rem)}%" if w_rem is not None else "–")

    lines.append(_c("Panel equivalent (widget):", ANSI_BOLD, use_color=use_color))
    panel_line = f"  Session: {session_comp}  │  Daily: {daily_comp}  │  Weekly: {weekly_comp}"
    _emit(lines, panel_line, width, subsequent_indent="  ")
    if s_color or d_color or w_color:
        _emit(lines, f"  Színek: session={s_color or 'n/a'}  daily={d_color or 'n/a'}  weekly={w_color or 'n/a'}", width, subsequent_indent="  ")
    return "\n".join(lines)


def render_screen(payload: dict, trace: dict, refresh_time: datetime, reason: str, next_time: datetime, width: int | None = None, use_color: bool | None = None) -> str:
    if width is None:
        width = _term_width()
    if use_color is None:
        use_color = _supports_color()
    parts: list[str] = []
    parts.append(_render_header(payload, trace, refresh_time, reason, next_time, width=width, use_color=use_color))
    parts.append(_render_session(trace, width=width, use_color=use_color))
    parts.append("")
    parts.append(_render_daily(trace, width=width, use_color=use_color))
    parts.append("")
    parts.append(_render_weekly(trace, width=width, use_color=use_color))
    parts.append("")
    parts.append(_render_summary(trace, width=width, use_color=use_color))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

def _do_refresh() -> tuple[dict, dict]:
    """Perform a live refresh and build trace. Returns (payload, trace)."""
    from .fetcher import refresh_status
    payload = refresh_status()
    effective = payload
    if not payload.get("ok") and payload.get("last_success"):
        effective = {**payload["last_success"], "ok": payload["ok"], "status": payload["status"], "message": payload.get("message"), "last_success": payload["last_success"], "source_label": payload.get("source_label")}
        trace_payload = {**payload["last_success"]}
        trace_payload["_freshness_ok"] = payload["ok"]
        trace_payload["_freshness_status"] = payload["status"]
        trace = get_trace(trace_payload)
        if "_meta" in trace:
            trace["_meta"]["ok"] = payload["ok"]
            trace["_meta"]["status"] = payload["status"]
            trace["_meta"]["isStale"] = True
            trace["_meta"]["hasLastSuccess"] = True
        return payload, trace
    trace = get_trace(effective)
    return payload, trace

def _clear_screen(*args, **kwargs) -> None:
    # Accept any args for test compatibility (tests mock with lambda: None)
    try:
        use_alt = sys.stdout.isatty() and sys.stdin.isatty()
    except Exception:
        use_alt = False
    # If caller explicitly forced via kwargs, honor it
    if "use_alt" in kwargs:
        use_alt = bool(kwargs["use_alt"])
    elif args and isinstance(args[0], bool):
        use_alt = bool(args[0])
    if use_alt:
        sys.stdout.write("\033[?1049h\033[H")
    else:
        sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()

def _restore_screen(*args, **kwargs) -> None:
    try:
        use_alt = sys.stdout.isatty() and sys.stdin.isatty()
    except Exception:
        use_alt = False
    if "use_alt" in kwargs:
        use_alt = bool(kwargs["use_alt"])
    elif args and isinstance(args[0], bool):
        use_alt = bool(args[0])
    if use_alt:
        sys.stdout.write("\033[?1049l")
    sys.stdout.flush()

def _enter_raw_mode() -> Any:
    """Enter raw terminal mode, return old settings or None if not a tty."""
    if not sys.stdin.isatty():
        return None
    try:
        import termios
        import tty
        old = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno())
        return old
    except Exception:
        return None

def _exit_raw_mode(old: Any) -> None:
    if old is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old)
    except Exception:
        pass

def run_debug(no_color: bool = False, width: int | None = None) -> int:
    """Entry point for `codex-session-meter debug`."""
    import select
    import signal

    # Resolve color once, but respect NO_COLOR
    use_color = _supports_color(no_color_flag=no_color)
    use_alt = sys.stdout.isatty() and sys.stdin.isatty()
    # Validate explicit width (clamped in _term_width)
    explicit_width: int | None = None
    if width is not None:
        try:
            explicit_width = max(60, min(160, int(width)))
        except Exception:
            explicit_width = None

    refresh_time = datetime.now().astimezone()
    reason = "indítás"
    try:
        payload, trace = _do_refresh()
    except Exception as exc:
        payload = {"ok": False, "status": "error", "display": "Codex: hiba", "message": str(exc)[:200]}
        trace = get_trace(payload)

    next_time = datetime.fromtimestamp(refresh_time.timestamp() + DEBUG_INTERVAL_SECONDS).astimezone()

    is_tty = sys.stdin.isatty()

    # track resize
    resized = {"flag": False}
    def _on_winch(signum, frame):
        resized["flag"] = True
    try:
        signal.signal(signal.SIGWINCH, _on_winch)
    except Exception:
        pass

    # old_term will be set later; draw checks it for raw-mode newline handling (zsh fix)
    old_term_holder: dict[str, Any] = {"old": None}

    def draw() -> None:
        w = _term_width(explicit=explicit_width) if explicit_width is not None else _term_width()
        screen = render_screen(payload, trace, refresh_time, reason, next_time, width=w, use_color=use_color)
        _clear_screen()
        out = screen + "\n"
        # In raw mode (zsh), ONLCR is disabled -> \n must be \r\n, otherwise lines don't wrap
        if old_term_holder["old"] is not None:
            out = out.replace("\n", "\r\n")
        sys.stdout.write(out)
        sys.stdout.flush()

    if not is_tty:
        # Non-interactive: just render once and exit (no color unless forced)
        w = _term_width(explicit=explicit_width) if explicit_width is not None else _term_width()
        if no_color:
            use_color_local = False
        else:
            use_color_local = _supports_color(no_color_flag=False) if os.environ.get("FORCE_COLOR") else False
        screen = render_screen(payload, trace, refresh_time, reason, next_time, width=w, use_color=use_color_local)
        sys.stdout.write(screen + "\n")
        sys.stdout.flush()
        return 0

    old_term = _enter_raw_mode()
    old_term_holder["old"] = old_term
    try:
        draw()
        while True:
            if resized["flag"]:
                resized["flag"] = False
                draw()
            deadline = refresh_time.timestamp() + DEBUG_INTERVAL_SECONDS
            remaining = deadline - time.time()
            if remaining <= 0:
                refresh_time = datetime.now().astimezone()
                reason = "automatikus (60 s)"
                try:
                    payload, trace = _do_refresh()
                except Exception as exc:
                    payload = {"ok": False, "status": "error", "display": "Codex: hiba", "message": str(exc)[:200]}
                    trace = get_trace(payload)
                next_time = datetime.fromtimestamp(refresh_time.timestamp() + DEBUG_INTERVAL_SECONDS).astimezone()
                draw()
                continue

            timeout = min(remaining, 0.2)
            try:
                rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            except InterruptedError:
                continue
            except Exception:
                time.sleep(0.2)
                continue

            if rlist:
                try:
                    ch = sys.stdin.read(1)
                except Exception:
                    ch = ""
                if not ch:
                    continue
                if ch == "\x03":
                    break
                if ch in ("q", "Q"):
                    break
                if ch in ("r", "R"):
                    refresh_time = datetime.now().astimezone()
                    reason = "kézi (R)"
                    try:
                        payload, trace = _do_refresh()
                    except Exception as exc:
                        payload = {"ok": False, "status": "error", "display": "Codex: hiba", "message": str(exc)[:200]}
                        trace = get_trace(payload)
                    next_time = datetime.fromtimestamp(refresh_time.timestamp() + DEBUG_INTERVAL_SECONDS).astimezone()
                    draw()
    except KeyboardInterrupt:
        pass
    finally:
        _exit_raw_mode(old_term)
        if use_alt:
            _restore_screen()
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        print("\nKilépés.")
    return 0
