import test from 'node:test';
import assert from 'node:assert/strict';

import {calculateWeeklyPace, dailyLimitIndicatorColor, dailyLimitIndicatorLevel, formatPanelDisplay, resolveDailyRemainingPercent} from './weekly-pace.js';

test('prefers the real five hour session percent when the payload provides one', () => {
    const value = resolveDailyRemainingPercent({
        sessionPercent: 42,
        quotaRemainingPercent: 85,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T09:00:00+02:00',
        workdays: 5,
    });

    assert.equal(value, 42);
});

test('clamps the real five hour session percent into the zero to hundred range', () => {
    assert.equal(resolveDailyRemainingPercent({sessionPercent: 130}), 100);
    assert.equal(resolveDailyRemainingPercent({sessionPercent: -5}), 0);
});

test('falls back to the weekly pace estimate without a real five hour window', () => {
    const value = resolveDailyRemainingPercent({
        sessionPercent: null,
        quotaRemainingPercent: 85,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T09:00:00+02:00',
        workdays: 5,
    });

    const expected = calculateWeeklyPace({
        quotaRemainingPercent: 85,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T09:00:00+02:00',
        workdays: 5,
    }).dailyRemainingPercent;

    assert.equal(value, expected);
});

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
    assert.equal(dailyLimitIndicatorColor(0), '#D1495B');
    assert.equal(dailyLimitIndicatorColor(20), '#EE964B');
    assert.equal(dailyLimitIndicatorColor(40), '#F4D35E');
    assert.equal(dailyLimitIndicatorColor(55), '#99D98C');
    assert.equal(dailyLimitIndicatorColor(70), '#52B69A');
    assert.equal(dailyLimitIndicatorColor(85), '#34A0A4');
    assert.equal(dailyLimitIndicatorColor(100), '#168AAD');
    assert.equal(dailyLimitIndicatorColor(50), '#B7D77D');
    assert.equal(dailyLimitIndicatorColor(null), null);
});

test('adds daily weekly and reset labels in verbose panel format', () => {
    assert.equal(
        formatPanelDisplay({
            dailyRemainingPercent: 125,
            weeklyPercent: 89,
            weeklyResetDate: '07.20.',
            sessionResetTime: '12:56',
            displayFormat: 'verbose',
            fallback: 'Codex: ismeretlen hiba',
        }),
        'Napi 125% | Heti 89% | Reset 12:56 / 07.20.'
    );
});

test('keeps the compact panel format unlabeled', () => {
    assert.equal(
        formatPanelDisplay({
            dailyRemainingPercent: 125,
            weeklyPercent: 89,
            weeklyResetDate: '07.20.',
            sessionResetTime: '12:56',
            displayFormat: 'compact',
            fallback: 'Codex: ismeretlen hiba',
        }),
        '125% / 89% | 12:56 / 07.20.'
    );
});

test('shows only the weekly reset without a five hour window', () => {
    assert.equal(
        formatPanelDisplay({
            dailyRemainingPercent: 125,
            weeklyPercent: 89,
            weeklyResetDate: '07.20.',
            sessionResetTime: null,
            displayFormat: 'verbose',
            fallback: 'Codex: ismeretlen hiba',
        }),
        'Napi 125% | Heti 89% | Reset 07.20.'
    );
    assert.equal(
        formatPanelDisplay({
            dailyRemainingPercent: 125,
            weeklyPercent: 89,
            weeklyResetDate: null,
            sessionResetTime: '12:56',
            displayFormat: 'compact',
            fallback: 'Codex: ismeretlen hiba',
        }),
        '125% / 89% | 12:56'
    );
});
