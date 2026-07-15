import test from 'node:test';
import assert from 'node:assert/strict';

import {calculateWeeklyPace, dailyLimitIndicatorColor, dailyLimitIndicatorLevel, formatPanelDisplay} from './weekly-pace.js';

test('treats the day after a late weekly reset as the second allocation day', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 85,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T09:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.startedWorkdays, 2);
    assert.equal(pace.todayMinimumRemainingPercent, 60);
    assert.equal(pace.dailyRemainingPercent, 125);
});

test('shows five percent of the daily quota after using nineteen of the first twenty weekly points', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 81,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-13T09:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.startedWorkdays, 1);
    assert.equal(pace.dailyRemainingPercent, 5);
});

test('reduces the normalized daily limit by four points across four workdays', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 99,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-13T09:00:00+02:00',
        workdays: 4,
    });

    assert.equal(pace.budgetPerWorkday, 25);
    assert.equal(pace.dailyRemainingPercent, 96);
});

test('reduces the normalized daily limit by three points across three workdays', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 99,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-13T09:00:00+02:00',
        workdays: 3,
    });

    assert.equal(pace.budgetPerWorkday, 100 / 3);
    assert.equal(Math.round(pace.dailyRemainingPercent), 97);
});

test('maps five-day daily quota drops to proportional indicator steps', () => {
    assert.equal(dailyLimitIndicatorLevel(125), 'over');
    assert.equal(dailyLimitIndicatorLevel(100), '100');
    assert.equal(dailyLimitIndicatorLevel(95), '95');
    assert.equal(dailyLimitIndicatorLevel(90), '90');
    assert.equal(dailyLimitIndicatorLevel(4), '4');
    assert.equal(dailyLimitIndicatorLevel(-2), '0');
});

test('normalizes daily quota drops for four and three workdays', () => {
    assert.equal(dailyLimitIndicatorLevel(96), '96');
    assert.equal(dailyLimitIndicatorLevel(97), '97');
});

test('colors the daily indicator proportionally from red to green', () => {
    assert.equal(dailyLimitIndicatorColor(0), 'hsl(0, 75%, 45%)');
    assert.equal(dailyLimitIndicatorColor(50), 'hsl(60, 75%, 45%)');
    assert.equal(dailyLimitIndicatorColor(100), 'hsl(120, 75%, 45%)');
    assert.equal(dailyLimitIndicatorColor(null), null);
});

test('adds daily weekly and reset labels in verbose panel format', () => {
    assert.equal(
        formatPanelDisplay({
            dailyRemainingPercent: 125,
            weeklyPercent: 89,
            weeklyResetDate: '07.20.',
            displayFormat: 'verbose',
            fallback: 'Codex: ismeretlen hiba',
        }),
        'Napi 125% | Heti 89% | Reset 07.20.'
    );
});

test('keeps the compact panel format unlabeled', () => {
    assert.equal(
        formatPanelDisplay({
            dailyRemainingPercent: 125,
            weeklyPercent: 89,
            weeklyResetDate: '07.20.',
            displayFormat: 'compact',
            fallback: 'Codex: ismeretlen hiba',
        }),
        '125% / 89% | 07.20.'
    );
});
