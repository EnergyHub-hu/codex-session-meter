const DAY_MILLIS = 24 * 60 * 60 * 1000;

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

export function dailyLimitIndicatorColor(dailyRemainingPercent) {
    if (!Number.isFinite(dailyRemainingPercent))
        return null;

    const boundedPercent = Math.max(0, Math.min(100, dailyRemainingPercent));
    const hue = Math.round(boundedPercent * 1.2);
    return `hsl(${hue}, 75%, 45%)`;
}

export function formatPanelDisplay({dailyRemainingPercent, weeklyPercent, weeklyResetDate, displayFormat, fallback}) {
    if (dailyRemainingPercent === null)
        return fallback;

    const daily = Math.round(dailyRemainingPercent);
    const weekly = weeklyPercent ?? 'n/a';
    const reset = weeklyResetDate || 'nincs';
    if (displayFormat === 'verbose')
        return `Napi ${daily}% | Heti ${weekly}% | Reset ${reset}`;

    return `${daily}% / ${weekly}% | ${reset}`;
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
