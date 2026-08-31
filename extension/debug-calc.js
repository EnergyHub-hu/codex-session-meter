#!/usr/bin/env node
// debug-calc.js — consumes a helper payload (JSON on stdin) and emits a
// full calculation trace (JSON on stdout) using the same weekly-pace.js
// functions that the GNOME extension uses for display.

import {
    traceCalculateSessionPace,
    traceCalculateWeeklyPace,
    traceElapsedFractionOfConsumptionHorizon,
    traceWeeklyConsumptionPace,
    tracePaceToColor,
    traceSessionPaceColor,
    traceLimitIndicatorColor,
    traceDailyLimitIndicatorLevel,
    traceNormalizePace,
    traceDailyRemainingColor,
} from './weekly-pace.js';

import fs from 'node:fs';

function readStdin() {
    return fs.readFileSync(0, 'utf-8');
}

function safeJsonParse(text) {
    try {
        return JSON.parse(text);
    } catch {
        return {};
    }
}

function buildTrace(payload) {
    const weeklyPercent = payload?.weekly_percent;
    const weeklyUsedPercent = payload?.weekly_used_percent;
    const weeklyResetAt = payload?.weekly_reset_at ?? null;
    const sessionPercent = payload?.session_percent ?? null;
    const sessionUsedPercent = payload?.session_used_percent ?? null;
    const sessionResetAt = payload?.session_reset_at ?? null;
    const sessionWindowMins = payload?.session_window_mins ?? null;
    const lastUpdated = payload?.last_updated ?? null;
    const weeklyWorkdays = payload?.settings?.weekly_workdays ?? 5;
    const ok = payload?.ok ?? false;
    const status = payload?.status ?? 'unknown';
    const sourceLabel = payload?.source_label ?? null;
    const hasLastSuccess = payload?.last_success != null;
    const isStale = hasLastSuccess && !ok;

    // --- Session block ---
    const sessionPaceTrace = traceCalculateSessionPace({
        sessionPercent,
        sessionResetAt,
        lastUpdated,
        sessionWindowMins,
    });
    const sessionPace = sessionPaceTrace.result;
    // session colors: need fallback trace first to reuse boundedPercent for remaining
    const sessionFallbackColorTrace = traceLimitIndicatorColor(sessionPercent);
    // session remaining — reuse trace boundedPercent instead of duplicating clamp formula
    const sessionRemainingRaw = sessionPercent;
    const sessionRemainingClamped = sessionFallbackColorTrace.trace.boundedPercent;
    const sessionRemainingRounded = Number.isFinite(sessionRemainingClamped) ? Math.round(sessionRemainingClamped) : null;

    // Session health color uses the same discrete band mapping as production.
    const sessionPaceColorTrace = sessionPace !== null
        ? traceSessionPaceColor(sessionPace)
        : {result: null, trace: {pace: sessionPace, reason: 'pace is null, no health band color'}};
    const sessionEffectiveColor = sessionPaceColorTrace.result ?? sessionFallbackColorTrace.result;
    const sessionLevelTrace = traceDailyLimitIndicatorLevel(sessionPercent);

    // --- Daily block ---
    // Use traceCalculateWeeklyPace for the EOD-normalized daily remaining + elapsedFraction
    const weeklyPaceTrace = traceCalculateWeeklyPace({
        quotaRemainingPercent: weeklyPercent,
        resetAt: weeklyResetAt,
        lastUpdated,
        workdays: weeklyWorkdays,
    });
    const paceResult = weeklyPaceTrace.result;
    const dailyRemainingPercent = paceResult?.dailyRemainingPercent ?? null;

    const dailyColorTrace = traceDailyRemainingColor(dailyRemainingPercent);
    const dailyFallbackColorTrace = traceLimitIndicatorColor(dailyRemainingPercent);
    const dailyEffectiveColor = dailyColorTrace.result ?? dailyFallbackColorTrace.result;
    const dailyLevelTrace = traceDailyLimitIndicatorLevel(dailyRemainingPercent);

    // --- Weekly block ---
    const weeklyElapsedTrace = traceElapsedFractionOfConsumptionHorizon(weeklyResetAt, lastUpdated, weeklyWorkdays);
    let weeklyPaceTrace2;
    if (weeklyElapsedTrace.result != null && Number.isFinite(weeklyPercent)) {
        weeklyPaceTrace2 = traceWeeklyConsumptionPace({
            quotaRemainingPercent: weeklyPercent,
            elapsedFraction: weeklyElapsedTrace.result,
        });
    } else {
        weeklyPaceTrace2 = {result: null, trace: {reason: 'elapsedFraction or weeklyPercent unavailable', elapsedFraction: weeklyElapsedTrace.result, weeklyPercent}};
    }
    const weeklyPace = weeklyPaceTrace2.result;
    const weeklyPaceColorTrace = tracePaceToColor(weeklyPace);
    const weeklyFallbackColorTrace = traceLimitIndicatorColor(weeklyPercent);
    const weeklyEffectiveColor = weeklyPaceColorTrace.result ?? weeklyFallbackColorTrace.result;
    const weeklyLevelTrace = traceDailyLimitIndicatorLevel(weeklyPercent);

    // Weekly remaining (simple) — reuse fallback trace boundedPercent instead of duplicating clamp
    const weeklyRemainingClamped = weeklyFallbackColorTrace.trace.boundedPercent;
    const weeklyRemainingRounded = Number.isFinite(weeklyRemainingClamped) ? Math.round(weeklyRemainingClamped) : null;

    return {
        _meta: {
            ok,
            status,
            sourceLabel,
            isStale,
            hasLastSuccess,
            lastUpdated,
            weeklyResetAt,
            sessionResetAt,
            sessionWindowMins,
            weeklyWorkdays,
            sessionPercent,
            sessionUsedPercent,
            weeklyPercent,
            weeklyUsedPercent,
        },
        session: {
            input: {
                sessionPercent,
                sessionUsedPercent,
                sessionResetAt,
                sessionWindowMins,
                lastUpdated,
            },
            remaining: {
                raw: sessionRemainingRaw,
                clamped: sessionRemainingClamped,
                rounded: sessionRemainingRounded,
            },
            pace: {
                result: sessionPace,
                trace: sessionPaceTrace.trace,
            },
            paceColor: {
                result: sessionPaceColorTrace.result,
                trace: sessionPaceColorTrace.trace,
                fallback: sessionFallbackColorTrace,
                effective: sessionEffectiveColor,
            },
            indicatorLevel: {
                result: sessionLevelTrace.result,
                trace: sessionLevelTrace.trace,
                fallbackColor: sessionFallbackColorTrace.result,
            },
        },
        daily: {
            input: {
                weeklyPercent,
                weeklyUsedPercent,
                weeklyResetAt,
                lastUpdated,
                weeklyWorkdays,
            },
            weeklyPaceResult: {
                result: paceResult,
                trace: weeklyPaceTrace.trace,
            },
            remaining: {
                result: dailyRemainingPercent,
                trace: weeklyPaceTrace.trace,
            },
            color: {
                result: dailyColorTrace.result,
                trace: dailyColorTrace.trace,
                fallback: dailyFallbackColorTrace,
                effective: dailyEffectiveColor,
            },
            indicatorLevel: {
                result: dailyLevelTrace.result,
                trace: dailyLevelTrace.trace,
                fallbackColor: dailyFallbackColorTrace.result,
            },
        },
        weekly: {
            input: {
                weeklyPercent,
                weeklyUsedPercent,
                weeklyResetAt,
                lastUpdated,
                weeklyWorkdays,
            },
            remaining: {
                raw: weeklyPercent,
                clamped: weeklyRemainingClamped,
                rounded: weeklyRemainingRounded,
            },
            elapsedFraction: {
                result: weeklyElapsedTrace.result,
                trace: weeklyElapsedTrace.trace,
            },
            pace: {
                result: weeklyPace,
                trace: weeklyPaceTrace2.trace,
            },
            paceColor: {
                result: weeklyPaceColorTrace.result,
                trace: weeklyPaceColorTrace.trace,
                fallback: weeklyFallbackColorTrace,
                effective: weeklyEffectiveColor,
            },
            indicatorLevel: {
                result: weeklyLevelTrace.result,
                trace: weeklyLevelTrace.trace,
                fallbackColor: weeklyFallbackColorTrace.result,
            },
        },
        // Raw payload passthrough for freshness checks
        payload,
    };
}

function main() {
    const input = readStdin();
    const payload = input.trim() ? safeJsonParse(input) : {};
    const trace = buildTrace(payload);
    // Use a replacer that handles Infinity / -Infinity
    const json = JSON.stringify(trace, (_key, value) => {
        if (value === Infinity) return '__INFINITY__';
        if (value === -Infinity) return '__NEG_INFINITY__';
        if (Number.isNaN(value)) return '__NAN__';
        return value;
    });
    process.stdout.write(json + '\n');
}

main();
