const DAY_MILLIS = 24 * 60 * 60 * 1000;
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
const DAILY_PACE_MIN = -100;
const DAILY_PACE_MAX = 200;
const SESSION_PACE_MIN = -100;
const SESSION_PACE_MAX = 100;

function localCalendarDayMillis(date) {
    return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
}

export function dailyLimitIndicatorLevel(dailyRemainingPercent) {
    if (!Number.isFinite(dailyRemainingPercent))
        return 'unknown';
    if (dailyRemainingPercent > 100)
        return 'over';
    return String(Math.round(Math.max(0, dailyRemainingPercent)));
}

export function dailyLimitIndicatorColor(remainingPercent) {
    return limitIndicatorColor(remainingPercent);
}

export function limitIndicatorColor(remainingPercent) {
    if (!Number.isFinite(remainingPercent))
        return null;

    const boundedPercent = Math.max(0, Math.min(100, remainingPercent));
    for (let index = 1; index < LIMIT_COLOR_STOPS.length; index++) {
        const [upperPercent, upperColor] = LIMIT_COLOR_STOPS[index];
        const [lowerPercent, lowerColor] = LIMIT_COLOR_STOPS[index - 1];
        if (boundedPercent > upperPercent)
            continue;

        const ratio = (boundedPercent - lowerPercent) / (upperPercent - lowerPercent);
        const lowerRgb = hexToRgb(lowerColor);
        const upperRgb = hexToRgb(upperColor);
        const rgb = lowerRgb.map((component, componentIndex) => Math.round(component + (upperRgb[componentIndex] - component) * ratio));
        return rgbToHex(rgb);
    }

    return LIMIT_COLOR_STOPS[LIMIT_COLOR_STOPS.length - 1][1];
}

export function normalizePace(pace, min, max) {
    if (!Number.isFinite(pace))
        return null;
    const clamped = Math.max(min, Math.min(max, pace));
    return ((clamped - min) / (max - min)) * 100;
}

export function paceColor(pace, min, max) {
    const normalized = normalizePace(pace, min, max);
    if (normalized === null)
        return null;
    for (let index = 1; index < PACE_COLOR_STOPS.length; index++) {
        const [upperPercent, upperColor] = PACE_COLOR_STOPS[index];
        const [lowerPercent, lowerColor] = PACE_COLOR_STOPS[index - 1];
        if (normalized > upperPercent)
            continue;

        const ratio = (normalized - lowerPercent) / (upperPercent - lowerPercent);
        const lowerRgb = hexToRgb(lowerColor);
        const upperRgb = hexToRgb(upperColor);
        const rgb = lowerRgb.map((component, componentIndex) => Math.round(component + (upperRgb[componentIndex] - component) * ratio));
        return rgbToHex(rgb);
    }

    return PACE_COLOR_STOPS[PACE_COLOR_STOPS.length - 1][1];
}

export function dailyPaceColor(pace) {
    return paceColor(pace, DAILY_PACE_MIN, DAILY_PACE_MAX);
}

export function sessionPaceColor(pace) {
    return paceColor(pace, SESSION_PACE_MIN, SESSION_PACE_MAX);
}

export function weeklyPaceColor(pace) {
    return paceToColor(pace);
}

const PACE_THRESHOLDS = [
    {max: 0.80, color: '#15803D'},
    {max: 0.94, color: '#84CC16'},
    {max: 1.05, color: '#FACC15'},
    {max: 1.25, color: '#EA580C'},
    {max: Infinity, color: '#B91C1C'},
];

export function dailyConsumptionPace({actualUsage, expectedUsage}) {
    if (!Number.isFinite(actualUsage) || !Number.isFinite(expectedUsage))
        return null;
    if (expectedUsage === 0 && actualUsage === 0)
        return 1.0;
    if (expectedUsage === 0 && actualUsage > 0)
        return Infinity;
    return actualUsage / expectedUsage;
}

export function weeklyConsumptionPace({quotaRemainingPercent, elapsedFraction}) {
    if (!Number.isFinite(quotaRemainingPercent) || !Number.isFinite(elapsedFraction))
        return null;
    const actualUsage = 100 - quotaRemainingPercent;
    const expectedUsage = elapsedFraction * 100;
    return dailyConsumptionPace({actualUsage, expectedUsage});
}

export function paceToColor(pace) {
    if (!Number.isFinite(pace))
        return null;
    for (const {max, color} of PACE_THRESHOLDS) {
        if (pace <= max)
            return color;
    }
    return PACE_THRESHOLDS[PACE_THRESHOLDS.length - 1].color;
}

export function resolveLimitIndicatorPercents({sessionPercent, weeklyPercent}) {
    const bounded = value => (Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null);
    return {
        session: bounded(sessionPercent),
        weekly: bounded(weeklyPercent),
    };
}

export function calculateSessionPace({sessionPercent, sessionResetAt, lastUpdated, sessionWindowMins}) {
    if (!Number.isFinite(sessionPercent) || !Number.isFinite(sessionWindowMins) || sessionWindowMins <= 0)
        return null;

    const resetAtMillis = Date.parse(sessionResetAt || '');
    const lastUpdatedMillis = Date.parse(lastUpdated || '');
    if (!Number.isFinite(resetAtMillis) || !Number.isFinite(lastUpdatedMillis))
        return null;

    const sessionTotalMillis = sessionWindowMins * 60 * 1000;
    const sessionStartMillis = resetAtMillis - sessionTotalMillis;
    const elapsedMillis = lastUpdatedMillis - sessionStartMillis;
    const timeElapsedPercent = Math.max(0, Math.min(100, (elapsedMillis / sessionTotalMillis) * 100));

    return Math.max(-100, Math.min(100, sessionPercent - timeElapsedPercent));
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

export function calculateWeeklyPace({quotaRemainingPercent, resetAt, lastUpdated, workdays}) {
    const resetAtMillis = Date.parse(resetAt || '');
    const lastUpdatedMillis = Date.parse(lastUpdated || '');

    if (!Number.isFinite(quotaRemainingPercent) || !Number.isFinite(resetAtMillis) || !Number.isFinite(lastUpdatedMillis)) {
        return {
            level: 'unknown',
            quotaRemainingPercent: null,
            todayMinimumRemainingPercent: null,
            dailyRemainingPercent: null,
            elapsedWorkdays: null,
            workdays,
            budgetPerWorkday: null,
        };
    }

    const boundedQuotaRemainingPercent = Math.max(0, Math.min(100, quotaRemainingPercent));
    const windowStartMillis = resetAtMillis - (7 * DAY_MILLIS);
    const windowDurationMillis = 7 * DAY_MILLIS;
    const elapsedMillis = Math.max(0, lastUpdatedMillis - windowStartMillis);
    const elapsedFraction = Math.min(1, elapsedMillis / windowDurationMillis);
    const elapsedWorkdays = elapsedFraction * workdays;
    const budgetPerWorkday = 100 / workdays;
    const todayMinimumRemainingPercent = Math.max(0, 100 - elapsedWorkdays * budgetPerWorkday);
    const dailyRemainingPercent = ((boundedQuotaRemainingPercent - todayMinimumRemainingPercent) / budgetPerWorkday) * 100;

    return {
        quotaRemainingPercent: boundedQuotaRemainingPercent,
        todayMinimumRemainingPercent,
        dailyRemainingPercent,
        elapsedWorkdays,
        workdays,
        budgetPerWorkday,
        elapsedFraction,
    };
}
