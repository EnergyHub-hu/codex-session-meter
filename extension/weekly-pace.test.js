import test from 'node:test';
import assert from 'node:assert/strict';

import {calculateWeeklyPace, calculateSessionPace, compactPanelComponents, dailyLimitIndicatorLevel, limitIndicatorColor, resolveDailyRemainingPercent, resolveLimitIndicatorPercents, normalizePace, paceColor, dailyPaceColor, sessionPaceColor, dailyConsumptionPace, paceToColor, weeklyConsumptionPace, weeklyPaceColor, elapsedFractionOfWeek} from './weekly-pace.js';

// ---------------------------------------------------------------------------
// Canonical model constants
// resetAt = Sunday 18:00 CEST
// weeklyStart = resetAt - 7 days = previous Sunday 18:00 CEST (shared origin)
// workdays=5 => daily horizon = 5*24h, weekly horizon = 7*24h
// workdays=3 => daily horizon = 3*24h, weekly horizon = 7*24h
// workdays=7 => daily horizon = 7*24h, weekly horizon = 7*24h
// ---------------------------------------------------------------------------

test('resolveDailyRemainingPercent delegates to calculateWeeklyPace', () => {
    const value = resolveDailyRemainingPercent({
        quotaRemainingPercent: 85,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-16T09:00:00+02:00',
        workdays: 5,
    });

    const expected = calculateWeeklyPace({
        quotaRemainingPercent: 85,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-16T09:00:00+02:00',
        workdays: 5,
    }).dailyRemainingPercent;

    assert.equal(value, expected);
});

test('returns unknown level for incomplete data', () => {
    const pace = calculateWeeklyPace({});
    assert.equal(pace.level, 'unknown');
    assert.equal(pace.quotaRemainingPercent, null);
    assert.equal(pace.elapsedWorkdays, null);
    assert.equal(pace.budgetPerWorkday, null);
});

test('resolveDailyRemainingPercent returns null for incomplete data', () => {
    assert.equal(resolveDailyRemainingPercent({}), null);
    assert.equal(resolveDailyRemainingPercent({quotaRemainingPercent: 80}), null);
});

// ---------------------------------------------------------------------------
// 1. Reset/start instant
// At window start, elapsed = 0, plannedUsage = 0%
// ---------------------------------------------------------------------------

test('at window start: zero elapsed time, 0% planned usage', () => {
    // workdays=5, weeklyStart = 2026-07-13T18:00:00+02:00 (resetAt - 7 days)
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 100,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-13T18:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedWorkdays, 0);
    assert.equal(pace.elapsedFraction, 0);
    assert.equal(pace.todayMinimumRemainingPercent, 100);
    assert.equal(pace.budgetPerWorkday, 20);
    assert.equal(pace.dailyRemainingPercent, 100);
});

// ---------------------------------------------------------------------------
// 2. One minute after reset
// 60000ms / (5*24h) = 0.0000694, plannedUsage ~0.00694%
// ---------------------------------------------------------------------------

test('one minute after window start: negligible planned usage', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 99.99,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-13T18:01:00+02:00',
        workdays: 5,
    });

    assert.ok(pace.elapsedFraction > 0);
    assert.ok(pace.elapsedFraction < 0.001);
    assert.ok(pace.todayMinimumRemainingPercent > 99.9);
    assert.ok(Math.round(pace.todayMinimumRemainingPercent) === 100);
});

// ---------------------------------------------------------------------------
// 3. Fractional first day (9 hours into window)
// elapsedDays = 9/24 = 0.375, plannedUsage = 0.375 * 20 = 7.5%
// ---------------------------------------------------------------------------

test('fractional first day: 9 hours into 7-day window', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 92.5,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T03:00:00+02:00',
        workdays: 5,
    });

    // 9h / (5*24h) = 9/120 = 0.075
    assert.ok(Math.abs(pace.elapsedFraction - 0.075) < 1e-10);
    // elapsedWorkdays = 0.075 * 5 = 0.375
    assert.ok(Math.abs(pace.elapsedWorkdays - 0.375) < 1e-10);
    // todayMinimumRemainingPercent = 100 - 0.375 * 20 = 92.5
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - 92.5) < 1e-10);
    // EOD-normalized: 7.5% used, allowedByEOD=25%, available=17.5%, divisor=20 => 87.5%
    assert.ok(Math.abs(pace.dailyRemainingPercent - 87.5) < 1e-10);
});

// ---------------------------------------------------------------------------
// 4. Exactly 24 hours after reset
// elapsedDays = 1, plannedUsage = 1 * 20 = 20%
// ---------------------------------------------------------------------------

test('exactly 24 hours after window start: 20% planned usage', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 80,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T18:00:00+02:00',
        workdays: 5,
    });

    // elapsedFraction = 24 / 120 = 0.2
    assert.ok(Math.abs(pace.elapsedFraction - 0.2) < 1e-10);
    // elapsedWorkdays = 0.2 * 5 = 1.0
    assert.ok(Math.abs(pace.elapsedWorkdays - 1.0) < 1e-10);
    // todayMinimumRemainingPercent = 100 - 1.0 * 20 = 80
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - 80) < 1e-10);
    // EOD-normalized: 20% used, allowedByEOD=25%, available=5%, divisor=20 => 25%
    assert.ok(Math.abs(pace.dailyRemainingPercent - 25) < 1e-10);
});

// ---------------------------------------------------------------------------
// 5. Multiple full days (48h = 2 days)
// elapsedDays = 2, plannedUsage = 2 * 20 = 40%
// ---------------------------------------------------------------------------

test('48 hours after window start: 40% planned usage', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 60,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 5,
    });

    // elapsedFraction = 48 / 120 = 0.4
    assert.ok(Math.abs(pace.elapsedFraction - 0.4) < 1e-10);
    // elapsedWorkdays = 0.4 * 5 = 2.0
    assert.ok(Math.abs(pace.elapsedWorkdays - 2.0) < 1e-10);
    // todayMinimumRemainingPercent = 100 - 2.0 * 20 = 60
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - 60) < 1e-10);
    // EOD-normalized: 40% used, allowedByEOD=45%, available=5%, divisor=20 => 25%
    assert.ok(Math.abs(pace.dailyRemainingPercent - 25) < 1e-10);
});

// ---------------------------------------------------------------------------
// 6. Exactly workdays * 24h (full consumption horizon)
// elapsedDays = 5, plannedUsage = 100%, todayMinimumRemainingPercent = 0
// ---------------------------------------------------------------------------

test('exactly workdays*24h: full consumption, 0% minimum remaining', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 30,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-20T18:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedFraction, 1);
    assert.equal(pace.elapsedWorkdays, 5);
    assert.equal(pace.todayMinimumRemainingPercent, 0);
    assert.equal(pace.budgetPerWorkday, 20);
    assert.equal(pace.dailyRemainingPercent, 150);
});

// ---------------------------------------------------------------------------
// 7. Time after the configured consumption horizon (clamped at 100%)
// ---------------------------------------------------------------------------

test('time after consumption horizon: planned usage capped at 100%', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 50,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-18T18:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedFraction, 1);
    assert.equal(pace.elapsedWorkdays, 5);
    assert.equal(pace.todayMinimumRemainingPercent, 0);
    assert.equal(pace.budgetPerWorkday, 20);
    // consumption horizon ends mid-day (18:00), todayDuration=18h, todayBudget=15
    // allowedByEOD=100%, actualUsage=50%, available=50%, divisor=15
    assert.ok(Math.abs(pace.dailyRemainingPercent - 50 / 15 * 100) < 1e-10);
});

test('time before window start: clamped at 0% planned usage', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 100,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-12T09:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedWorkdays, 0);
    assert.equal(pace.elapsedFraction, 0);
    assert.equal(pace.todayMinimumRemainingPercent, 100);
    assert.equal(pace.dailyRemainingPercent, 0);
});

// ---------------------------------------------------------------------------
// 8. workdays parameter actually changes pacing (3, 5, 7)
// At the same absolute time, different workdays => different planned usage
// ---------------------------------------------------------------------------

test('workdays=3: faster consumption over shorter window', () => {
    // workdays=3, weeklyStart = 2026-07-13T18:00:00+02:00 (resetAt - 7 days)
    // At 24h after weekly start: elapsedDays = 1, plannedUsage = 1/3 * 100 = 33.33%
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 66.67,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T18:00:00+02:00',
        workdays: 3,
    });

    assert.ok(Math.abs(pace.budgetPerWorkday - 100 / 3) < 1e-10);
    // elapsedFraction = 24 / 72 = 0.333...
    assert.ok(Math.abs(pace.elapsedFraction - 1 / 3) < 1e-10);
    // elapsedWorkdays = (1/3) * 3 = 1.0
    assert.ok(Math.abs(pace.elapsedWorkdays - 1.0) < 1e-10);
    // todayMinimumRemainingPercent = 100 - 1.0 * (100/3) = 66.67
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - (100 - 100 / 3)) < 0.01);
});

test('workdays=5: standard consumption over 5-day window', () => {
    // At 24h after weekly start: elapsedDays = 1, plannedUsage = 1/5 * 100 = 20%
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 80,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T18:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.budgetPerWorkday, 20);
    assert.ok(Math.abs(pace.elapsedFraction - 0.2) < 1e-10);
    assert.ok(Math.abs(pace.elapsedWorkdays - 1.0) < 1e-10);
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - 80) < 1e-10);
});

test('workdays=7: slower consumption over 7-day window', () => {
    // workdays=7, weeklyStart = 2026-07-13T18:00:00+02:00 (resetAt - 7 days)
    // At 24h after weekly start: elapsedDays = 1, plannedUsage = 1/7 * 100 = 14.29%
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 85.71,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T18:00:00+02:00',
        workdays: 7,
    });

    assert.ok(Math.abs(pace.budgetPerWorkday - 100 / 7) < 1e-10);
    // elapsedFraction = 24 / 168 = 1/7
    assert.ok(Math.abs(pace.elapsedFraction - 1 / 7) < 1e-10);
    // elapsedWorkdays = (1/7) * 7 = 1.0
    assert.ok(Math.abs(pace.elapsedWorkdays - 1.0) < 1e-10);
    // todayMinimumRemainingPercent = 100 - 1.0 * (100/7) = 85.71
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - (100 - 100 / 7)) < 0.01);
});

test('different workdays produce different planned usage at same elapsed time', () => {
    // 48 hours after weekly start (resetAt - 7 days = July 13 18:00):
    // All share the same weeklyStart, different daily horizons:
    // workdays=3: 48/72 = 66.67% planned
    // workdays=5: 48/120 = 40% planned
    // workdays=7: 48/168 = 28.57% planned
    const pace3 = calculateWeeklyPace({
        quotaRemainingPercent: 33.33,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 3,
    });
    const pace5 = calculateWeeklyPace({
        quotaRemainingPercent: 60,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 5,
    });
    const pace7 = calculateWeeklyPace({
        quotaRemainingPercent: 71.43,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 7,
    });

    // workdays=3: 48h into 72h window => 66.67% planned
    assert.ok(Math.abs(pace3.todayMinimumRemainingPercent - (100 - 100 * 2 / 3)) < 0.01);
    // workdays=5: 48h into 120h window => 40% planned
    assert.ok(Math.abs(pace5.todayMinimumRemainingPercent - 60) < 1e-10);
    // workdays=7: 48h into 168h window => 28.57% planned
    assert.ok(Math.abs(pace7.todayMinimumRemainingPercent - (100 - 100 / 7 * 2)) < 0.01);
});

// ---------------------------------------------------------------------------
// 9. Actual usage exactly on planned pace
// ---------------------------------------------------------------------------

test('actual usage exactly on planned pace: dailyRemainingPercent = 0', () => {
    // 2 days into 5-day window: allowedByEOD = 45%, actualUsage = 40%
    // available = 5%, divisor = 20, dailyRemainingPercent = 25
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 60,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 5,
    });

    assert.ok(Math.abs(pace.dailyRemainingPercent - 25) < 1e-10);
});

// ---------------------------------------------------------------------------
// 10. Actual usage below planned pace (conserving quota)
// ---------------------------------------------------------------------------

test('actual usage below planned pace: positive dailyRemainingPercent', () => {
    // 2 days into 5-day window: allowedByEOD = 45%, actualUsage = 20% (80% remaining)
    // available = 25%, divisor = 20, dailyRemainingPercent = 125
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 80,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 5,
    });

    assert.ok(Math.abs(pace.dailyRemainingPercent - 125) < 1e-10);
});

// ---------------------------------------------------------------------------
// 11. Actual usage above planned pace (overusing quota)
// ---------------------------------------------------------------------------

test('actual usage above planned pace: negative dailyRemainingPercent', () => {
    // 2 days into 5-day window: allowedByEOD = 45%, actualUsage = 60% (40% remaining)
    // available = 45-60 = -15%, divisor = 20, dailyRemainingPercent = -75
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 40,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 5,
    });

    assert.ok(Math.abs(pace.dailyRemainingPercent - (-75)) < 1e-10);
});

// ---------------------------------------------------------------------------
// 12. Clamping / boundary behavior
// ---------------------------------------------------------------------------

test('quotaRemainingPercent is clamped to 0-100', () => {
    const over = calculateWeeklyPace({
        quotaRemainingPercent: 120,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 5,
    });
    assert.equal(over.quotaRemainingPercent, 100);

    const under = calculateWeeklyPace({
        quotaRemainingPercent: -10,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 5,
    });
    assert.equal(under.quotaRemainingPercent, 0);
});

test('elapsed is clamped to 0 before window start', () => {
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

test('elapsed is clamped to workdays after window end', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 50,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-25T09:00:00+02:00',
        workdays: 5,
    });

    assert.equal(pace.elapsedWorkdays, 5);
    assert.equal(pace.todayMinimumRemainingPercent, 0);
});

// ---------------------------------------------------------------------------
// 13. Daily and weekly pace/color from corrected model
// weeklyConsumptionPace takes elapsedFraction (now window-based)
// ---------------------------------------------------------------------------

test('weeklyConsumptionPace uses window-based elapsedFraction', () => {
    // 2 days into 5-day window: elapsedFraction = 48/120 = 0.4
    // actualUsage = 40%, expectedUsage = 0.4 * 100 = 40, pace = 1.0
    const pace = weeklyConsumptionPace({quotaRemainingPercent: 60, elapsedFraction: 0.4});
    assert.ok(Math.abs(pace - 1.0) < 1e-10);
});

test('weeklyConsumptionPace: below pace', () => {
    // elapsedFraction = 0.4, actualUsage = 20%, expected = 40%
    const pace = weeklyConsumptionPace({quotaRemainingPercent: 80, elapsedFraction: 0.4});
    assert.ok(Math.abs(pace - 0.5) < 1e-10);
});

test('weeklyConsumptionPace: above pace', () => {
    // elapsedFraction = 0.4, actualUsage = 60%, expected = 40%
    const pace = weeklyConsumptionPace({quotaRemainingPercent: 40, elapsedFraction: 0.4});
    assert.ok(Math.abs(pace - 1.5) < 1e-10);
});

test('weeklyConsumptionPace returns 1.0 at window start with no usage', () => {
    assert.equal(weeklyConsumptionPace({quotaRemainingPercent: 100, elapsedFraction: 0}), 1.0);
});

test('weeklyConsumptionPace returns Infinity for usage before time', () => {
    assert.equal(weeklyConsumptionPace({quotaRemainingPercent: 95, elapsedFraction: 0}), Infinity);
});

test('weeklyConsumptionPace returns null for invalid input', () => {
    assert.equal(weeklyConsumptionPace({quotaRemainingPercent: NaN, elapsedFraction: 0.5}), null);
    assert.equal(weeklyConsumptionPace({quotaRemainingPercent: 80, elapsedFraction: NaN}), null);
});

// ---------------------------------------------------------------------------
// Key regression test: 18:00 start + 5 workdays + midnight evaluation
// 6 hours elapsed, plannedUsage = 5%, NOT 20%
// ---------------------------------------------------------------------------

test('key regression: 18:00 start, 5 workdays, midnight => only 5% planned', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 95,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T00:00:00+02:00',
        workdays: 5,
    });

    // 6h / (5*24h) = 6/120 = 0.05
    assert.ok(Math.abs(pace.elapsedFraction - 0.05) < 1e-10);
    // elapsedWorkdays = 0.05 * 5 = 0.25
    assert.ok(Math.abs(pace.elapsedWorkdays - 0.25) < 1e-10);
    // todayMinimumRemainingPercent = 100 - 0.25 * 20 = 95
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - 95) < 1e-10);
    // plannedUsage = 5%, NOT 20%
    assert.ok(Math.abs(100 - pace.todayMinimumRemainingPercent - 5) < 1e-10);
});

test('key regression: 18:00 start, 5 workdays, +24h => 20% planned', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 80,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T18:00:00+02:00',
        workdays: 5,
    });

    // 24h / (5*24h) = 24/120 = 0.2 (measured from weeklyStart = resetAt - 7d)
    assert.ok(Math.abs(pace.elapsedFraction - 0.2) < 1e-10);
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - 80) < 1e-10);
    // plannedUsage = 20%
    assert.ok(Math.abs(100 - pace.todayMinimumRemainingPercent - 20) < 1e-10);
});

// ---------------------------------------------------------------------------
// Planned usage examples from the task spec
// ---------------------------------------------------------------------------

test('planned usage grows continuously: intermediate points', () => {
    // 18:00 -> plannedUsage = 0% (at weeklyStart = resetAt - 7 days)
    const p0 = calculateWeeklyPace({
        quotaRemainingPercent: 100,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-13T18:00:00+02:00',
        workdays: 5,
    });
    assert.ok(Math.abs(100 - p0.todayMinimumRemainingPercent) < 1e-10);

    // 19:00 (1h later) -> ~0.8333%
    const p1h = calculateWeeklyPace({
        quotaRemainingPercent: 99.17,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-13T19:00:00+02:00',
        workdays: 5,
    });
    assert.ok(Math.abs(100 - p1h.todayMinimumRemainingPercent - 100 / 120) < 0.01);

    // +24h -> 20%
    const p24h = calculateWeeklyPace({
        quotaRemainingPercent: 80,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T18:00:00+02:00',
        workdays: 5,
    });
    assert.ok(Math.abs(100 - p24h.todayMinimumRemainingPercent - 20) < 1e-10);

    // +48h -> 40%
    const p48h = calculateWeeklyPace({
        quotaRemainingPercent: 60,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00',
        workdays: 5,
    });
    assert.ok(Math.abs(100 - p48h.todayMinimumRemainingPercent - 40) < 1e-10);

    // +120h -> 100%
    const p120h = calculateWeeklyPace({
        quotaRemainingPercent: 0,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-18T18:00:00+02:00',
        workdays: 5,
    });
    assert.equal(100 - p120h.todayMinimumRemainingPercent, 100);
});

// ---------------------------------------------------------------------------
// Existing helper function tests (unchanged behavior)
// ---------------------------------------------------------------------------

test('maps daily quota drops to proportional indicator steps', () => {
    assert.equal(dailyLimitIndicatorLevel(125), 'over');
    assert.equal(dailyLimitIndicatorLevel(100), '100');
    assert.equal(dailyLimitIndicatorLevel(95), '95');
    assert.equal(dailyLimitIndicatorLevel(90), '90');
    assert.equal(dailyLimitIndicatorLevel(4), '4');
    assert.equal(dailyLimitIndicatorLevel(-2), '0');
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

test('dailyConsumptionPace returns 1.0 for zero usage at day start', () => {
    assert.equal(dailyConsumptionPace({actualUsage: 0, expectedUsage: 0}), 1.0);
});

test('dailyConsumptionPace returns Infinity when usage before time', () => {
    assert.equal(dailyConsumptionPace({actualUsage: 5, expectedUsage: 0}), Infinity);
});

test('dailyConsumptionPace calculates pace correctly', () => {
    assert.equal(dailyConsumptionPace({actualUsage: 10, expectedUsage: 10}), 1.0);
    assert.equal(dailyConsumptionPace({actualUsage: 5, expectedUsage: 10}), 0.5);
    assert.equal(dailyConsumptionPace({actualUsage: 20, expectedUsage: 10}), 2.0);
});

test('dailyConsumptionPace returns null for invalid input', () => {
    assert.equal(dailyConsumptionPace({actualUsage: NaN, expectedUsage: 10}), null);
    assert.equal(dailyConsumptionPace({actualUsage: 10, expectedUsage: NaN}), null);
});

test('paceToColor returns correct colors for thresholds', () => {
    assert.equal(paceToColor(0.5), '#15803D');
    assert.equal(paceToColor(0.8), '#15803D');
    assert.equal(paceToColor(0.81), '#84CC16');
    assert.equal(paceToColor(0.95), '#FACC15');
    assert.equal(paceToColor(1.05), '#FACC15');
    assert.equal(paceToColor(1.06), '#EA580C');
    assert.equal(paceToColor(1.25), '#EA580C');
    assert.equal(paceToColor(1.26), '#B91C1C');
});

test('paceToColor returns null for invalid input', () => {
    assert.equal(paceToColor(null), null);
    assert.equal(paceToColor(NaN), null);
    assert.equal(paceToColor(Infinity), null);
});

test('weeklyPaceColor returns correct colors for thresholds', () => {
    assert.equal(weeklyPaceColor(0.5), '#15803D');
    assert.equal(weeklyPaceColor(0.8), '#15803D');
    assert.equal(weeklyPaceColor(0.81), '#84CC16');
    assert.equal(weeklyPaceColor(0.95), '#FACC15');
    assert.equal(weeklyPaceColor(1.05), '#FACC15');
    assert.equal(weeklyPaceColor(1.06), '#EA580C');
    assert.equal(weeklyPaceColor(1.25), '#EA580C');
    assert.equal(weeklyPaceColor(1.26), '#B91C1C');
});

test('weeklyPaceColor returns null for invalid input', () => {
    assert.equal(weeklyPaceColor(null), null);
    assert.equal(weeklyPaceColor(NaN), null);
    assert.equal(weeklyPaceColor(Infinity), null);
});

// ---------------------------------------------------------------------------
// elapsedFractionOfWeek: 7-day window fraction
// ---------------------------------------------------------------------------

test('elapsedFractionOfWeek returns 0 at 7 days before reset', () => {
    const f = elapsedFractionOfWeek('2026-07-20T18:00:00+02:00', '2026-07-13T18:00:00+02:00');
    assert.equal(f, 0);
});

test('elapsedFractionOfWeek returns 1 at reset time', () => {
    const f = elapsedFractionOfWeek('2026-07-20T18:00:00+02:00', '2026-07-20T18:00:00+02:00');
    assert.equal(f, 1);
});

test('elapsedFractionOfWeek returns ~0.1429 after 24h (1/7)', () => {
    const f = elapsedFractionOfWeek('2026-07-20T18:00:00+02:00', '2026-07-14T18:00:00+02:00');
    assert.ok(Math.abs(f - 1 / 7) < 1e-10);
});

test('elapsedFractionOfWeek clamps before 7-day window', () => {
    const f = elapsedFractionOfWeek('2026-07-20T18:00:00+02:00', '2026-07-10T09:00:00+02:00');
    assert.equal(f, 0);
});

test('elapsedFractionOfWeek clamps after reset', () => {
    const f = elapsedFractionOfWeek('2026-07-20T18:00:00+02:00', '2026-07-25T09:00:00+02:00');
    assert.equal(f, 1);
});

test('elapsedFractionOfWeek returns null for invalid input', () => {
    assert.equal(elapsedFractionOfWeek('', '2026-07-14T18:00:00+02:00'), null);
    assert.equal(elapsedFractionOfWeek('2026-07-20T18:00:00+02:00', ''), null);
});

// ---------------------------------------------------------------------------
// Daily vs weekly dot divergence
// daily expected = elapsed / (workdays * 24h)
// weekly expected = elapsed / (7 * 24h)
// Same actual usage, different expected => different pace values
// ---------------------------------------------------------------------------

test('daily and weekly dots produce different pace values at 24h with workdays=5', () => {
    // resetAt = Sunday 18:00, lastUpdated = Monday 18:00 (24h later)
    // workdays=5 => daily expected = 24/120 = 20%
    // 7-day      => weekly expected = 24/168 ≈ 14.29%
    // actualUsage = 20%
    const dailyFrac = 24 / (5 * 24); // 0.2
    const weeklyFrac = 24 / (7 * 24); // 1/7 ≈ 0.1429
    const actualUsage = 20;

    const dailyPace = actualUsage / (dailyFrac * 100);
    const weeklyPace = actualUsage / (weeklyFrac * 100);

    assert.ok(Math.abs(dailyPace - 1.0) < 1e-10, `daily pace should be 1.0, got ${dailyPace}`);
    assert.ok(Math.abs(weeklyPace - 7 / 5) < 1e-10, `weekly pace should be 1.4, got ${weeklyPace}`);
    assert.notEqual(dailyPace, weeklyPace);
});

test('daily on pace but weekly ahead at 24h with workdays=5 and 20% usage', () => {
    // resetAt = Sunday 18:00, lastUpdated = Monday 18:00
    const resetAt = '2026-07-20T18:00:00+02:00';
    const lastUpdated = '2026-07-14T18:00:00+02:00';

    const dailyFrac = 24 / (5 * 24); // 0.2
    const weeklyFrac = elapsedFractionOfWeek(resetAt, lastUpdated); // 1/7

    const actualUsage = 20;
    const dailyPace = dailyConsumptionPace({actualUsage, expectedUsage: dailyFrac * 100});
    const weeklyPace = weeklyConsumptionPace({quotaRemainingPercent: 80, elapsedFraction: weeklyFrac});

    assert.ok(Math.abs(dailyPace - 1.0) < 1e-10, 'daily pace = 1.0 (on pace)');
    assert.ok(weeklyPace > 1.0, `weekly pace > 1.0 (ahead), got ${weeklyPace}`);
    assert.ok(Math.abs(weeklyPace - 1.4) < 0.01, `weekly pace ≈ 1.4, got ${weeklyPace}`);
});

test('daily ahead but weekly on pace when workdays < 7 and usage matches weekly horizon', () => {
    // With the corrected model, both daily and weekly share the same weeklyStart.
    // dailyFrac = elapsed/(workdays*24h), weeklyFrac = elapsed/(7*24h).
    // dailyFrac > weeklyFrac when workdays < 7 (same elapsed, shorter denominator).
    // To get dailyPace < 1 (ahead) AND weeklyPace = 1 (on pace):
    //   actualUsage = weeklyFrac*100 (on weekly pace)
    //   dailyPace = (weeklyFrac*100) / (dailyFrac*100) = weeklyFrac/dailyFrac = workdays/7 < 1
    const resetAt = '2026-07-20T18:00:00+02:00';
    const lastUpdated = '2026-07-15T18:00:00+02:00'; // 48h after weeklyStart (July 13 18:00)

    // workdays=5: dailyFrac = 48/120 = 0.4, weeklyFrac = 48/168 ≈ 0.2857
    const dailyFrac = 48 / (5 * 24); // 0.4
    const weeklyFrac = elapsedFractionOfWeek(resetAt, lastUpdated); // 48/168 = 2/7

    // actualUsage = weeklyFrac * 100 = 200/7 ≈ 28.57% (on weekly pace)
    const actualUsage = 200 / 7;
    const dailyPace = dailyConsumptionPace({actualUsage, expectedUsage: dailyFrac * 100});
    const weeklyPace = weeklyConsumptionPace({
        quotaRemainingPercent: 100 - actualUsage,
        elapsedFraction: weeklyFrac,
    });

    assert.ok(dailyPace < 1.0, `daily pace < 1.0 (ahead on daily), got ${dailyPace}`);
    assert.ok(Math.abs(weeklyPace - 1.0) < 1e-10, `weekly pace = 1.0 (on pace), got ${weeklyPace}`);
    assert.ok(dailyPace !== weeklyPace, 'daily and weekly paces differ');
});

test('workdays=7 aligns daily and weekly horizons', () => {
    // workdays=7 => daily horizon = 7*24h = weekly horizon, both from same weeklyStart
    const resetAt = '2026-07-20T18:00:00+02:00';
    // 72h after weeklyStart = resetAt - 7*24h = Sunday July 13 18:00
    // lastUpdated = Thursday July 16 18:00
    const lastUpdated = '2026-07-16T18:00:00+02:00';

    const dailyFrac = 72 / (7 * 24); // 3/7 (72h from 7-day windowStart)
    const weeklyFrac = elapsedFractionOfWeek(resetAt, lastUpdated); // 72/168 = 3/7
    const actualUsage = 30;

    const dailyPace = dailyConsumptionPace({actualUsage, expectedUsage: dailyFrac * 100});
    const weeklyPace = weeklyConsumptionPace({quotaRemainingPercent: 70, elapsedFraction: weeklyFrac});

    assert.ok(Math.abs(dailyFrac - weeklyFrac) < 1e-10, `daily=${dailyFrac} and weekly=${weeklyFrac} fractions equal for workdays=7`);
    assert.ok(Math.abs(dailyPace - weeklyPace) < 1e-10, 'daily and weekly paces are equal for workdays=7');
});

// ---------------------------------------------------------------------------
// Regression tests: 7-day origin invariance
// ---------------------------------------------------------------------------

test('weeklyStart = resetAt - 7 days regardless of weekly_workdays', () => {
    // All three workday configs must measure elapsed from the same weeklyStart.
    const resetAt = '2026-07-20T18:00:00+02:00';
    const lastUpdated = '2026-07-15T18:00:00+02:00'; // 48h after weeklyStart

    const pace3 = calculateWeeklyPace({quotaRemainingPercent: 50, resetAt, lastUpdated, workdays: 3});
    const pace5 = calculateWeeklyPace({quotaRemainingPercent: 50, resetAt, lastUpdated, workdays: 5});
    const pace7 = calculateWeeklyPace({quotaRemainingPercent: 50, resetAt, lastUpdated, workdays: 7});

    // All measure 48h from the same weeklyStart = July 13 18:00
    // elapsedFraction differs because denominator differs (workdays * 24h)
    assert.ok(Math.abs(pace3.elapsedFraction - 48 / (3 * 24)) < 1e-10);
    assert.ok(Math.abs(pace5.elapsedFraction - 48 / (5 * 24)) < 1e-10);
    assert.ok(Math.abs(pace7.elapsedFraction - 48 / (7 * 24)) < 1e-10);

    // But elapsedMillis from weeklyStart is identical for all three
    const resetAtMillis = Date.parse(resetAt);
    const lastUpdatedMillis = Date.parse(lastUpdated);
    const weeklyStartMillis = resetAtMillis - 7 * 24 * 60 * 60 * 1000;
    const expectedElapsed = lastUpdatedMillis - weeklyStartMillis;
    assert.equal(expectedElapsed, 48 * 60 * 60 * 1000);
});

test('with workdays=5, 24h after real weekly start, daily planned usage is 20%', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 80,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-14T18:00:00+02:00', // 24h after weeklyStart (July 13 18:00)
        workdays: 5,
    });

    // elapsedFraction = 24 / (5*24) = 0.2
    assert.ok(Math.abs(pace.elapsedFraction - 0.2) < 1e-10);
    // elapsedWorkdays = 0.2 * 5 = 1.0
    assert.ok(Math.abs(pace.elapsedWorkdays - 1.0) < 1e-10);
    // todayMinimumRemainingPercent = 100 - 1.0 * 20 = 80 (20% planned usage)
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - 80) < 1e-10);
});

test('with workdays=5, 48h after real weekly start, daily planned usage is 40%', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 60,
        resetAt: '2026-07-20T18:00:00+02:00',
        lastUpdated: '2026-07-15T18:00:00+02:00', // 48h after weeklyStart (July 13 18:00)
        workdays: 5,
    });

    // elapsedFraction = 48 / 120 = 0.4
    assert.ok(Math.abs(pace.elapsedFraction - 0.4) < 1e-10);
    // elapsedWorkdays = 0.4 * 5 = 2.0
    assert.ok(Math.abs(pace.elapsedWorkdays - 2.0) < 1e-10);
    // todayMinimumRemainingPercent = 100 - 2.0 * 20 = 60 (40% planned usage)
    assert.ok(Math.abs(pace.todayMinimumRemainingPercent - 60) < 1e-10);
});

test('daily horizon reaches 100% after exactly 5 days and stays capped', () => {
    const resetAt = '2026-07-20T18:00:00+02:00';

    // Exactly 5 days (120h) after weeklyStart: 100% planned
    const at5d = calculateWeeklyPace({
        quotaRemainingPercent: 0,
        resetAt,
        lastUpdated: '2026-07-18T18:00:00+02:00', // 120h after July 13 18:00
        workdays: 5,
    });
    assert.equal(at5d.elapsedFraction, 1);
    assert.equal(at5d.todayMinimumRemainingPercent, 0);

    // 6 days (144h) after weeklyStart: still capped at 100%
    const at6d = calculateWeeklyPace({
        quotaRemainingPercent: 0,
        resetAt,
        lastUpdated: '2026-07-19T18:00:00+02:00', // 144h after July 13 18:00
        workdays: 5,
    });
    assert.equal(at6d.elapsedFraction, 1);
    assert.equal(at6d.todayMinimumRemainingPercent, 0);
});

test('weekly pacing reaches 100% only after 7 days', () => {
    const resetAt = '2026-07-20T18:00:00+02:00';

    // 6 days (144h) after weeklyStart: not yet at 100%
    const at6d = elapsedFractionOfWeek(resetAt, '2026-07-19T18:00:00+02:00');
    assert.ok(at6d < 1, `at 6d: ${at6d} < 1`);
    assert.ok(Math.abs(at6d - 144 / 168) < 1e-10);

    // 7 days (168h) after weeklyStart: exactly 100%
    const at7d = elapsedFractionOfWeek(resetAt, '2026-07-20T18:00:00+02:00');
    assert.equal(at7d, 1);
});

test('weekly_workdays=3,5,7 change daily horizon but never weeklyStart', () => {
    const resetAt = '2026-07-20T18:00:00+02:00';
    const lastUpdated = '2026-07-14T18:00:00+02:00'; // 24h after weeklyStart

    // Verify weeklyElapsedFraction is independent of workdays
    const wf3 = elapsedFractionOfWeek(resetAt, lastUpdated);
    const wf5 = elapsedFractionOfWeek(resetAt, lastUpdated);
    const wf7 = elapsedFractionOfWeek(resetAt, lastUpdated);
    assert.ok(Math.abs(wf3 - 1 / 7) < 1e-10);
    assert.ok(Math.abs(wf5 - 1 / 7) < 1e-10);
    assert.ok(Math.abs(wf7 - 1 / 7) < 1e-10);

    // Daily fractions differ because denominator differs
    const p3 = calculateWeeklyPace({quotaRemainingPercent: 80, resetAt, lastUpdated, workdays: 3});
    const p5 = calculateWeeklyPace({quotaRemainingPercent: 80, resetAt, lastUpdated, workdays: 5});
    const p7 = calculateWeeklyPace({quotaRemainingPercent: 80, resetAt, lastUpdated, workdays: 7});

    assert.ok(Math.abs(p3.elapsedFraction - 1 / 3) < 1e-10); // 24/72
    assert.ok(Math.abs(p5.elapsedFraction - 0.2) < 1e-10);    // 24/120
    assert.ok(Math.abs(p7.elapsedFraction - 1 / 7) < 1e-10);  // 24/168

    // Different planned usage from same weeklyStart
    // workdays=3: 24/72 = 33.33%, workdays=5: 24/120 = 20%, workdays=7: 24/168 = 14.29%
    assert.ok(Math.abs(p3.todayMinimumRemainingPercent - (100 - 100 / 3)) < 0.01);
    assert.ok(Math.abs(p5.todayMinimumRemainingPercent - 80) < 1e-10);
    assert.ok(Math.abs(p7.todayMinimumRemainingPercent - (100 - 100 / 7)) < 0.01);
});

test('daily-vs-weekly pace divergence still works with correct 7-day origin', () => {
    // Same weeklyStart, different horizons => different pace values
    const resetAt = '2026-07-20T18:00:00+02:00';
    const lastUpdated = '2026-07-14T18:00:00+02:00'; // 24h after weeklyStart

    // 20% actual usage: on daily pace (24/120 = 20%) but ahead of weekly pace (24/168 ≈ 14.29%)
    const actualUsage = 20;
    const dailyFrac = 24 / (5 * 24);       // 0.2
    const weeklyFrac = elapsedFractionOfWeek(resetAt, lastUpdated); // 1/7

    const dailyPace = dailyConsumptionPace({actualUsage, expectedUsage: dailyFrac * 100});
    const weeklyPace = weeklyConsumptionPace({quotaRemainingPercent: 80, elapsedFraction: weeklyFrac});

    // Daily: 20/20 = 1.0 (on pace)
    assert.ok(Math.abs(dailyPace - 1.0) < 1e-10, `daily pace = 1.0, got ${dailyPace}`);
    // Weekly: 20 / (100/7) ≈ 1.4 (ahead)
    assert.ok(weeklyPace > 1.0, `weekly pace > 1.0, got ${weeklyPace}`);
    assert.ok(Math.abs(weeklyPace - 1.4) < 0.01, `weekly pace ≈ 1.4, got ${weeklyPace}`);
});

// ---------------------------------------------------------------------------
// EOD-normalized Daily label regression tests (spec examples)
// resetAt = Friday 18:00 CEST
// weeklyStart = Friday 18:00 CEST (7 days before resetAt)
// workdays=5 => fullDayBudget=20, consumptionHorizon = weeklyStart + 120h
// First day overlap = 6h (Friday 18:00 -> Saturday 00:00)
// ---------------------------------------------------------------------------

test('partial first day with zero usage => Daily 100%', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 100,
        resetAt: '2026-05-15T18:00:00+02:00',
        lastUpdated: '2026-05-08T20:00:00+02:00',
        workdays: 5,
    });
    // weeklyStart=May8 18:00, lastUpdated=May8 20:00 (same day, 2h after start)
    // todayDuration=6h, todayBudget=5, allowedByEOD=6h/120h*100=5%
    // actualUsage=0, available=5, divisor=5 => 100%
    assert.ok(Math.abs(pace.dailyRemainingPercent - 100) < 1e-10);
});

test('partial first day half consumed => Daily 50%', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 97.5,
        resetAt: '2026-05-15T18:00:00+02:00',
        lastUpdated: '2026-05-08T20:00:00+02:00',
        workdays: 5,
    });
    // allowedByEOD=5%, actualUsage=2.5%, available=2.5%, divisor=5 => 50%
    assert.ok(Math.abs(pace.dailyRemainingPercent - 50) < 1e-10);
});

test('carry-over produces >100% Daily', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 100,
        resetAt: '2026-05-15T18:00:00+02:00',
        lastUpdated: '2026-05-09T20:00:00+02:00',
        workdays: 5,
    });
    // Saturday 20:00: allowedByEOD = 30h/120h*100 = 25%
    // actualUsage=0, available=25%, divisor=20 => 125%
    assert.ok(pace.dailyRemainingPercent > 100);
    assert.ok(Math.abs(pace.dailyRemainingPercent - 125) < 1e-10);
});

test('overconsumption produces <0% Daily', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 60,
        resetAt: '2026-05-15T18:00:00+02:00',
        lastUpdated: '2026-05-09T12:00:00+02:00',
        workdays: 5,
    });
    // Saturday 12:00: allowedByEOD = 30h/120h*100 = 25%
    // actualUsage=40%, available=-15%, divisor=20 => -75%
    assert.ok(pace.dailyRemainingPercent < 0);
    assert.ok(Math.abs(pace.dailyRemainingPercent - (-75)) < 1e-10);
});

test('Sunday 18:00 example: Daily 25%', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 60,
        resetAt: '2026-05-15T18:00:00+02:00',
        lastUpdated: '2026-05-10T18:00:00+02:00',
        workdays: 5,
    });
    // Sunday 18:00 = 54h after weeklyStart (Fri18:00)
    // allowedByEOD = 54/120*100 = 45%, actualUsage = 40%, available = 5%
    // divisor = 20, dailyRemainingPercent = 25%
    assert.ok(Math.abs(pace.dailyRemainingPercent - 25) < 1e-10);
});

test('post-horizon with 20% remaining => Daily 100%', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 20,
        resetAt: '2026-05-10T18:00:00+02:00',
        lastUpdated: '2026-05-10T12:00:00+02:00',
        workdays: 5,
    });
    // Past consumption horizon (Fri18:00), todayBudget=0, divisor=fullDayBudget=20
    // allowedByEOD=100%, actualUsage=80%, available=20%
    // dailyRemainingPercent = 20/20*100 = 100%
    assert.ok(Math.abs(pace.dailyRemainingPercent - 100) < 1e-10);
});

test('post-horizon with no remaining quota => Daily 0%', () => {
    const pace = calculateWeeklyPace({
        quotaRemainingPercent: 0,
        resetAt: '2026-05-10T18:00:00+02:00',
        lastUpdated: '2026-05-10T12:00:00+02:00',
        workdays: 5,
    });
    // allowedByEOD=100%, actualUsage=100%, available=0%, divisor=20
    // dailyRemainingPercent = 0%
    assert.ok(Math.abs(pace.dailyRemainingPercent) < 1e-10);
});

test('weekly_workdays changes Daily but never changes weeklyStart', () => {
    const resetAt = '2026-07-20T18:00:00+02:00';
    const lastUpdated = '2026-07-16T12:00:00+02:00';

    const pace3 = calculateWeeklyPace({quotaRemainingPercent: 50, resetAt, lastUpdated, workdays: 3});
    const pace5 = calculateWeeklyPace({quotaRemainingPercent: 50, resetAt, lastUpdated, workdays: 5});
    const pace7 = calculateWeeklyPace({quotaRemainingPercent: 50, resetAt, lastUpdated, workdays: 7});

    // Different workdays => different fullDayBudget => different dailyRemainingPercent
    assert.notEqual(pace3.dailyRemainingPercent, pace5.dailyRemainingPercent);
    assert.notEqual(pace5.dailyRemainingPercent, pace7.dailyRemainingPercent);

    // All share the same weeklyStart = resetAt - 7 days
    const resetAtMillis = Date.parse(resetAt);
    const expectedWeeklyStart = resetAtMillis - 7 * 24 * 60 * 60 * 1000;
    const ws3 = Date.parse(resetAt) - 7 * 24 * 60 * 60 * 1000;
    assert.equal(ws3, expectedWeeklyStart);
});

test('Daily label and Daily pace remain independent', () => {
    const resetAt = '2026-07-20T18:00:00+02:00';
    const lastUpdated = '2026-07-14T18:00:00+02:00';
    const workdays = 5;
    const quotaRemainingPercent = 80;

    const pace = calculateWeeklyPace({quotaRemainingPercent, resetAt, lastUpdated, workdays});

    // Daily pace: actualUsage / expectedUsage from time-proportional model
    const actualUsage = 100 - quotaRemainingPercent; // 20
    const dailyFrac = pace.elapsedFraction; // 24/120 = 0.2
    const dailyPaceVal = dailyConsumptionPace({actualUsage, expectedUsage: dailyFrac * 100});
    assert.ok(Math.abs(dailyPaceVal - 1.0) < 1e-10, 'daily pace = 1.0');

    // Daily label: EOD-normalized = 25%
    assert.ok(Math.abs(pace.dailyRemainingPercent - 25) < 1e-10, 'daily label = 25%');

    // They are independent: pace is 1.0 (on pace), label is 25% (not 100%)
    assert.notEqual(dailyPaceVal, pace.dailyRemainingPercent);
});

test('correct local midnight epoch', () => {
    // Europe/Budapest CEST (UTC+2): July 14 00:00 CEST = July 13 22:00 UTC
    const d = new Date(2026, 6, 14, 0, 0, 0, 0); // month is 0-indexed
    const utcEpoch = Date.UTC(2026, 6, 14, 0, 0, 0, 0);
    const localEpoch = d.getTime();
    // local midnight != UTC midnight when timezone != UTC
    assert.notEqual(localEpoch, utcEpoch);
    // CEST = UTC+2 => local midnight is 2h before UTC midnight
    assert.ok(Math.abs(localEpoch - utcEpoch + 2 * 60 * 60 * 1000) < 1000);
});

test('Europe/Budapest spring DST: 23h between consecutive local midnights', () => {
    // Spring forward: March 29 2026, 02:00 CET -> 03:00 CEST
    const before = new Date(2026, 2, 29, 0, 0, 0, 0).getTime();
    const after = new Date(2026, 2, 30, 0, 0, 0, 0).getTime();
    const diffHours = (after - before) / (60 * 60 * 1000);
    assert.ok(Math.abs(diffHours - 23) < 0.01,
        `spring DST gap should be 23h, got ${diffHours}h`);
});

test('Europe/Budapest autumn DST: 25h between consecutive local midnights', () => {
    // Fall back: October 25 2026, 03:00 CEST -> 02:00 CET
    const before = new Date(2026, 9, 25, 0, 0, 0, 0).getTime();
    const after = new Date(2026, 9, 26, 0, 0, 0, 0).getTime();
    const diffHours = (after - before) / (60 * 60 * 1000);
    assert.ok(Math.abs(diffHours - 25) < 0.01,
        `autumn DST gap should be 25h, got ${diffHours}h`);
});
