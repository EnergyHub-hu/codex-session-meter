import test from 'node:test';
import assert from 'node:assert/strict';

import {calculateWeeklyPace, calculateSessionPace, compactPanelComponents, dailyLimitIndicatorLevel, limitIndicatorColor, resolveDailyRemainingPercent, resolveLimitIndicatorPercents, normalizePace, paceColor, dailyPaceColor, sessionPaceColor} from './weekly-pace.js';

test('calculates daily remaining from weekly pace only', () => {
    const value = resolveDailyRemainingPercent({
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

test('returns null when weekly pace data is incomplete', () => {
    assert.equal(resolveDailyRemainingPercent({}), null);
    assert.equal(resolveDailyRemainingPercent({quotaRemainingPercent: 80}), null);
});

test('calculates time-proportional pace for a partially elapsed first day', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 85,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T09:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedWorkdays > 0, true);
    assert.equal(pace.elapsedWorkdays < 1, true);
    assert.equal(Math.round(pace.todayMinimumRemainingPercent), 91);
    assert.equal(Math.round(pace.dailyRemainingPercent), -30);
});

test('shows daily quota surplus when most of the week has elapsed but quota remains', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 81,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-19T09:00:00+02:00',
        workdays: 5,
    });

    assert.equal(Math.round(pace.elapsedWorkdays), 4);
    assert.equal(Math.round(pace.dailyRemainingPercent), 307);
});

test('calculates time-proportional pace across four workdays', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 99,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-19T09:00:00+02:00',
        workdays: 4,
    });

    assert.equal(pace.budgetPerWorkday, 25);
    assert.equal(Math.round(pace.elapsedWorkdays), 3);
    assert.equal(Math.round(pace.dailyRemainingPercent), 317);
});

test('calculates time-proportional pace across three workdays', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 99,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-19T09:00:00+02:00',
        workdays: 3,
    });

    assert.equal(Math.round(pace.budgetPerWorkday), 33);
    assert.equal(Math.round(pace.elapsedWorkdays), 2);
    assert.equal(Math.round(pace.dailyRemainingPercent), 238);
});

test('treats the exact window start as zero elapsed time', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 100,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-13T18:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedWorkdays, 0);
    assert.equal(pace.todayMinimumRemainingPercent, 100);
    assert.equal(pace.dailyRemainingPercent, 0);
});

test('treats the exact reset time as fully elapsed', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 30,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-20T18:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedWorkdays, 5);
    assert.equal(pace.todayMinimumRemainingPercent, 0);
    assert.equal(pace.dailyRemainingPercent, 150);
});

test('handles a partial first day when the window started hours ago', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 95,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T16:52:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedWorkdays > 0, true);
    assert.equal(pace.elapsedWorkdays < 1, true);
    assert.equal(pace.todayMinimumRemainingPercent > 80, true);
    assert.equal(pace.dailyRemainingPercent > 0, true);
});

test('clamps elapsed to window start when lastUpdated is before the window', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 100,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-10T09:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedWorkdays, 0);
    assert.equal(pace.todayMinimumRemainingPercent, 100);
    assert.equal(pace.dailyRemainingPercent, 0);
});

test('clamps elapsed to window end when lastUpdated is after the reset', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 50,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-25T09:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedWorkdays, 5);
    assert.equal(pace.todayMinimumRemainingPercent, 0);
    assert.equal(pace.dailyRemainingPercent, 250);
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

test('colors the limit indicator on the warm scale from deep red to green', () => {
    assert.equal(limitIndicatorColor(0), '#B91C1C');
    assert.equal(limitIndicatorColor(25), '#EA580C');
    assert.equal(limitIndicatorColor(50), '#FACC15');
    assert.equal(limitIndicatorColor(75), '#A3E635');
    assert.equal(limitIndicatorColor(100), '#22C55E');
    assert.equal(limitIndicatorColor(60), '#D7D622');
    assert.equal(limitIndicatorColor(null), null);
});

test('resolves separate session and weekly indicator percents', () => {
    assert.deepEqual(
        resolveLimitIndicatorPercents({sessionPercent: 84, weeklyPercent: 95}),
        {session: 84, weekly: 95}
    );
    assert.deepEqual(
        resolveLimitIndicatorPercents({sessionPercent: 130, weeklyPercent: -5}),
        {session: 100, weekly: 0}
    );
    assert.deepEqual(
        resolveLimitIndicatorPercents({sessionPercent: null, weeklyPercent: undefined}),
        {session: null, weekly: null}
    );
});

test('builds compact panel components with percent and reset labels', () => {
    assert.deepEqual(
        compactPanelComponents({
            sessionPercent: 87,
            sessionResetTime: '12:56',
            dailyRemainingPercent: 125,
            weeklyPercent: 89.4,
            weeklyResetDate: '07.20.',
        }),
        {
            session: '87% (12:56)',
            daily: '125%',
            weekly: '89% (07.20.)',
        }
    );
});

test('marks missing compact component data as null', () => {
    assert.deepEqual(
        compactPanelComponents({
            sessionPercent: null,
            sessionResetTime: null,
            dailyRemainingPercent: null,
            weeklyPercent: null,
            weeklyResetDate: null,
        }),
        {
            session: null,
            daily: null,
            weekly: null,
        }
    );
});

test('keeps the session label without a five hour reset time', () => {
    const components = compactPanelComponents({
        sessionPercent: 42,
        sessionResetTime: null,
        dailyRemainingPercent: 30,
        weeklyPercent: 60,
        weeklyResetDate: '09.01.',
    });

    assert.equal(components.session, '42%');
    assert.equal(components.weekly, '60% (09.01.)');
});

test('calculates session pace as remaining minus elapsed time', () => {
    const pace = calculateSessionPace({
        sessionPercent: 82,
        sessionResetAt: '2026-08-27T14:31:00+02:00',
        lastUpdated: '2026-08-27T11:29:00+02:00',
        sessionWindowMins: 300,
    });

    assert.equal(Math.round(pace), 43);
});

test('returns negative pace when session is overused relative to time', () => {
    const pace = calculateSessionPace({
        sessionPercent: 30,
        sessionResetAt: '2026-08-27T14:31:00+02:00',
        lastUpdated: '2026-08-27T12:31:00+02:00',
        sessionWindowMins: 300,
    });

    assert.equal(pace, -30);
});

test('returns null for missing session pace data', () => {
    assert.equal(calculateSessionPace({}), null);
    assert.equal(calculateSessionPace({sessionPercent: 80}), null);
    assert.equal(calculateSessionPace({sessionWindowMins: 300}), null);
});

test('normalizes pace to 0-100 range', () => {
    assert.equal(normalizePace(-100, -100, 200), 0);
    assert.equal(normalizePace(200, -100, 200), 100);
    assert.ok(Math.abs(normalizePace(0, -100, 200) - 100 / 3) < 1e-10);
    assert.equal(normalizePace(50, -100, 200), 50);
    assert.equal(normalizePace(null, -100, 200), null);
    assert.equal(normalizePace(NaN, -100, 200), null);
});

test('clamps pace values to bounds', () => {
    assert.equal(normalizePace(-200, -100, 200), 0);
    assert.equal(normalizePace(300, -100, 200), 100);
});

test('interpolates pace color between stops', () => {
    const color0 = paceColor(-100, -100, 200);
    const color50 = paceColor(50, -100, 200);
    const color200 = paceColor(200, -100, 200);
    assert.ok(color0);
    assert.ok(color50);
    assert.ok(color200);
    assert.notEqual(color0, color200);
});

test('returns null pace color for invalid input', () => {
    assert.equal(paceColor(null, -100, 200), null);
    assert.equal(paceColor(NaN, -100, 200), null);
});

test('dailyPaceColor uses daily bounds', () => {
    const red = dailyPaceColor(-100);
    const green = dailyPaceColor(200);
    assert.ok(red);
    assert.ok(green);
    assert.notEqual(red, green);
});

test('sessionPaceColor uses session bounds', () => {
    const red = sessionPaceColor(-100);
    const green = sessionPaceColor(100);
    assert.ok(red);
    assert.ok(green);
    assert.notEqual(red, green);
});
