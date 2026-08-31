const DAY_MILLIS = 24 * 60 * 60 * 1000;

function weekStartMillis(resetAtMillis) {
    return resetAtMillis - 7 * DAY_MILLIS;
}

function localMidnightEpochMillis(date) {
    return new Date(
        date.getFullYear(),
        date.getMonth(),
        date.getDate(),
        0, 0, 0, 0
    ).getTime();
}

function nextLocalMidnightEpochMillis(date) {
    return new Date(
        date.getFullYear(),
        date.getMonth(),
        date.getDate() + 1,
        0, 0, 0, 0
    ).getTime();
}

function localDayBounds(epochMillis) {
    const date = new Date(epochMillis);
    const startMillis = localMidnightEpochMillis(date);
    const endMillis = nextLocalMidnightEpochMillis(date);
    return {
        startMillis,
        endMillis,
        durationMillis: endMillis - startMillis,
    };
}

function addLocalCalendarDaysMillis(epochMillis, days) {
    const date = new Date(epochMillis);
    return new Date(
        date.getFullYear(),
        date.getMonth(),
        date.getDate() + days,
        date.getHours(),
        date.getMinutes(),
        date.getSeconds(),
        date.getMilliseconds()
    ).getTime();
}

function localCalendarDayUnitsBetween(startMillis, endMillis) {
    if (!Number.isFinite(startMillis) || !Number.isFinite(endMillis))
        return null;
    if (endMillis <= startMillis)
        return 0;
    let cursor = startMillis;
    let units = 0;
    while (cursor < endMillis) {
        const bounds = localDayBounds(cursor);
        const segmentEnd = Math.min(endMillis, bounds.endMillis);
        units += (segmentEnd - cursor) / bounds.durationMillis;
        cursor = segmentEnd;
    }
    return units;
}
const LIMIT_COLOR_STOPS = [
    [0, '#B91C1C'],
    [25, '#EA580C'],
    [50, '#FACC15'],
    [75, '#A3E635'],
    [100, '#22C55E'],
];
const PACE_COLOR_STOPS = [
    [0, '#991B1B'],
    [17, '#DC2626'],
    [33, '#F97316'],
    [50, '#FACC15'],
    [67, '#84CC16'],
    [83, '#22C55E'],
    [100, '#15803D'],
];
export const DAILY_REMAINING_MIN = -100;
export const DAILY_REMAINING_MAX = 200;
export const DAILY_PACE_MIN = DAILY_REMAINING_MIN;
export const DAILY_PACE_MAX = DAILY_REMAINING_MAX;
export const SESSION_PACE_MIN = -100;
export const SESSION_PACE_MAX = 100;

// ---------------------------------------------------------------------------
// dailyLimitIndicatorLevel — shared internal
// ---------------------------------------------------------------------------
function _dailyLimitIndicatorLevelInternal(dailyRemainingPercent) {
    const trace = {
        input: dailyRemainingPercent,
        isFinite: Number.isFinite(dailyRemainingPercent),
        isOver100: Number.isFinite(dailyRemainingPercent) ? dailyRemainingPercent > 100 : null,
        clamped: null,
        rounded: null,
        result: null,
    };
    if (!Number.isFinite(dailyRemainingPercent)) {
        trace.result = 'unknown';
        return {result: trace.result, trace};
    }
    if (dailyRemainingPercent > 100) {
        trace.result = 'over';
        return {result: trace.result, trace};
    }
    trace.clamped = Math.max(0, dailyRemainingPercent);
    trace.rounded = Math.round(trace.clamped);
    trace.result = String(trace.rounded);
    return {result: trace.result, trace};
}

export function dailyLimitIndicatorLevel(dailyRemainingPercent) {
    return _dailyLimitIndicatorLevelInternal(dailyRemainingPercent).result;
}

export function traceDailyLimitIndicatorLevel(dailyRemainingPercent) {
    return _dailyLimitIndicatorLevelInternal(dailyRemainingPercent);
}

// ---------------------------------------------------------------------------
// limitIndicatorColor — shared internal
// ---------------------------------------------------------------------------
function _limitIndicatorColorInternal(remainingPercent) {
    const trace = {
        input: remainingPercent,
        isFinite: Number.isFinite(remainingPercent),
        boundedPercent: null,
        selectedIndex: null,
        lowerPercent: null,
        upperPercent: null,
        lowerColor: null,
        upperColor: null,
        ratio: null,
        lowerRgb: null,
        upperRgb: null,
        interpolatedRgb: null,
        result: null,
    };
    if (!Number.isFinite(remainingPercent)) {
        trace.result = null;
        return {result: null, trace};
    }
    trace.boundedPercent = Math.max(0, Math.min(100, remainingPercent));
    for (let index = 1; index < LIMIT_COLOR_STOPS.length; index++) {
        const [upperPercent, upperColor] = LIMIT_COLOR_STOPS[index];
        const [lowerPercent, lowerColor] = LIMIT_COLOR_STOPS[index - 1];
        if (trace.boundedPercent > upperPercent)
            continue;
        trace.selectedIndex = index;
        trace.lowerPercent = lowerPercent;
        trace.upperPercent = upperPercent;
        trace.lowerColor = lowerColor;
        trace.upperColor = upperColor;
        trace.ratio = (trace.boundedPercent - lowerPercent) / (upperPercent - lowerPercent);
        trace.lowerRgb = hexToRgb(lowerColor);
        trace.upperRgb = hexToRgb(upperColor);
        trace.interpolatedRgb = trace.lowerRgb.map((component, componentIndex) => Math.round(component + (trace.upperRgb[componentIndex] - component) * trace.ratio));
        trace.result = rgbToHex(trace.interpolatedRgb);
        return {result: trace.result, trace};
    }
    trace.selectedIndex = LIMIT_COLOR_STOPS.length - 1;
    trace.result = LIMIT_COLOR_STOPS[LIMIT_COLOR_STOPS.length - 1][1];
    return {result: trace.result, trace};
}

export function limitIndicatorColor(remainingPercent) {
    return _limitIndicatorColorInternal(remainingPercent).result;
}

export function traceLimitIndicatorColor(remainingPercent) {
    return _limitIndicatorColorInternal(remainingPercent);
}

export function dailyLimitIndicatorColor(remainingPercent) {
    return limitIndicatorColor(remainingPercent);
}

export function traceDailyLimitIndicatorColor(remainingPercent) {
    return traceLimitIndicatorColor(remainingPercent);
}

// ---------------------------------------------------------------------------
// normalizePace — shared internal
// ---------------------------------------------------------------------------
function _normalizePaceInternal(pace, min, max) {
    const trace = {
        pace,
        min,
        max,
        isFinite: Number.isFinite(pace),
        clamped: null,
        normalized: null,
        result: null,
    };
    if (!Number.isFinite(pace)) {
        trace.result = null;
        return {result: null, trace};
    }
    trace.clamped = Math.max(min, Math.min(max, pace));
    trace.normalized = ((trace.clamped - min) / (max - min)) * 100;
    trace.result = trace.normalized;
    return {result: trace.result, trace};
}

export function normalizePace(pace, min, max) {
    return _normalizePaceInternal(pace, min, max).result;
}

export function traceNormalizePace(pace, min, max) {
    return _normalizePaceInternal(pace, min, max);
}

// ---------------------------------------------------------------------------
// paceColor — shared internal
// ---------------------------------------------------------------------------
function _paceColorInternal(pace, min, max) {
    const trace = {
        pace,
        min,
        max,
        normalizeTrace: null,
        normalized: null,
        selectedIndex: null,
        lowerPercent: null,
        upperPercent: null,
        lowerColor: null,
        upperColor: null,
        ratio: null,
        lowerRgb: null,
        upperRgb: null,
        interpolatedRgb: null,
        result: null,
    };
    const normInternal = _normalizePaceInternal(pace, min, max);
    trace.normalizeTrace = normInternal.trace;
    trace.normalized = normInternal.result;
    if (normInternal.result === null) {
        trace.result = null;
        return {result: null, trace};
    }
    const normalized = normInternal.result;
    for (let index = 1; index < PACE_COLOR_STOPS.length; index++) {
        const [upperPercent, upperColor] = PACE_COLOR_STOPS[index];
        const [lowerPercent, lowerColor] = PACE_COLOR_STOPS[index - 1];
        if (normalized > upperPercent)
            continue;
        trace.selectedIndex = index;
        trace.lowerPercent = lowerPercent;
        trace.upperPercent = upperPercent;
        trace.lowerColor = lowerColor;
        trace.upperColor = upperColor;
        trace.ratio = (normalized - lowerPercent) / (upperPercent - lowerPercent);
        trace.lowerRgb = hexToRgb(lowerColor);
        trace.upperRgb = hexToRgb(upperColor);
        trace.interpolatedRgb = trace.lowerRgb.map((component, componentIndex) => Math.round(component + (trace.upperRgb[componentIndex] - component) * trace.ratio));
        trace.result = rgbToHex(trace.interpolatedRgb);
        return {result: trace.result, trace};
    }
    trace.selectedIndex = PACE_COLOR_STOPS.length - 1;
    trace.result = PACE_COLOR_STOPS[PACE_COLOR_STOPS.length - 1][1];
    return {result: trace.result, trace};
}

export function paceColor(pace, min, max) {
    return _paceColorInternal(pace, min, max).result;
}

export function tracePaceColor(pace, min, max) {
    return _paceColorInternal(pace, min, max);
}

export function dailyRemainingColor(dailyRemainingPercent) {
    return paceColor(dailyRemainingPercent, DAILY_REMAINING_MIN, DAILY_REMAINING_MAX);
}

export function traceDailyRemainingColor(dailyRemainingPercent) {
    return _paceColorInternal(dailyRemainingPercent, DAILY_REMAINING_MIN, DAILY_REMAINING_MAX);
}

export function dailyPaceColor(pace) {
    return dailyRemainingColor(pace);
}

export function traceDailyPaceColor(pace) {
    return traceDailyRemainingColor(pace);
}

export function sessionPaceColor(pace) {
    return paceColor(pace, SESSION_PACE_MIN, SESSION_PACE_MAX);
}

export function traceSessionPaceColor(pace) {
    return _paceColorInternal(pace, SESSION_PACE_MIN, SESSION_PACE_MAX);
}

export function weeklyPaceColor(pace) {
    return paceToColor(pace);
}

export function traceWeeklyPaceColor(pace) {
    return tracePaceToColor(pace);
}

const PACE_THRESHOLDS = [
    {max: 0.80, color: '#15803D'},
    {max: 0.94, color: '#84CC16'},
    {max: 1.05, color: '#FACC15'},
    {max: 1.25, color: '#EA580C'},
    {max: Infinity, color: '#B91C1C'},
];

// ---------------------------------------------------------------------------
// dailyConsumptionPace — shared internal
// ---------------------------------------------------------------------------
function _dailyConsumptionPaceInternal({actualUsage, expectedUsage}) {
    const trace = {
        actualUsage,
        expectedUsage,
        isActualFinite: Number.isFinite(actualUsage),
        isExpectedFinite: Number.isFinite(expectedUsage),
        isZeroZero: false,
        isInfiniteCase: false,
        ratio: null,
        result: null,
    };
    if (!Number.isFinite(actualUsage) || !Number.isFinite(expectedUsage)) {
        trace.result = null;
        return {result: null, trace};
    }
    if (expectedUsage === 0 && actualUsage === 0) {
        trace.isZeroZero = true;
        trace.result = 1.0;
        return {result: 1.0, trace};
    }
    if (expectedUsage === 0 && actualUsage > 0) {
        trace.isInfiniteCase = true;
        trace.result = Infinity;
        return {result: Infinity, trace};
    }
    trace.ratio = actualUsage / expectedUsage;
    trace.result = trace.ratio;
    return {result: trace.result, trace};
}

export function dailyConsumptionPace({actualUsage, expectedUsage}) {
    return _dailyConsumptionPaceInternal({actualUsage, expectedUsage}).result;
}

export function traceDailyConsumptionPace({actualUsage, expectedUsage}) {
    return _dailyConsumptionPaceInternal({actualUsage, expectedUsage});
}

// ---------------------------------------------------------------------------
// elapsedFractionOfWeek — shared internal (deprecated: use consumption horizon)
// Kept for backward compatibility — delegates to 7-day horizon.
// ---------------------------------------------------------------------------
function _elapsedFractionOfWeekInternal(resetAt, lastUpdated) {
    const trace = {
        resetAt,
        lastUpdated,
        resetAtMillis: Date.parse(resetAt || ''),
        lastUpdatedMillis: Date.parse(lastUpdated || ''),
        isResetFinite: null,
        isLastUpdatedFinite: null,
        weekMillis: 7 * DAY_MILLIS,
        windowStartMillis: null,
        elapsedMillis: null,
        rawFraction: null,
        clampedFraction: null,
        result: null,
    };
    trace.isResetFinite = Number.isFinite(trace.resetAtMillis);
    trace.isLastUpdatedFinite = Number.isFinite(trace.lastUpdatedMillis);
    if (!trace.isResetFinite || !trace.isLastUpdatedFinite) {
        trace.result = null;
        return {result: null, trace};
    }
    trace.windowStartMillis = weekStartMillis(trace.resetAtMillis);
    trace.elapsedMillis = Math.max(0, trace.lastUpdatedMillis - trace.windowStartMillis);
    trace.rawFraction = trace.elapsedMillis / trace.weekMillis;
    trace.clampedFraction = Math.min(1, trace.rawFraction);
    trace.result = trace.clampedFraction;
    return {result: trace.result, trace};
}

export function elapsedFractionOfWeek(resetAt, lastUpdated) {
    return _elapsedFractionOfWeekInternal(resetAt, lastUpdated).result;
}

export function traceElapsedFractionOfWeek(resetAt, lastUpdated) {
    return _elapsedFractionOfWeekInternal(resetAt, lastUpdated);
}

// ---------------------------------------------------------------------------
// elapsedFractionOfConsumptionHorizon — shared internal
// Weekly quota window remains 7 days (weeklyStart = reset - 7*DAY),
// but expected consumption spreads over workdays local calendar days.
// ---------------------------------------------------------------------------
function _elapsedFractionOfConsumptionHorizonInternal(resetAt, lastUpdated, workdays) {
    const trace = {
        resetAt,
        lastUpdated,
        workdays,
        resetAtMillis: Date.parse(resetAt || ''),
        lastUpdatedMillis: Date.parse(lastUpdated || ''),
        isResetFinite: null,
        isLastUpdatedFinite: null,
        isWorkdaysValid: null,
        weeklyStartMillis: null,
        consumptionDurationMillis: null,
        consumptionHorizonMillis: null,
        cappedEndMillis: null,
        elapsedCalendarDayUnits: null,
        elapsedMillis: null,
        rawFraction: null,
        clampedFraction: null,
        result: null,
    };
    trace.isResetFinite = Number.isFinite(trace.resetAtMillis);
    trace.isLastUpdatedFinite = Number.isFinite(trace.lastUpdatedMillis);
    trace.isWorkdaysValid = Number.isFinite(workdays) && workdays > 0;
    if (!trace.isResetFinite || !trace.isLastUpdatedFinite || !trace.isWorkdaysValid) {
        trace.result = null;
        return {result: null, trace};
    }
    trace.weeklyStartMillis = weekStartMillis(trace.resetAtMillis);
    trace.consumptionHorizonMillis = addLocalCalendarDaysMillis(trace.weeklyStartMillis, workdays);
    trace.consumptionDurationMillis = trace.consumptionHorizonMillis - trace.weeklyStartMillis;
    if (!Number.isFinite(trace.consumptionDurationMillis) || trace.consumptionDurationMillis <= 0) {
        trace.result = null;
        return {result: null, trace};
    }
    trace.cappedEndMillis = Math.min(Math.max(trace.lastUpdatedMillis, trace.weeklyStartMillis), trace.consumptionHorizonMillis);
    trace.elapsedCalendarDayUnits = localCalendarDayUnitsBetween(trace.weeklyStartMillis, trace.cappedEndMillis);
    trace.elapsedMillis = Math.max(0, trace.lastUpdatedMillis - trace.weeklyStartMillis);
    trace.rawFraction = trace.elapsedCalendarDayUnits / workdays;
    trace.clampedFraction = Math.min(1, Math.max(0, trace.rawFraction));
    trace.result = trace.clampedFraction;
    return {result: trace.result, trace};
}

export function elapsedFractionOfConsumptionHorizon(resetAt, lastUpdated, workdays) {
    // Support both positional (resetAt, lastUpdated, workdays) and object {resetAt, lastUpdated, workdays}
    if (resetAt !== null && typeof resetAt === 'object' && !Array.isArray(resetAt) && 'resetAt' in resetAt) {
        const obj = resetAt;
        return _elapsedFractionOfConsumptionHorizonInternal(obj.resetAt, obj.lastUpdated, obj.workdays).result;
    }
    return _elapsedFractionOfConsumptionHorizonInternal(resetAt, lastUpdated, workdays).result;
}

export function traceElapsedFractionOfConsumptionHorizon(resetAt, lastUpdated, workdays) {
    if (resetAt !== null && typeof resetAt === 'object' && !Array.isArray(resetAt) && 'resetAt' in resetAt) {
        const obj = resetAt;
        return _elapsedFractionOfConsumptionHorizonInternal(obj.resetAt, obj.lastUpdated, obj.workdays);
    }
    return _elapsedFractionOfConsumptionHorizonInternal(resetAt, lastUpdated, workdays);
}

export function elapsedFractionOfWorkdayHorizon(resetAt, lastUpdated, workdays) {
    return elapsedFractionOfConsumptionHorizon(resetAt, lastUpdated, workdays);
}

export function traceElapsedFractionOfWorkdayHorizon(resetAt, lastUpdated, workdays) {
    return traceElapsedFractionOfConsumptionHorizon(resetAt, lastUpdated, workdays);
}

// ---------------------------------------------------------------------------
// weeklyConsumptionPace — shared internal
// ---------------------------------------------------------------------------
function _weeklyConsumptionPaceInternal({quotaRemainingPercent, elapsedFraction}) {
    const trace = {
        quotaRemainingPercent,
        elapsedFraction,
        isQuotaFinite: Number.isFinite(quotaRemainingPercent),
        isElapsedFinite: Number.isFinite(elapsedFraction),
        actualUsage: null,
        expectedUsage: null,
        dailyPaceTrace: null,
        result: null,
    };
    if (!Number.isFinite(quotaRemainingPercent) || !Number.isFinite(elapsedFraction)) {
        trace.result = null;
        return {result: null, trace};
    }
    trace.actualUsage = 100 - quotaRemainingPercent;
    trace.expectedUsage = elapsedFraction * 100;
    const inner = _dailyConsumptionPaceInternal({actualUsage: trace.actualUsage, expectedUsage: trace.expectedUsage});
    trace.dailyPaceTrace = inner.trace;
    trace.result = inner.result;
    return {result: trace.result, trace};
}

export function weeklyConsumptionPace({quotaRemainingPercent, elapsedFraction}) {
    return _weeklyConsumptionPaceInternal({quotaRemainingPercent, elapsedFraction}).result;
}

export function traceWeeklyConsumptionPace({quotaRemainingPercent, elapsedFraction}) {
    return _weeklyConsumptionPaceInternal({quotaRemainingPercent, elapsedFraction});
}

// ---------------------------------------------------------------------------
// paceToColor — shared internal
// ---------------------------------------------------------------------------
function _paceToColorInternal(pace) {
    const trace = {
        pace,
        isFinite: Number.isFinite(pace),
        selectedThreshold: null,
        selectedColor: null,
        result: null,
    };
    if (!Number.isFinite(pace)) {
        trace.result = null;
        return {result: null, trace};
    }
    for (const {max, color} of PACE_THRESHOLDS) {
        if (pace <= max) {
            trace.selectedThreshold = max;
            trace.selectedColor = color;
            trace.result = color;
            return {result: color, trace};
        }
    }
    trace.selectedThreshold = PACE_THRESHOLDS[PACE_THRESHOLDS.length - 1].max;
    trace.selectedColor = PACE_THRESHOLDS[PACE_THRESHOLDS.length - 1].color;
    trace.result = trace.selectedColor;
    return {result: trace.result, trace};
}

export function paceToColor(pace) {
    return _paceToColorInternal(pace).result;
}

export function tracePaceToColor(pace) {
    return _paceToColorInternal(pace);
}

export function resolveLimitIndicatorPercents({sessionPercent, weeklyPercent}) {
    const bounded = value => (Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null);
    return {
        session: bounded(sessionPercent),
        weekly: bounded(weeklyPercent),
    };
}

// ---------------------------------------------------------------------------
// calculateSessionPace — shared internal
// ---------------------------------------------------------------------------
function _calculateSessionPaceInternal({sessionPercent, sessionResetAt, lastUpdated, sessionWindowMins}) {
    const trace = {
        sessionPercent,
        sessionResetAt,
        lastUpdated,
        sessionWindowMins,
        isSessionPercentFinite: Number.isFinite(sessionPercent),
        isWindowValid: Number.isFinite(sessionWindowMins) ? sessionWindowMins > 0 : false,
        resetAtMillis: null,
        lastUpdatedMillis: null,
        isResetFinite: null,
        isLastUpdatedFinite: null,
        sessionTotalMillis: null,
        sessionStartMillis: null,
        elapsedMillis: null,
        elapsedMinutes: null,
        timeElapsedPercentRaw: null,
        timeElapsedPercentClamped: null,
        expectedRemainingPercent: null,
        rawPace: null,
        clampedPace: null,
        result: null,
    };
    if (!Number.isFinite(sessionPercent) || !Number.isFinite(sessionWindowMins) || sessionWindowMins <= 0) {
        trace.result = null;
        return {result: null, trace};
    }
    trace.resetAtMillis = Date.parse(sessionResetAt || '');
    trace.lastUpdatedMillis = Date.parse(lastUpdated || '');
    trace.isResetFinite = Number.isFinite(trace.resetAtMillis);
    trace.isLastUpdatedFinite = Number.isFinite(trace.lastUpdatedMillis);
    if (!trace.isResetFinite || !trace.isLastUpdatedFinite) {
        trace.result = null;
        return {result: null, trace};
    }
    trace.sessionTotalMillis = sessionWindowMins * 60 * 1000;
    trace.sessionStartMillis = trace.resetAtMillis - trace.sessionTotalMillis;
    trace.elapsedMillis = trace.lastUpdatedMillis - trace.sessionStartMillis;
    trace.elapsedMinutes = trace.elapsedMillis / 60000;
    trace.timeElapsedPercentRaw = (trace.elapsedMillis / trace.sessionTotalMillis) * 100;
    trace.timeElapsedPercentClamped = Math.max(0, Math.min(100, trace.timeElapsedPercentRaw));
    trace.expectedRemainingPercent = 100 - trace.timeElapsedPercentClamped;
    trace.rawPace = sessionPercent - trace.expectedRemainingPercent;
    trace.clampedPace = Math.max(-100, Math.min(100, trace.rawPace));
    trace.result = trace.clampedPace;
    return {result: trace.result, trace};
}

export function calculateSessionPace({sessionPercent, sessionResetAt, lastUpdated, sessionWindowMins}) {
    return _calculateSessionPaceInternal({sessionPercent, sessionResetAt, lastUpdated, sessionWindowMins}).result;
}

export function traceCalculateSessionPace({sessionPercent, sessionResetAt, lastUpdated, sessionWindowMins}) {
    return _calculateSessionPaceInternal({sessionPercent, sessionResetAt, lastUpdated, sessionWindowMins});
}

function hexToRgb(hex) {
    return [1, 3, 5].map(index => Number.parseInt(hex.slice(index, index + 2), 16));
}

function rgbToHex(rgb) {
    return `#${rgb.map(component => component.toString(16).padStart(2, '0')).join('').toUpperCase()}`;
}

export function compactPanelComponents({sessionPercent, sessionResetTime, dailyRemainingPercent, weeklyPercent, weeklyResetDate}) {
    const percentLabel = value => Number.isFinite(value) ? `${Math.round(value)}%` : null;
    const resetLabel = value => value ? `(${value})` : null;
    const joinParts = (...parts) => parts.filter(Boolean).join(' ') || null;
    return {
        session: joinParts(percentLabel(sessionPercent), resetLabel(sessionResetTime)),
        daily: percentLabel(dailyRemainingPercent),
        weekly: joinParts(percentLabel(weeklyPercent), resetLabel(weeklyResetDate)),
    };
}

export function resolveDailyRemainingPercent({quotaRemainingPercent, resetAt, lastUpdated, workdays}) {
    return calculateWeeklyPace({quotaRemainingPercent, resetAt, lastUpdated, workdays}).dailyRemainingPercent;
}

// ---------------------------------------------------------------------------
// calculateWeeklyPace — shared internal
// ---------------------------------------------------------------------------
function _calculateWeeklyPaceInternal({quotaRemainingPercent, resetAt, lastUpdated, workdays}) {
    const trace = {
        quotaRemainingPercent,
        resetAt,
        lastUpdated,
        workdays,
        resetAtMillis: Date.parse(resetAt || ''),
        lastUpdatedMillis: Date.parse(lastUpdated || ''),
        isQuotaFinite: Number.isFinite(quotaRemainingPercent),
        isResetFinite: null,
        isLastUpdatedFinite: null,
        isIncomplete: null,
        boundedQuotaRemainingPercent: null,
        weeklyStartMillis: null,
        consumptionHorizonMillis: null,
        fullDayBudget: null,
        lastUpdatedDate: null,
        localToday00: null,
        localNextDay00: null,
        effectiveDayStart: null,
        effectiveDayEnd: null,
        todayDuration: null,
        todayDurationHours: null,
        todayBudget: null,
        nextDayCapped: null,
        allowedByEOD: null,
        actualUsage: null,
        available: null,
        divisor: null,
        dailyRemainingPercent: null,
        elapsedMillis: null,
        elapsedFraction: null,
        elapsedWorkdays: null,
        todayMinimumRemainingPercent: null,
        result: null,
    };
    trace.isResetFinite = Number.isFinite(trace.resetAtMillis);
    trace.isLastUpdatedFinite = Number.isFinite(trace.lastUpdatedMillis);

    if (!Number.isFinite(quotaRemainingPercent) || !trace.isResetFinite || !trace.isLastUpdatedFinite) {
        trace.isIncomplete = true;
        trace.result = {
            level: 'unknown',
            quotaRemainingPercent: null,
            todayMinimumRemainingPercent: null,
            dailyRemainingPercent: null,
            elapsedWorkdays: null,
            workdays,
            budgetPerWorkday: null,
            elapsedFraction: null,
        };
        return {result: trace.result, trace};
    }

    trace.isIncomplete = false;
    trace.boundedQuotaRemainingPercent = Math.max(0, Math.min(100, quotaRemainingPercent));
    trace.weeklyStartMillis = weekStartMillis(trace.resetAtMillis);
    trace.consumptionHorizonMillis = addLocalCalendarDaysMillis(trace.weeklyStartMillis, workdays);
    trace.consumptionDurationMillis = trace.consumptionHorizonMillis - trace.weeklyStartMillis;
    trace.fullDayBudget = 100 / workdays;

    trace.lastUpdatedDate = new Date(trace.lastUpdatedMillis);
    trace.localToday00 = localMidnightEpochMillis(trace.lastUpdatedDate);
    trace.localNextDay00 = nextLocalMidnightEpochMillis(trace.lastUpdatedDate);

    trace.effectiveDayStart = Math.max(trace.localToday00, trace.weeklyStartMillis);
    trace.effectiveDayEnd = Math.min(trace.localNextDay00, trace.consumptionHorizonMillis);
    trace.todayDuration = Math.max(0, trace.effectiveDayEnd - trace.effectiveDayStart);
    trace.todayDurationHours = trace.todayDuration / (60 * 60 * 1000);
    trace.todayDayUnits = localCalendarDayUnitsBetween(trace.effectiveDayStart, trace.effectiveDayEnd) ?? 0;
    trace.todayBudget = trace.todayDayUnits * trace.fullDayBudget;

    trace.nextDayCapped = Math.min(trace.localNextDay00, trace.consumptionHorizonMillis);
    trace.allowedDayUnitsByEOD = localCalendarDayUnitsBetween(trace.weeklyStartMillis, trace.nextDayCapped) ?? 0;
    trace.allowedByEOD = Math.max(0, Math.min(100,
        trace.allowedDayUnitsByEOD / workdays * 100
    ));

    trace.actualUsage = 100 - trace.boundedQuotaRemainingPercent;
    trace.available = trace.allowedByEOD - trace.actualUsage;
    trace.divisor = trace.todayBudget > 0 ? trace.todayBudget : trace.fullDayBudget;
    trace.dailyRemainingPercent = trace.available / trace.divisor * 100;

    trace.cappedEndMillis = Math.min(Math.max(trace.lastUpdatedMillis, trace.weeklyStartMillis), trace.consumptionHorizonMillis);
    trace.elapsedCalendarDayUnits = localCalendarDayUnitsBetween(trace.weeklyStartMillis, trace.cappedEndMillis) ?? 0;
    trace.elapsedMillis = Math.max(0, trace.lastUpdatedMillis - trace.weeklyStartMillis);
    trace.elapsedFraction = Math.max(0, Math.min(1, trace.elapsedCalendarDayUnits / workdays));
    trace.elapsedWorkdays = trace.elapsedCalendarDayUnits;
    trace.todayMinimumRemainingPercent = Math.max(0, 100 - trace.elapsedWorkdays * trace.fullDayBudget);

    trace.result = {
        quotaRemainingPercent: trace.boundedQuotaRemainingPercent,
        todayMinimumRemainingPercent: trace.todayMinimumRemainingPercent,
        dailyRemainingPercent: trace.dailyRemainingPercent,
        elapsedWorkdays: trace.elapsedWorkdays,
        workdays,
        budgetPerWorkday: trace.fullDayBudget,
        elapsedFraction: trace.elapsedFraction,
    };
    return {result: trace.result, trace};
}

export function calculateWeeklyPace({quotaRemainingPercent, resetAt, lastUpdated, workdays}) {
    return _calculateWeeklyPaceInternal({quotaRemainingPercent, resetAt, lastUpdated, workdays}).result;
}

export function traceCalculateWeeklyPace({quotaRemainingPercent, resetAt, lastUpdated, workdays}) {
    return _calculateWeeklyPaceInternal({quotaRemainingPercent, resetAt, lastUpdated, workdays});
}
