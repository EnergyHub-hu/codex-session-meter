from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEBUG_INTERVAL_SECONDS = 60

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

def _render_header(payload: dict, trace: dict, refresh_time: datetime, reason: str, next_time: datetime) -> str:
    lines: list[str] = []
    lines.append("Codex Session Meter — Calculation Debug")
    lines.append("=======================================")
    lines.append("")
    # Determine data status
    ok = payload.get("ok")
    has_last = payload.get("last_success") is not None or (trace.get("_meta", {}).get("hasLastSuccess"))
    is_stale = trace.get("_meta", {}).get("isStale") or (not ok and has_last)
    source_label = trace.get("_meta", {}).get("sourceLabel") or payload.get("source_label") or "n/a"
    status = payload.get("status") or trace.get("_meta", {}).get("status") or "unknown"

    if ok:
        data_status = "LIVE"
    elif is_stale:
        data_status = "CACHED / STALE — Live refresh: FAILED"
    else:
        data_status = f"CACHED / STALE — {status}"

    lines.append(f"Frissítés:       {refresh_time.isoformat(timespec='seconds')}")
    lines.append(f"Frissítés oka:   {reason}")
    lines.append(f"Következő:       {next_time.strftime('%H:%M:%S')}  (60 s)")
    lines.append(f"Adatforrás:      {source_label}")
    lines.append(f"Állapot:         {data_status}  (status: {status})")
    if not ok:
        msg = payload.get("message") or ""
        if msg:
            lines.append(f"Üzenet:          {msg[:120]}")
        # show cached timestamp if available
        ls = payload.get("last_success") or {}
        cached_ts = ls.get("last_updated") or (trace.get("payload", {}).get("last_success", {}) or {}).get("last_updated")
        if cached_ts:
            lines.append(f"Cached időpont:  {cached_ts}")
        # if trace has error
        if trace.get("_error"):
            lines.append(f"Hiba:            {trace['_error'][:120]}")
    lines.append("")
    lines.append("Beállítások")
    lines.append("-----------")
    ww = trace.get("_meta", {}).get("weeklyWorkdays", "n/a")
    lines.append(f"Heti munkanapok: {ww}")
    lines.append(f"Debug frissítés: {DEBUG_INTERVAL_SECONDS} s")
    lines.append("")
    lines.append("[R] frissítés most    [Q] kilépés")
    lines.append("")
    return "\n".join(lines)


def _render_session(trace: dict) -> str:
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
    lines.append("1. 5 ÓRÁS SESSION")
    lines.append("=================")
    lines.append("")
    lines.append("INPUT")
    lines.append("-----")
    # Show both used and remaining if available
    if session_used is not None:
        lines.append(f"Codex session usedPercent (helper, kerekített, clampelt): {_fmt_percent(session_used, 2)}")
        lines.append(f"  -> remaining (100 - used) = {_fmt_percent(session_percent, 2) if session_percent is not None else 'n/a'}")
    else:
        lines.append(f"Codex session usedPercent:           n/a")
        lines.append(f"Session remaining (payload session_percent): {_fmt_percent(session_percent, 2)}")
    lines.append(f"Session window:                          {_safe(session_window_mins)} min" + (f"  ({session_window_mins * 60} s)" if isinstance(session_window_mins, (int, float)) else ""))
    lines.append(f"Reset timestamp (session_reset_at):      {_fmt_iso_short(session_reset_at)}")
    if pt.get("resetAtMillis") is not None:
        lines.append(f"  epoch: {_fmt_millis(pt.get('resetAtMillis'))}")
    lines.append(f"Current / lastUpdated:                   {_fmt_iso_short(last_updated)}")
    if pt.get("lastUpdatedMillis") is not None:
        lines.append(f"  epoch: {_fmt_millis(pt.get('lastUpdatedMillis'))}")

    # Detect missing/invalid
    has_valid = pt.get("isSessionPercentFinite") and pt.get("isWindowValid") and pt.get("isResetFinite") and pt.get("isLastUpdatedFinite")
    if not has_valid and session_percent is None:
        lines.append("")
        lines.append("REMAINING % SZÁMÍTÁS")
        lines.append("--------------------")
        lines.append("Session adat nem elérhető (session_percent = n/a).")
        lines.append("A widget ebben az állapotban nem jelenít meg session értéket.")
        lines.append("")
        lines.append("PACE SZÁMÍTÁS")
        lines.append("-------------")
        lines.append("Pace nem számítható (hiányzó bemenet).")
        if pt.get("isSessionPercentFinite") is False:
            lines.append("  sessionPercent nem véges / hiányzik")
        if pt.get("isWindowValid") is False:
            lines.append("  sessionWindowMins hiányzik vagy <= 0")
        if pt.get("isResetFinite") is False:
            lines.append("  sessionResetAt érvénytelen timestamp")
        if pt.get("isLastUpdatedFinite") is False:
            lines.append("  lastUpdated érvénytelen timestamp")
        lines.append("")
        lines.append("COLOR / DISPLAY")
        lines.append("---------------")
        lines.append(f"Indicator level:  {level.get('result', 'n/a')}")
        lines.append(f"Indicator class:  codex-session-daily-limit-{level.get('result', 'n/a')}")
        lines.append(f"Color (fallback, limitIndicatorColor): {_fmt_color(pcolor.get('fallback', {}).get('result') if isinstance(pcolor.get('fallback'), dict) else pcolor.get('effective'))}")
        lines.append(f"Effective dot color:                   {_fmt_color(pcolor.get('effective'))}")
        return "\n".join(lines)

    lines.append("")
    lines.append("REMAINING % SZÁMÍTÁS")
    lines.append("--------------------")
    if session_used is not None and session_percent is not None:
        lines.append(f"Raw used (Codex API usedPercent, helper kerekítve):  {_fmt_percent(session_used, 2)}")
        lines.append(f"Bounded used (clamp [0,100]):                        {_fmt_percent(max(0, min(100, session_used)), 2) if isinstance(session_used, (int, float)) else 'n/a'}")
        lines.append(f"remaining = 100 - bounded_used")
        if isinstance(session_used, (int, float)):
            bounded = max(0, min(100, round(session_used)))
            # payload remaining is 100 - clamp(round(used))
            rem = 100 - bounded
            lines.append(f"         = 100 - {bounded:.2f}")
            lines.append(f"         = {rem:.2f} %")
        lines.append(f"Eredmény (payload session_percent):                   {_fmt_percent(remaining.get('raw'), 2)}")
        lines.append(f"Widget kijelzés (kerekítve):                          {remaining.get('rounded') if remaining.get('rounded') is not None else 'n/a'} %")
    else:
        lines.append(f"Remaining (payload):                 {_fmt_percent(remaining.get('raw'), 2)}")
        lines.append(f"  clamped [0,100]:                   {_fmt_percent(remaining.get('clamped'), 2)}")
        lines.append(f"  kerekítve (widget):                {remaining.get('rounded') if remaining.get('rounded') is not None else 'n/a'} %")

    lines.append("")
    lines.append("PACE SZÁMÍTÁS  —  calculateSessionPace()")
    lines.append("----------------------------------------")
    if pace.get("result") is None:
        lines.append(f"Eredmény:        n/a (null)")
        lines.append(f"Ok:              hiányzó vagy érvénytelen bemenet")
        # Show what we have
        if pt.get("isSessionPercentFinite") is False:
            lines.append("  sessionPercent nem véges")
        if pt.get("isWindowValid") is False:
            lines.append("  sessionWindowMins érvénytelen")
        if pt.get("isResetFinite") is False:
            lines.append("  sessionResetAt érvénytelen timestamp")
        if pt.get("isLastUpdatedFinite") is False:
            lines.append("  lastUpdated érvénytelen timestamp")
    else:
        # Full derivation
        total_millis = pt.get("sessionTotalMillis")
        start_millis = pt.get("sessionStartMillis")
        elapsed_millis = pt.get("elapsedMillis")
        elapsed_mins = pt.get("elapsedMinutes")
        raw_pct = pt.get("timeElapsedPercentRaw")
        clamped_pct = pt.get("timeElapsedPercentClamped")
        raw_pace = pt.get("rawPace")
        clamped_pace = pt.get("clampedPace")

        lines.append(f"Session teljes idő (sessionWindowMins * 60 * 1000):")
        lines.append(f"  {session_window_mins} min * 60 * 1000 = {_safe(total_millis)} ms  ({_fmt_number(total_millis / 60000 if isinstance(total_millis, (int, float)) else None, 2)} min)")
        lines.append("")
        lines.append(f"Session kezdete = reset - duration:")
        if start_millis is not None:
            lines.append(f"  {pt.get('resetAtMillis')} - {total_millis} = {start_millis} ms")
            lines.append(f"  {_fmt_millis(start_millis)}")
        else:
            lines.append(f"  n/a")
        lines.append("")
        lines.append(f"Eltelt idő = lastUpdated - sessionStart:")
        if elapsed_millis is not None:
            lines.append(f"  {pt.get('lastUpdatedMillis')} - {start_millis} = {elapsed_millis} ms")
            if isinstance(elapsed_millis, (int, float)):
                hrs = int(elapsed_millis // 3600000)
                mins = int((elapsed_millis % 3600000) // 60000)
                secs = int((elapsed_millis % 60000) // 1000)
                lines.append(f"  = {hrs}ó {mins}p {secs}mp  ({_fmt_number(elapsed_mins, 2)} min)")
        lines.append("")
        lines.append(f"Eltelt idő aránya:")
        lines.append(f"  elapsed / total * 100")
        if raw_pct is not None:
            lines.append(f"  = {elapsed_millis} / {total_millis} * 100")
            lines.append(f"  = {_fmt_number(raw_pct, 6)} %  (raw)")
            lines.append(f"  clamp [0,100] -> {_fmt_percent(clamped_pct, 4)}")
        lines.append("")
        lines.append(f"Remaining:                         {_fmt_percent(session_percent, 2)}")
        lines.append(f"Raw pace = remaining - elapsedPct:")
        if raw_pace is not None:
            lines.append(f"        = {_fmt_number(session_percent, 2)} - {_fmt_number(clamped_pct, 4)}")
            lines.append(f"        = {_fmt_number(raw_pace, 4)}")
            lines.append(f"Clamp [-100, +100] ->              {_fmt_number(clamped_pace, 2)}")
        lines.append(f"Final pace:                        {_fmt_number(pace.get('result'), 2)}")

    lines.append("")
    lines.append("COLOR / DISPLAY")
    lines.append("---------------")
    pcolor_trace = pcolor.get("trace") or {}
    fallback = pcolor.get("fallback") if isinstance(pcolor.get("fallback"), dict) else {}
    if pace.get("result") is not None:
        norm = pcolor_trace.get("normalizeTrace") or {}
        lines.append(f"Pace input:                        {_fmt_number(pace.get('result'), 2)}")
        lines.append(f"Color normalization (paceColor, min=-100, max=+100):")
        lines.append(f"  clamp [{-100}, {100}] -> {_fmt_number(pcolor_trace.get('normalizeTrace', {}).get('clamped') if isinstance(pcolor_trace.get('normalizeTrace'), dict) else 'n/a', 2)}")
        lines.append(f"  normalized = (clamped - min)/(max-min)*100 = {_fmt_number(pcolor_trace.get('normalized'), 4)} %")
        if pcolor_trace.get("selectedIndex") is not None:
            lines.append(f"  PACE_COLOR_STOPS intervallum: index {pcolor_trace.get('selectedIndex')}  [{pcolor_trace.get('lowerPercent')}%, {pcolor_trace.get('upperPercent')}%]")
            lines.append(f"  Alsó szín: {_fmt_color(pcolor_trace.get('lowerColor'))}  Felső szín: {_fmt_color(pcolor_trace.get('upperColor'))}")
            lines.append(f"  ratio = (norm - lower)/(upper-lower) = {_fmt_number(pcolor_trace.get('ratio'), 6)}")
            lines.append(f"  Interpolált RGB: {pcolor_trace.get('interpolatedRgb')}")
        lines.append(f"Selected / interpolated:           {_fmt_color(pcolor.get('result'))}")
        lines.append(f"Fallback (limitIndicatorColor):    {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else 'n/a')}")
        lines.append(f"Effective dot color:               {_fmt_color(pcolor.get('effective'))}")
    else:
        lines.append(f"Pace:                              n/a (null)")
        lines.append(f"Fallback color (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else _fmt_color(pcolor.get('effective')))}")
        lines.append(f"Effective dot color:               {_fmt_color(pcolor.get('effective'))}")
    lines.append(f"Indicator remaining:               {_fmt_percent(session_percent, 2)}")
    lines.append(f"Indicator class:                   codex-session-daily-limit-{level.get('result', 'n/a')}")
    if level.get("trace"):
        lt = level["trace"]
        lines.append(f"  input={_fmt_percent(lt.get('input'),2)}, isOver100={lt.get('isOver100')}, clamped={_safe(lt.get('clamped'))}, rounded={_safe(lt.get('rounded'))}")

    return "\n".join(lines)


def _render_daily(trace: dict) -> str:
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
    # weeklyPaceTrace details
    wt = wpr_trace

    lines: list[str] = []
    lines.append("2. NAPI KERET")
    lines.append("=============")
    lines.append("")
    lines.append("INPUT")
    lines.append("-----")
    lines.append(f"Weekly remaining (payload weekly_percent):     {_fmt_percent(weekly_percent, 2)}")
    if weekly_used is not None:
        lines.append(f"Weekly used (helper clamped):                  {_fmt_percent(weekly_used, 2)}")
    lines.append(f"Configured workdays (weekly_workdays):          {_safe(workdays)}")
    lines.append(f"Weekly reset (weekly_reset_at):                {_fmt_iso_short(weekly_reset_at)}")
    if wt.get("resetAtMillis") is not None:
        lines.append(f"  epoch: {_fmt_millis(wt.get('resetAtMillis'))}")
    lines.append(f"Current / lastUpdated:                         {_fmt_iso_short(last_updated)}")
    if wt.get("lastUpdatedMillis") is not None:
        lines.append(f"  epoch: {_fmt_millis(wt.get('lastUpdatedMillis'))}")
    lines.append(f"Budget / workday = 100 / workdays:              {_fmt_number(wt.get('fullDayBudget'), 4) if wt.get('fullDayBudget') is not None else 'n/a'} pp")
    if wt.get("isIncomplete"):
        lines.append("")
        lines.append("REMAINING % SZÁMÍTÁS")
        lines.append("--------------------")
        lines.append("Napi keret nem számítható (hiányzó bemenet).")
        lines.append(f"  isQuotaFinite={wt.get('isQuotaFinite')}, isResetFinite={wt.get('isResetFinite')}, isLastUpdatedFinite={wt.get('isLastUpdatedFinite')}")
        lines.append("")
        lines.append("PACE SZÁMÍTÁS")
        lines.append("-------------")
        lines.append("Pace nem számítható (hiányzó daily elapsedFraction).")
        lines.append("")
        lines.append("COLOR / DISPLAY")
        lines.append("---------------")
        lines.append(f"Indicator level:  {level.get('result', 'n/a')}")
        lines.append(f"Effective color:  {_fmt_color(pcolor.get('effective'))}")
        return "\n".join(lines)

    lines.append("")
    lines.append("Idő-számítás részletei (calculateWeeklyPace belső):")
    lines.append("---------------------------------------------------")
    lines.append(f"WeeklyStart = reset - 7 nap:")
    if wt.get("weeklyStartMillis") is not None:
        lines.append(f"  {wt.get('resetAtMillis')} - 7*86400000 = {wt.get('weeklyStartMillis')} ms")
        lines.append(f"  {_fmt_millis(wt.get('weeklyStartMillis'))}")
    lines.append(f"Consumption horizon = weeklyStart + workdays * 24h:")
    if wt.get("consumptionHorizonMillis") is not None:
        lines.append(f"  {wt.get('weeklyStartMillis')} + {workdays}*86400000 = {wt.get('consumptionHorizonMillis')} ms")
        lines.append(f"  {_fmt_millis(wt.get('consumptionHorizonMillis'))}")
    lines.append(f"FullDayBudget = 100 / {workdays} = {_fmt_number(wt.get('fullDayBudget'), 4)} pp")
    lines.append("")
    lines.append(f"lastUpdatedDate:                   {_safe(wt.get('lastUpdatedDate'))}")
    if wt.get("localToday00") is not None:
        lines.append(f"localToday00 (helyi éjfél):        {_fmt_millis(wt.get('localToday00'))}")
        # Show how it's computed: new Date(y,m,d,0,0,0,0)
        try:
            d_obj = wt.get("lastUpdatedDate")
            # d_obj is a Date string representation; show epoch directly
        except Exception:
            pass
    if wt.get("localNextDay00") is not None:
        lines.append(f"localNextDay00 (következő éjfél):  {_fmt_millis(wt.get('localNextDay00'))}")
    if wt.get("effectiveDayStart") is not None:
        lines.append(f"effectiveDayStart = max(localToday00, weeklyStart) = {wt.get('effectiveDayStart')} ms")
        lines.append(f"  {_fmt_millis(wt.get('effectiveDayStart'))}")
    if wt.get("effectiveDayEnd") is not None:
        lines.append(f"effectiveDayEnd = min(localNextDay00, horizon) = {wt.get('effectiveDayEnd')} ms")
        lines.append(f"  {_fmt_millis(wt.get('effectiveDayEnd'))}")
    if wt.get("todayDuration") is not None:
        lines.append(f"todayDuration = max(0, end - start) = {wt.get('todayDuration')} ms  ({_fmt_number(wt.get('todayDurationHours'), 4)} h)")
    if wt.get("todayBudget") is not None:
        lines.append(f"todayBudget = todayDuration/DAY * fullDayBudget = {_fmt_number(wt.get('todayDuration'), 2)} / 86400000 * {_fmt_number(wt.get('fullDayBudget'), 4)} = {_fmt_number(wt.get('todayBudget'), 6)} pp")

    lines.append("")
    lines.append("REMAINING % SZÁMÍTÁS  —  EOD-normalizált napi maradék")
    lines.append("-----------------------------------------------")
    lines.append(f"Weekly bounded remaining (clamp [0,100]):     {_fmt_percent(wt.get('boundedQuotaRemainingPercent'), 2)}")
    if wt.get("nextDayCapped") is not None:
        lines.append(f"nextDayCapped = min(localNextDay00, horizon) = {wt.get('nextDayCapped')} ms")
    if wt.get("allowedByEOD") is not None:
        lines.append(f"allowedByEOD = (nextDayCapped - weeklyStart)/(workdays*DAY)*100")
        if wt.get("weeklyStartMillis") is not None and wt.get("nextDayCapped") is not None:
            lines.append(f"  = ({wt.get('nextDayCapped')} - {wt.get('weeklyStartMillis')}) / ({workdays}*86400000) * 100")
            lines.append(f"  = {_fmt_percent(wt.get('allowedByEOD'), 4)}")
    if wt.get("actualUsage") is not None:
        lines.append(f"actualUsage = 100 - boundedRemaining = 100 - {_fmt_number(wt.get('boundedQuotaRemainingPercent'), 2)} = {_fmt_number(wt.get('actualUsage'), 4)} pp")
    if wt.get("available") is not None:
        lines.append(f"available = allowedByEOD - actualUsage = {_fmt_number(wt.get('allowedByEOD'), 4)} - {_fmt_number(wt.get('actualUsage'), 4)} = {_fmt_number(wt.get('available'), 4)} pp")
    if wt.get("divisor") is not None:
        lines.append(f"divisor = todayBudget > 0 ? todayBudget : fullDayBudget = {_fmt_number(wt.get('divisor'), 6)} pp")
    lines.append(f"dailyRemainingPercent = available / divisor * 100")
    if daily_remaining is not None:
        lines.append(f"  = {_fmt_number(wt.get('available'), 4)} / {_fmt_number(wt.get('divisor'), 6)} * 100")
        lines.append(f"  = {_fmt_number(daily_remaining, 4)} %  (raw, nincs clamp!)")
        if daily_remaining > 100:
            lines.append(f"  -> >100 % : előtakarékosság (kevesebb fogyott, mint tervezett)")
        elif daily_remaining < 0:
            lines.append(f"  -> <0 % : túlfogyasztás (több fogyott, mint az EOD-keret)")
    else:
        lines.append(f"  = n/a")
    lines.append(f"Eredmény (dailyRemainingPercent):             {_fmt_number(daily_remaining, 4) if daily_remaining is not None else 'n/a'} %")
    if daily_remaining is not None:
        lines.append(f"Widget kijelzés (kerekítve):                  {round(daily_remaining)} %")
        lines.append(f"Indicator-level input (raw):                  {_fmt_percent(daily_remaining, 2)}")
        lines.append(f"Indicator class:                              codex-session-daily-limit-{level.get('result', 'n/a')}")
    # also show elapsedFraction etc.
    if wt.get("elapsedFraction") is not None:
        lines.append(f"elapsedMillis = max(0, lastUpdated - weeklyStart) = {wt.get('elapsedMillis')} ms")
        lines.append(f"elapsedFraction = min(1, elapsedMillis/(workdays*DAY)) = {_fmt_number(wt.get('elapsedFraction'), 6)}")
        lines.append(f"  = {wt.get('elapsedMillis')} / {workdays * 86400000} = {_fmt_number(wt.get('elapsedFraction'), 6)}")
        lines.append(f"elapsedWorkdays = elapsedFraction * workdays = {_fmt_number(wt.get('elapsedWorkdays'), 4)}")
        lines.append(f"todayMinimumRemainingPercent = max(0, 100 - elapsedWorkdays*fullDayBudget) = {_fmt_number(wt.get('todayMinimumRemainingPercent'), 4)} %")

    lines.append("")
    lines.append("PACE SZÁMÍTÁS  —  dailyConsumptionPace()  [napi pont színe]")
    lines.append("-----------------------------------------------------------")
    lines.append("A napi pont színe NEM a napi remaining-ből jön, hanem külön pace-ből:")
    lines.append("  dailyPace = actualUsage / expectedUsage")
    lines.append("  actualUsage   = 100 - weeklyPercent")
    lines.append("  expectedUsage = elapsedFraction(daily) * 100")
    pt = pace.get("trace") or {}
    if pace.get("result") is None:
        lines.append(f"Eredmény:   n/a (null)")
        if pt.get("reason"):
            lines.append(f"Ok:       {pt.get('reason')}")
        elif pt.get("isActualFinite") is False or pt.get("isExpectedFinite") is False:
            lines.append(f"Ok:       nem véges bemenet")
    else:
        lines.append(f"actualUsage   = 100 - {_fmt_number(weekly_percent, 2)} = {_fmt_number(pt.get('actualUsage'), 4)} pp")
        lines.append(f"expectedUsage = elapsedFraction * 100 = {_fmt_number(wt.get('elapsedFraction'), 6)} * 100 = {_fmt_number(pt.get('expectedUsage'), 4)} pp")
        if pt.get("isZeroZero"):
            lines.append(f"Speciális: expected=0 és actual=0  -> pace = 1.0 (pontosan terv szerint)")
        elif pt.get("isInfiniteCase"):
            lines.append(f"Speciális: expected=0 de actual>0  -> pace = ∞ (idő előtt fogyott)")
            lines.append(f"  actualUsage={_fmt_number(pt.get('actualUsage'),4)} > 0, expectedUsage=0")
        else:
            lines.append(f"Raw pace = actual / expected = {_fmt_number(pt.get('actualUsage'), 4)} / {_fmt_number(pt.get('expectedUsage'), 4)} = {_fmt_number(pt.get('ratio'), 6)}")
        lines.append(f"Final pace:                              {_fmt_number(pace.get('result'), 6)}×")
        lines.append(f"  1.00 = terv szerinti ütem")
        lines.append(f"  <1.00 = lassabb a tervnél (kíméled a keretet)")
        lines.append(f"  >1.00 = gyorsabb a tervnél (gyorsabban fogy)")
        if isinstance(pace.get("result"), float) and math.isinf(pace.get("result")):
            lines.append(f"  ∞ = végtelen: nulla idő alatt már fogyott")
    lines.append("")
    lines.append("COLOR / DISPLAY  —  paceToColor()  küszöbök")
    lines.append("-------------------------------------------")
    pct = pcolor.get("trace") or {}
    fallback = pcolor.get("fallback") if isinstance(pcolor.get("fallback"), dict) else {}
    if pace.get("result") is None:
        lines.append(f"Pace:                    n/a")
        lines.append(f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else pcolor.get('effective'))}")
    else:
        lines.append(f"Pace input:              {_fmt_number(pace.get('result'), 6)}")
        if pct.get("selectedThreshold") is not None:
            thr = pct.get("selectedThreshold")
            # Find which band
            bands = [
                (0.80, "#15803D", "zöld (lassú / takarékos)"),
                (0.94, "#84CC16", "világoszöld"),
                (1.05, "#FACC15", "sárga (terv közelében)"),
                (1.25, "#EA580C", "narancs (gyors)"),
                (float("inf"), "#B91C1C", "piros (kritikus)"),
            ]
            band_label = ""
            for b_thr, b_col, b_label in bands:
                if pace.get("result") <= b_thr:
                    band_label = b_label
                    break
            lines.append(f"Threshold értékelés:")
            for b_thr, b_col, b_label in bands:
                marker = " ← kiválasztott" if b_col == pct.get("selectedColor") else ""
                thr_str = "∞" if math.isinf(b_thr) else f"{b_thr:.2f}"
                lines.append(f"  pace <= {thr_str}  -> {b_col}  {b_label}{marker}")
            lines.append(f"Selected band küszöb:     {thr if not math.isinf(thr) else '∞'}")
        lines.append(f"Selected color:            {_fmt_color(pcolor.get('result'))}")
        lines.append(f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else 'n/a')}")
        lines.append(f"Effective dot color:       {_fmt_color(pcolor.get('effective'))}")
        # Show that Infinity returns null for paceToColor
        if isinstance(pace.get("result"), float) and math.isinf(pace.get("result")):
            lines.append(f"Megjegyzés: pace=∞ -> paceToColor(null) -> fallback szín érvényesül")
    lines.append(f"Indicator remaining:       {_fmt_percent(daily_remaining, 2) if daily_remaining is not None else 'n/a'}")
    lines.append(f"Indicator class:           codex-session-daily-limit-{level.get('result', 'n/a')}")

    return "\n".join(lines)


def _render_weekly(trace: dict) -> str:
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
    lines.append("3. HETI KERET")
    lines.append("=============")
    lines.append("")
    lines.append("INPUT")
    lines.append("-----")
    if weekly_used is not None:
        lines.append(f"Codex weekly usedPercent (helper, kerekített, clampelt): {_fmt_percent(weekly_used, 2)}")
        lines.append(f"  -> remaining (100 - used) = {_fmt_percent(weekly_percent, 2) if weekly_percent is not None else 'n/a'}")
    else:
        lines.append(f"Weekly remaining (payload weekly_percent):       {_fmt_percent(weekly_percent, 2)}")
    lines.append(f"Weekly reset (weekly_reset_at):                {_fmt_iso_short(weekly_reset_at)}")
    if et.get("resetAtMillis") is not None:
        lines.append(f"  epoch: {_fmt_millis(et.get('resetAtMillis'))}")
    lines.append(f"Current / lastUpdated:                         {_fmt_iso_short(last_updated)}")
    if et.get("lastUpdatedMillis") is not None:
        lines.append(f"  epoch: {_fmt_millis(et.get('lastUpdatedMillis'))}")

    lines.append("")
    lines.append("REMAINING % SZÁMÍTÁS")
    lines.append("--------------------")
    if weekly_percent is None or not isinstance(weekly_percent, (int, float)):
        lines.append(f"Weekly remaining:  n/a (weeklyPercent nem véges)")
    else:
        if weekly_used is not None:
            lines.append(f"API usedPercent (helper kerekítve/clampelve):  {_fmt_percent(weekly_used, 2)}")
            bounded = max(0, min(100, round(weekly_used)) if isinstance(weekly_used, (int, float)) else weekly_used)
            lines.append(f"  rounded: {_safe(round(weekly_used)) if isinstance(weekly_used, (int,float)) else 'n/a'}, clamped [0,100]: {_fmt_percent(bounded,2) if isinstance(bounded,(int,float)) else 'n/a'}")
            lines.append(f"remaining = 100 - bounded_used = 100 - {_safe(bounded)} = {_fmt_percent(remaining.get('raw'), 2)}")
        else:
            lines.append(f"remaining = 100 - used (közvetlen payload weekly_percent): {_fmt_percent(remaining.get('raw'), 2)}")
        lines.append(f"Raw remaining:                               {_fmt_percent(remaining.get('raw'), 2)}")
        lines.append(f"Clamped [0,100]:                             {_fmt_percent(remaining.get('clamped'), 2)}")
        lines.append(f"Rounded / widget kijelzés:                   {remaining.get('rounded') if remaining.get('rounded') is not None else 'n/a'} %")
        lines.append(f"Widget panel:                                {remaining.get('rounded') if remaining.get('rounded') is not None else 'n/a'}%")

    lines.append("")
    lines.append("PACE SZÁMÍTÁS  —  weeklyConsumptionPace() / elapsedFractionOfWeek()")
    lines.append("--------------------------------------------------------------------")
    lines.append("Heti pace = actualUsage / expectedUsage")
    lines.append("  actualUsage   = 100 - weeklyPercent")
    lines.append("  expectedUsage = elapsedFractionOfWeek * 100")
    lines.append("  elapsedFractionOfWeek = elapsedMillis / (7*DAY)  [7 napos ablak]")
    lines.append("")
    if et.get("isResetFinite") is False or et.get("isLastUpdatedFinite") is False:
        lines.append(f"elapsedFraction:  n/a (érvénytelen timestamp)")
        lines.append(f"  resetAtMillis finite={et.get('isResetFinite')}, lastUpdatedMillis finite={et.get('isLastUpdatedFinite')}")
    elif elapsed.get("result") is None:
        lines.append(f"elapsedFraction:  n/a")
        if et.get("reason"):
            lines.append(f"  ok: {et.get('reason')}")
    else:
        lines.append(f"elapsedFraction számítás (elapsedFractionOfWeek):")
        lines.append(f"  resetAtMillis:     {et.get('resetAtMillis')}  ({_fmt_millis(et.get('resetAtMillis'))})")
        lines.append(f"  windowStart = reset - 7 nap = {et.get('windowStartMillis')} ms")
        lines.append(f"    {_fmt_millis(et.get('windowStartMillis'))}")
        lines.append(f"  elapsedMillis = max(0, lastUpdated - windowStart) = {et.get('elapsedMillis')} ms")
        if isinstance(et.get('elapsedMillis'), (int, float)):
            hrs = et.get('elapsedMillis') / 3600000
            days = et.get('elapsedMillis') / 86400000
            lines.append(f"    = {_fmt_number(hrs, 2)} h  ({_fmt_number(days, 4)} nap)")
        lines.append(f"  weekMillis = 7 * 86400000 = {et.get('weekMillis')} ms")
        lines.append(f"  rawFraction = elapsed / weekMillis = {_fmt_number(et.get('rawFraction'), 6)}")
        lines.append(f"  clamped [0,1] = min(1, raw) = {_fmt_number(et.get('clampedFraction'), 6)}")
        lines.append(f"  Final elapsedFraction:         {_fmt_number(elapsed.get('result'), 6)}  ({_fmt_percent(elapsed.get('result') * 100 if isinstance(elapsed.get('result'), (int,float)) else None, 2)})")
        lines.append("")
        if pace.get("result") is None:
            lines.append(f"weeklyConsumptionPace:  n/a")
            if pt.get("reason"):
                lines.append(f"  ok: {pt.get('reason')}")
        else:
            lines.append(f"actualUsage   = 100 - {_fmt_number(weekly_percent,2)} = {_fmt_number(pt.get('actualUsage'), 4)} pp")
            lines.append(f"expectedUsage = elapsedFraction * 100 = {_fmt_number(elapsed.get('result'),6)} * 100 = {_fmt_number(pt.get('expectedUsage'), 4)} pp")
            dpt = pt.get("dailyPaceTrace") or {}
            if dpt.get("isZeroZero"):
                lines.append(f"Speciális: expected=0 és actual=0 -> pace=1.0")
            elif dpt.get("isInfiniteCase"):
                lines.append(f"Speciális: expected=0 de actual>0 -> pace=∞")
                lines.append(f"  actualUsage={_fmt_number(pt.get('actualUsage'),4)} > 0, expectedUsage=0")
            else:
                lines.append(f"Raw pace = actual / expected = {_fmt_number(pt.get('actualUsage'),4)} / {_fmt_number(pt.get('expectedUsage'),4)} = {_fmt_number(pt.get('ratio') if 'ratio' in dpt else pace.get('result'), 6)}")
            lines.append(f"Final weekly pace:           {_fmt_number(pace.get('result'), 6)}×")
            if isinstance(pace.get("result"), float) and math.isinf(pace.get("result")):
                lines.append(f"  ∞ = végtelen: a hét elején már fogyott a keret")
            else:
                lines.append(f"  1.00 = terv szerinti ütem (7 napos ablak)")
                lines.append(f"  <1.00 = lassabb a tervnél")
                lines.append(f"  >1.00 = gyorsabb a tervnél")

    lines.append("")
    lines.append("COLOR / DISPLAY  —  paceToColor()  küszöbök")
    lines.append("-------------------------------------------")
    pct = pcolor.get("trace") or {}
    fallback = pcolor.get("fallback") if isinstance(pcolor.get("fallback"), dict) else {}
    if pace.get("result") is None:
        lines.append(f"Pace:                    n/a")
        lines.append(f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else pcolor.get('effective'))}")
    else:
        if isinstance(pace.get("result"), float) and math.isinf(pace.get("result")):
            lines.append(f"Pace input:              ∞")
            lines.append(f"paceToColor(∞) -> null (nem véges) -> fallback szín érvényesül")
            lines.append(f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else 'n/a')}")
            lines.append(f"Effective dot color:       {_fmt_color(pcolor.get('effective'))}")
        else:
            lines.append(f"Pace input:              {_fmt_number(pace.get('result'),6)}")
            if pct.get("selectedThreshold") is not None:
                thr = pct.get("selectedThreshold")
                bands = [
                    (0.80, "#15803D", "zöld (lassú / takarékos)"),
                    (0.94, "#84CC16", "világoszöld"),
                    (1.05, "#FACC15", "sárga (terv közelében)"),
                    (1.25, "#EA580C", "narancs (gyors)"),
                    (float("inf"), "#B91C1C", "piros (kritikus)"),
                ]
                lines.append(f"Threshold értékelés:")
                for b_thr, b_col, b_label in bands:
                    marker = " ← kiválasztott" if b_col == pct.get("selectedColor") else ""
                    thr_str = "∞" if math.isinf(b_thr) else f"{b_thr:.2f}"
                    lines.append(f"  pace <= {thr_str}  -> {b_col}  {b_label}{marker}")
                lines.append(f"Selected band küszöb:     {thr if not math.isinf(thr) else '∞'}")
            lines.append(f"Selected color:            {_fmt_color(pcolor.get('result'))}")
            lines.append(f"Fallback (limitIndicatorColor): {_fmt_color(fallback.get('result') if isinstance(fallback, dict) else 'n/a')}")
            lines.append(f"Effective dot color:       {_fmt_color(pcolor.get('effective'))}")
    lines.append(f"Indicator remaining:       {_fmt_percent(weekly_percent,2) if weekly_percent is not None else 'n/a'}")
    lines.append(f"Indicator class:           codex-session-daily-limit-{level.get('result', 'n/a')}")

    return "\n".join(lines)


def _render_summary(trace: dict) -> str:
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
    lines.append("ÖSSZEFOGLALÓ")
    lines.append("============")
    lines.append("")
    lines.append(f"{'':<22} {'Remaining':<14} {'Pace':<14} {'Color'}")
    lines.append(f"{'5 órás session':<22} {fmt_rem(s_rem):<14} {fmt_pace_session(s_pace):<14} {s_color or 'n/a'}")
    # daily remaining may be float not rounded int
    d_rem_str = fmt_rem(d_rem) if d_rem is not None else "n/a"
    lines.append(f"{'Napi keret':<22} {d_rem_str:<14} {fmt_pace(d_pace):<14} {d_color or 'n/a'}")
    lines.append(f"{'Heti keret':<22} {fmt_rem(w_rem):<14} {fmt_pace(w_pace):<14} {w_color or 'n/a'}")
    lines.append("")
    # Panel equivalent
    panel_parts: list[str] = []
    sess_label = f"{round(s_rem)}% ({s.get('input', {}).get('sessionResetAt', '')[11:16] if s.get('input', {}).get('sessionResetAt') else ''})" if s_rem is not None else "–"
    # Actually use compactPanelComponents logic: session with reset time, daily %, weekly with date
    # For panel equivalent, mimic extension's compactPanelComponents output
    session_comp = f"{round(s_rem)}% ({s.get('input', {}).get('sessionResetAt', '')[11:16]})" if s_rem is not None and s.get("input", {}).get("sessionResetAt") else (f"{round(s_rem)}%" if s_rem is not None else "–")
    daily_comp = f"{round(d_rem)}%" if d_rem is not None else "–"
    # weekly reset date: MM.DD.
    w_reset = w.get("input", {}).get("weeklyResetAt") or ""
    weekly_date = ""
    if w_reset:
        try:
            dt = datetime.fromisoformat(w_reset.replace("Z", "+00:00"))
            weekly_date = dt.strftime("%m.%d.")
        except Exception:
            weekly_date = ""
    weekly_comp = f"{round(w_rem)}% ({weekly_date})" if w_rem is not None and weekly_date else (f"{round(w_rem)}%" if w_rem is not None else "–")

    lines.append("Panel equivalent (widget):")
    lines.append(f"  Session: {session_comp}  |  Daily: {daily_comp}  |  Weekly: {weekly_comp}")
    if s_color or d_color or w_color:
        lines.append(f"  Színek: session={s_color or 'n/a'}  daily={d_color or 'n/a'}  weekly={w_color or 'n/a'}")
    return "\n".join(lines)


def render_screen(payload: dict, trace: dict, refresh_time: datetime, reason: str, next_time: datetime) -> str:
    parts: list[str] = []
    parts.append(_render_header(payload, trace, refresh_time, reason, next_time))
    parts.append(_render_session(trace))
    parts.append("")
    parts.append(_render_daily(trace))
    parts.append("")
    parts.append(_render_weekly(trace))
    parts.append("")
    parts.append(_render_summary(trace))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Interactive loop
# ---------------------------------------------------------------------------

def _do_refresh() -> tuple[dict, dict]:
    """Perform a live refresh and build trace. Returns (payload, trace)."""
    from .fetcher import refresh_status
    payload = refresh_status()
    # If payload has last_success fallback, the actual live data may be inside it,
    # but trace should reflect the effective displayed values.
    # Use the payload itself (which may contain last_success). For LIVE data,
    # payload is the fresh one. For FAILED, payload contains last_success.
    # The trace should be built from the effective payload that the widget would show.
    # If ok==False and last_success exists, use last_success for calculations but keep status as CACHED.
    effective = payload
    if not payload.get("ok") and payload.get("last_success"):
        # For calculations, use last_success values but preserve freshness info
        effective = {**payload["last_success"], "ok": payload["ok"], "status": payload["status"], "message": payload.get("message"), "last_success": payload["last_success"], "source_label": payload.get("source_label")}
        # But for trace, we want to show what the widget displays (cached data)
        # So build trace from last_success's data fields
        trace_payload = {**payload["last_success"]}
        # Keep the freshness markers
        trace_payload["_freshness_ok"] = payload["ok"]
        trace_payload["_freshness_status"] = payload["status"]
        trace = get_trace(trace_payload)
        # Patch _meta to reflect stale
        if "_meta" in trace:
            trace["_meta"]["ok"] = payload["ok"]
            trace["_meta"]["status"] = payload["status"]
            trace["_meta"]["isStale"] = True
            trace["_meta"]["hasLastSuccess"] = True
        # Keep payload as original for header
        return payload, trace
    trace = get_trace(effective)
    return payload, trace

def _clear_screen() -> None:
    # Use ANSI: clear screen + move cursor home
    sys.stdout.write("\033[H\033[2J")
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

def run_debug() -> int:
    """Entry point for `codex-session-meter debug`."""
    import select

    # Initial refresh
    refresh_time = datetime.now().astimezone()
    reason = "indítás"
    try:
        payload, trace = _do_refresh()
    except Exception as exc:
        payload = {"ok": False, "status": "error", "display": "Codex: hiba", "message": str(exc)[:200]}
        trace = get_trace(payload)

    next_time = datetime.fromtimestamp(refresh_time.timestamp() + DEBUG_INTERVAL_SECONDS).astimezone()

    # Check if stdin is a tty
    is_tty = sys.stdin.isatty()

    def draw() -> None:
        _clear_screen()
        screen = render_screen(payload, trace, refresh_time, reason, next_time)
        sys.stdout.write(screen + "\n")
        sys.stdout.flush()

    if not is_tty:
        # Non-interactive: just render once and exit
        draw()
        return 0

    old_term = _enter_raw_mode()
    try:
        draw()
        while True:
            now = time.monotonic()
            deadline = refresh_time.timestamp() + DEBUG_INTERVAL_SECONDS
            remaining = deadline - time.time()
            if remaining <= 0:
                # Auto refresh
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

            # Wait for key with timeout
            timeout = min(remaining, 0.2)
            try:
                rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            except InterruptedError:
                continue
            except Exception:
                # Fallback: sleep
                time.sleep(0.2)
                continue

            if rlist:
                try:
                    ch = sys.stdin.read(1)
                except Exception:
                    ch = ""
                if not ch:
                    continue
                # Handle Ctrl+C (0x03), q, Q, r, R
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
        # Clear raw artifacts and show cursor
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        # Print exit message in cooked mode
        print("\nKilépés.")
    return 0
