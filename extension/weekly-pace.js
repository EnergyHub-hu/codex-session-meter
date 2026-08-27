const DAY_MILLIS = 24 * 60 * 60 * 1000;
const DAILY_LIMIT_COLOR_STOPS = [
    [0, '#D1495B'],
    [20, '#EE964B'],
    [40, '#F4D35E'],
    [55, '#99D98C'],
    [70, '#52B69A'],
    [85, '#34A0A4'],
    [100, '#168AAD'],
];

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
    for (let index = 1; index < DAILY_LIMIT_COLOR_STOPS.length; index++) {
        const [upperPercent, upperColor] = DAILY_LIMIT_COLOR_STOPS[index];
        const [lowerPercent, lowerColor] = DAILY_LIMIT_COLOR_STOPS[index - 1];
        if (boundedPercent > upperPercent)
            continue;

        const ratio = (boundedPercent - lowerPercent) / (upperPercent - lowerPercent);
        const lowerRgb = hexToRgb(lowerColor);
        const upperRgb = hexToRgb(upperColor);
        const rgb = lowerRgb.map((component, componentIndex) => Math.round(component + (upperRgb[componentIndex] - component) * ratio));
        return rgbToHex(rgb);
    }

    return DAILY_LIMIT_COLOR_STOPS[DAILY_LIMIT_COLOR_STOPS.length - 1][1];
}

export function resolveLimitIndicatorPercents({sessionPercent, weeklyPercent}) {
    const bounded = value => (Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : null);
    return {
        session: bounded(sessionPercent),
        weekly: bounded(weeklyPercent),
    };
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

export function resolveDailyRemainingPercent({sessionPercent, quotaRemainingPercent, resetAt, lastUpdated, workdays}) {
    if (Number.isFinite(sessionPercent))
        return Math.max(0, Math.min(100, sessionPercent));

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
            startedWorkdays: null,
            workdays,
            budgetPerWorkday: null,
        };
    }

    const boundedQuotaRemainingPercent = Math.max(0, Math.min(100, quotaRemainingPercent));
    const lastUpdatedDate = new Date(lastUpdatedMillis);
    const windowStartDate = new Date(resetAtMillis - (7 * DAY_MILLIS));
    const startedCalendarDays = Math.max(0, Math.floor((localCalendarDayMillis(lastUpdatedDate) - localCalendarDayMillis(windowStartDate)) / DAY_MILLIS) + 1);
    const startedWorkdays = Math.max(0, Math.min(workdays, startedCalendarDays));
    const budgetPerWorkday = 100 / workdays;
    const todayMinimumRemainingPercent = Math.max(0, 100 - startedWorkdays * budgetPerWorkday);
    const dailyRemainingPercent = ((boundedQuotaRemainingPercent - todayMinimumRemainingPercent) / budgetPerWorkday) * 100;

    return {
        quotaRemainingPercent: boundedQuotaRemainingPercent,
        todayMinimumRemainingPercent,
        dailyRemainingPercent,
        startedWorkdays,
        workdays,
        budgetPerWorkday,
    };
}
