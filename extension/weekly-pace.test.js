import test from 'node:test';
import assert from 'node:assert/strict';

import {calculateWeeklyPace, dailyLimitIndicatorLevel, formatPanelDisplay} from './weekly-pace.js';

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

test('maps daily remaining quota to ten-percent indicator steps', () => {
    assert.equal(dailyLimitIndicatorLevel(125), 'over');
    assert.equal(dailyLimitIndicatorLevel(100), '100');
    assert.equal(dailyLimitIndicatorLevel(91), '100');
    assert.equal(dailyLimitIndicatorLevel(90), '90');
    assert.equal(dailyLimitIndicatorLevel(4), '10');
    assert.equal(dailyLimitIndicatorLevel(-2), '0');
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
