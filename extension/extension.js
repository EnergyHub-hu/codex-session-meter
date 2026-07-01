import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const DEFAULT_SETTINGS = {
    poll_interval_minutes: 1,
    display_format: 'verbose',
    show_weekly_limits: true,
    weekly_workdays: 5,
    panel_icon: 'brain',
};
const POLL_INTERVALS = [1, 5, 10, 15];
const DISPLAY_FORMATS = ['verbose', 'compact'];
const WEEKLY_WORKDAYS = [1, 2, 3, 4, 5, 6, 7];
const ICON_OPTIONS = {
    brain: {
        label: '🧠 Agy',
        glyph: '🧠',
    },
    robot: {
        label: '🤖 Robot',
        glyph: '🤖',
    },
    chip: {
        label: '💾 Chip',
        glyph: '💾',
    },
    circuit: {
        label: '⚙️ Áramkör',
        glyph: '⚙️',
    },
    atom: {
        label: '⚛️ Atom',
        glyph: '⚛️',
    },
    terminal: {
        label: '🖥️ Terminál',
        glyph: '🖥️',
    },
    fire: {
        label: '🔥 Tűz',
        glyph: '🔥',
    },
    boom: {
        label: '💥 Boom',
        glyph: '💥',
    },
    star: {
        label: '⭐ Star',
        glyph: '⭐',
    },
    sparkle: {
        label: '✨ Ragyogás',
        glyph: '✨',
    },
};
const HELPER = GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'codex-session-meter']);
const HELPER_TIMEOUT_SECONDS = 20;
const SESSION_SECONDS = 5 * 60 * 60;
const DAY_SECONDS = 24 * 60 * 60;
const WEEKLY_WINDOW_SECONDS = 7 * DAY_SECONDS;

const CodexSessionIndicator = GObject.registerClass(class CodexSessionIndicator extends PanelMenu.Button {

    constructor() {
        super(0.0, 'Codex Session Widget');

        this._timerId = 0;
        this._helperTimeoutIds = new Set();
        this._helperProcesses = new Set();
        this._running = false;
        this._lastSuccess = null;
        this._settings = {...DEFAULT_SETTINGS};
        this._refreshSeconds = this._settings.poll_interval_minutes * 60;
        this._pollIntervalItems = new Map();
        this._formatItems = new Map();
        this._weeklyWorkdayItems = new Map();
        this._panelIconItems = new Map();
        this._panelIconGlyph = ICON_OPTIONS[this._settings.panel_icon].glyph;

        this._box = new St.BoxLayout({
            style_class: 'codex-session-box',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._icon = new St.Label({
            text: this._panelIconGlyph,
            style_class: 'codex-session-icon',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._paceDot = new St.Widget({
            style_class: 'codex-session-pace-dot codex-session-pace-unknown',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._weeklyPaceDot = new St.Widget({
            style_class: 'codex-session-weekly-pace-dot codex-session-pace-unknown',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._label = new St.Label({
            text: 'Codex: töltés…',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'codex-session-label',
        });

        this._applyIconSettings();

        this._box.add_child(this._icon);
        this._box.add_child(this._paceDot);
        this._box.add_child(this._weeklyPaceDot);
        this._box.add_child(this._label);
        this.add_child(this._box);

        this._statusItem = new PopupMenu.PopupMenuItem('Állapot: töltés…', {reactive: false});
        this._sessionItem = new PopupMenu.PopupMenuItem('Session: töltés…', {reactive: false});
        this._paceItem = new PopupMenu.PopupMenuItem('Fogyási tempó: töltés…', {reactive: false});
        this._weeklyPaceItem = new PopupMenu.PopupMenuItem('Heti fogyási tempó: töltés…', {reactive: false});
        this._resetItem = new PopupMenu.PopupMenuItem('Reset: töltés…', {reactive: false});
        this._updatedItem = new PopupMenu.PopupMenuItem('Frissítve: nincs', {reactive: false});
        this._sourceItem = new PopupMenu.PopupMenuItem('Forrás: nincs', {reactive: false});
        this._messageItem = new PopupMenu.PopupMenuItem('Üzenet: nincs', {reactive: false});
        this.menu.addMenuItem(this._statusItem);
        this.menu.addMenuItem(this._sessionItem);
        this.menu.addMenuItem(this._paceItem);
        this.menu.addMenuItem(this._weeklyPaceItem);
        this.menu.addMenuItem(this._resetItem);
        this.menu.addMenuItem(this._updatedItem);
        this.menu.addMenuItem(this._sourceItem);
        this.menu.addMenuItem(this._messageItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._addPollIntervalItems();
        this._addFormatItems();
        this._addWeeklyWorkdayItems();
        this._addIconItems();
        this._showWeeklyLimitsItem = this._addToggleItem('Heti limitek megjelenítése', this._settings.show_weekly_limits, enabled => this._setWeeklyLimits(enabled));
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        const refreshItem = new PopupMenu.PopupMenuItem('Refresh now');
        refreshItem.connect('activate', () => this.refresh());
        this.menu.addMenuItem(refreshItem);

        const loginItem = new PopupMenu.PopupMenuItem('Sign in to Codex usage');
        loginItem.connect('activate', () => this._runCommand([HELPER, 'login']));
        this.menu.addMenuItem(loginItem);

        const logsItem = new PopupMenu.PopupMenuItem('Open logs');
        logsItem.connect('activate', () => this._runCommand([HELPER, 'open-logs']));
        this.menu.addMenuItem(logsItem);

        this._syncMenuState();
    }

    start() {
        this._scheduleRefresh();
        this.refresh();
    }

    stop() {
        if (this._timerId) {
            GLib.Source.remove(this._timerId);
            this._timerId = 0;
        }
        for (const timeoutId of this._helperTimeoutIds)
            GLib.Source.remove(timeoutId);
        this._helperTimeoutIds.clear();

        for (const proc of this._helperProcesses) {
            try {
                if (!proc.get_if_exited())
                    proc.force_exit();
            } catch (error) {
                // Ignore shutdown races while GNOME Shell disables the extension.
            }
        }
        this._helperProcesses.clear();
        this._running = false;
    }

    refresh() {
        if (this._running)
            return;

        this._running = true;
        this._runJson([HELPER, 'refresh', '--json'], payload => {
            this._running = false;
            this._applySettings(payload?.settings);
            this._applyPayload(payload);
        });
    }

    _applyPayload(payload) {
        const showWeeklyLimits = payload?.settings?.show_weekly_limits ?? this._settings.show_weekly_limits;
        const weeklyPercent = showWeeklyLimits ? payload?.weekly_percent : null;
        const weeklyResetDate = showWeeklyLimits ? payload?.weekly_reset_date_local : null;
        const pace = this._calculateSessionPace(payload);
        const weeklyPace = this._calculateWeeklyPace(payload, showWeeklyLimits);
        const display = payload?.display || 'Codex: ismeretlen hiba';
        this._label.set_text(this._decorateDisplay(display));
        this._applyPaceDot(pace);
        this._applyWeeklyPaceDot(weeklyPace);
        this._statusItem.label.set_text(`Állapot: ${payload?.status || 'unknown'}`);
        this._sessionItem.label.set_text(`Session: ${payload?.percent ?? 'n/a'}%${weeklyPercent !== null && weeklyPercent !== undefined ? ` / ${weeklyPercent}%` : ''}`);
        this._paceItem.label.set_text(this._formatPaceText(pace));
        this._weeklyPaceItem.label.set_text(this._formatWeeklyPaceText(weeklyPace));
        this._resetItem.label.set_text(`Reset: ${payload?.reset_time_local || 'nincs'} (${payload?.remaining_human_hu || 'n/a'})${weeklyResetDate ? ` / ${weeklyResetDate}` : ''}`);
        this._updatedItem.label.set_text(`Frissítve: ${payload?.last_updated ? payload.last_updated.slice(11, 16) : 'nincs'}`);
        this._sourceItem.label.set_text(`Forrás: ${payload?.source_label || 'nincs'}`);
        this._messageItem.label.set_text(`Üzenet: ${payload?.message || 'nincs'}`);
    }

    _calculateSessionPace(payload) {
        const quotaRemainingPercent = Number(payload?.percent);
        const remainingSeconds = Number(payload?.remaining_seconds);

        if (!Number.isFinite(quotaRemainingPercent) || !Number.isFinite(remainingSeconds)) {
            return {
                level: 'unknown',
                quotaRemainingPercent: null,
                timeRemainingPercent: null,
                delta: null,
            };
        }

        const boundedQuotaRemainingPercent = Math.max(0, Math.min(100, quotaRemainingPercent));
        const boundedRemainingSeconds = Math.max(0, Math.min(SESSION_SECONDS, remainingSeconds));
        const timeRemainingPercent = (boundedRemainingSeconds / SESSION_SECONDS) * 100;
        const delta = boundedQuotaRemainingPercent - timeRemainingPercent;

        let level = 'neutral';
        if (delta >= 15)
            level = 'excellent';
        else if (delta >= 5)
            level = 'good';
        else if (delta < -15)
            level = 'critical';
        else if (delta < -5)
            level = 'warning';

        return {
            level,
            quotaRemainingPercent: boundedQuotaRemainingPercent,
            timeRemainingPercent,
            delta,
        };
    }

    _calculateWeeklyPace(payload, showWeeklyLimits) {
        if (!showWeeklyLimits) {
            return {
                hidden: true,
                level: 'unknown',
                quotaRemainingPercent: null,
                expectedQuotaRemainingPercent: null,
                delta: null,
                startedWorkdays: null,
                workdays: this._settings.weekly_workdays,
                budgetPerWorkday: null,
            };
        }

        const quotaRemainingPercent = Number(payload?.weekly_percent);
        const resetAtMillis = Date.parse(payload?.weekly_reset_at || '');
        const lastUpdatedMillis = Date.parse(payload?.last_updated || '');
        const workdays = WEEKLY_WORKDAYS.includes(this._settings.weekly_workdays) ? this._settings.weekly_workdays : DEFAULT_SETTINGS.weekly_workdays;

        if (!Number.isFinite(quotaRemainingPercent) || !Number.isFinite(resetAtMillis) || !Number.isFinite(lastUpdatedMillis)) {
            return {
                hidden: false,
                level: 'unknown',
                quotaRemainingPercent: null,
                expectedQuotaRemainingPercent: null,
                delta: null,
                startedWorkdays: null,
                workdays,
                budgetPerWorkday: null,
            };
        }

        const boundedQuotaRemainingPercent = Math.max(0, Math.min(100, quotaRemainingPercent));
        const windowStartMillis = resetAtMillis - (WEEKLY_WINDOW_SECONDS * 1000);
        const elapsedSeconds = Math.max(0, Math.min(WEEKLY_WINDOW_SECONDS, (lastUpdatedMillis - windowStartMillis) / 1000));
        const startedCalendarDays = elapsedSeconds <= 0 ? 0 : Math.floor(elapsedSeconds / DAY_SECONDS) + 1;
        const startedWorkdays = Math.max(0, Math.min(workdays, startedCalendarDays));
        const budgetPerWorkday = 100 / workdays;
        const allowedUsedPercent = Math.min(100, startedWorkdays * budgetPerWorkday);
        const expectedQuotaRemainingPercent = Math.max(0, 100 - allowedUsedPercent);
        const delta = boundedQuotaRemainingPercent - expectedQuotaRemainingPercent;

        let level = 'good';
        if (delta >= 15)
            level = 'excellent';
        else if (delta < -15)
            level = 'critical';
        else if (delta < -5)
            level = 'warning';

        return {
            hidden: false,
            level,
            quotaRemainingPercent: boundedQuotaRemainingPercent,
            expectedQuotaRemainingPercent,
            delta,
            startedWorkdays,
            workdays,
            budgetPerWorkday,
        };
    }

    _applyPaceDot(pace) {
        this._paceDot.set_style_class_name(`codex-session-pace-dot codex-session-pace-${pace.level}`);
    }

    _applyWeeklyPaceDot(pace) {
        if (pace.hidden) {
            this._weeklyPaceDot.hide();
            return;
        }
        this._weeklyPaceDot.show();
        this._weeklyPaceDot.set_style_class_name(`codex-session-weekly-pace-dot codex-session-pace-${pace.level}`);
    }

    _formatPaceText(pace) {
        if (pace.delta === null)
            return 'Fogyási tempó: n/a';

        const roundedDelta = Math.round(pace.delta);
        const timePercent = Math.round(pace.timeRemainingPercent);
        const quotaPercent = Math.round(pace.quotaRemainingPercent);

        if (roundedDelta >= 5) {
            return `Fogyási tempó: ${roundedDelta}%-kal jobb az időarányosnál (idő ${timePercent}%, keret ${quotaPercent}%)`;
        }
        if (roundedDelta <= -5) {
            return `Fogyási tempó: ${Math.abs(roundedDelta)}%-kal gyorsabb az időarányosnál (idő ${timePercent}%, keret ${quotaPercent}%)`;
        }
        return `Fogyási tempó: időarányos (idő ${timePercent}%, keret ${quotaPercent}%)`;
    }

    _formatWeeklyPaceText(pace) {
        if (pace.hidden)
            return 'Heti fogyási tempó: rejtve';
        if (pace.delta === null)
            return 'Heti fogyási tempó: n/a';

        const roundedDelta = Math.round(pace.delta);
        const quotaPercent = Math.round(pace.quotaRemainingPercent);
        const expectedPercent = Math.round(pace.expectedQuotaRemainingPercent);
        const dailyBudget = Math.round(pace.budgetPerWorkday);
        const workdayText = `${pace.startedWorkdays}/${pace.workdays} munkanap`;

        if (roundedDelta >= 5) {
            return `Heti fogyási tempó: ${roundedDelta}%-kal jobb a munkanap-arányosnál (keret ${quotaPercent}%, elvárt min. ${expectedPercent}%, ${workdayText}, napi keret ${dailyBudget}%)`;
        }
        if (roundedDelta <= -5) {
            return `Heti fogyási tempó: ${Math.abs(roundedDelta)}%-kal gyorsabb a munkanap-arányosnál (keret ${quotaPercent}%, elvárt min. ${expectedPercent}%, ${workdayText}, napi keret ${dailyBudget}%)`;
        }
        return `Heti fogyási tempó: munkanap-arányos (keret ${quotaPercent}%, elvárt min. ${expectedPercent}%, ${workdayText}, napi keret ${dailyBudget}%)`;
    }

    _applySettings(settings) {
        if (!settings)
            return;

        const next = {
            poll_interval_minutes: POLL_INTERVALS.includes(settings.poll_interval_minutes) ? settings.poll_interval_minutes : this._settings.poll_interval_minutes,
            display_format: DISPLAY_FORMATS.includes(settings.display_format) ? settings.display_format : this._settings.display_format,
            show_weekly_limits: typeof settings.show_weekly_limits === 'boolean' ? settings.show_weekly_limits : this._settings.show_weekly_limits,
            weekly_workdays: WEEKLY_WORKDAYS.includes(settings.weekly_workdays) ? settings.weekly_workdays : this._settings.weekly_workdays,
            panel_icon: Object.prototype.hasOwnProperty.call(ICON_OPTIONS, settings.panel_icon) ? settings.panel_icon : this._settings.panel_icon,
        };

        const changed = next.poll_interval_minutes !== this._settings.poll_interval_minutes || next.display_format !== this._settings.display_format || next.show_weekly_limits !== this._settings.show_weekly_limits || next.weekly_workdays !== this._settings.weekly_workdays || next.panel_icon !== this._settings.panel_icon;
        this._settings = next;
        this._refreshSeconds = this._settings.poll_interval_minutes * 60;
        this._applyIconSettings();
        this._syncMenuState();

        if (changed)
            this._scheduleRefresh();
    }

    _scheduleRefresh() {
        if (this._timerId) {
            GLib.Source.remove(this._timerId);
            this._timerId = 0;
        }

        this._timerId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, this._refreshSeconds, () => {
            this.refresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _addPollIntervalItems() {
        this.menu.addMenuItem(new PopupMenu.PopupMenuItem('Poll interval', {reactive: false}));
        for (const minutes of POLL_INTERVALS) {
            const item = new PopupMenu.PopupMenuItem(`${minutes} min`);
            item.connect('activate', () => this._setPollInterval(minutes));
            this.menu.addMenuItem(item);
            this._pollIntervalItems.set(minutes, item);
        }
    }

    _addFormatItems() {
        this.menu.addMenuItem(new PopupMenu.PopupMenuItem('Display format', {reactive: false}));
        for (const format of DISPLAY_FORMATS) {
            const label = format === 'verbose' ? 'Verbose' : 'Kompakt';
            const item = new PopupMenu.PopupMenuItem(label);
            item.connect('activate', () => this._setDisplayFormat(format));
            this.menu.addMenuItem(item);
            this._formatItems.set(format, item);
        }
    }

    _addWeeklyWorkdayItems() {
        const weeklyWorkdayMenu = new PopupMenu.PopupSubMenuMenuItem('Heti munkanapok');
        for (const days of WEEKLY_WORKDAYS) {
            const item = new PopupMenu.PopupMenuItem(`${days} nap`);
            item.connect('activate', () => this._setWeeklyWorkdays(days));
            weeklyWorkdayMenu.menu.addMenuItem(item);
            this._weeklyWorkdayItems.set(days, item);
        }
        this.menu.addMenuItem(weeklyWorkdayMenu);
    }

    _addIconItems() {
        const panelIconMenu = new PopupMenu.PopupSubMenuMenuItem('Panel ikon');
        for (const [iconName, option] of Object.entries(ICON_OPTIONS)) {
            const item = new PopupMenu.PopupMenuItem(option.label);
            item.connect('activate', () => this._setPanelIcon(iconName));
            panelIconMenu.menu.addMenuItem(item);
            this._panelIconItems.set(iconName, item);
        }
        this.menu.addMenuItem(panelIconMenu);
    }

    _addToggleItem(label, initialValue, onActivate) {
        const item = new PopupMenu.PopupMenuItem(label);
        item.connect('activate', () => onActivate(!this._settings.show_weekly_limits));
        this.menu.addMenuItem(item);
        item._toggleValue = initialValue;
        return item;
    }

    _syncMenuState() {
        for (const [minutes, item] of this._pollIntervalItems.entries()) {
            item.setOrnament?.(minutes === this._settings.poll_interval_minutes ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        }

        for (const [format, item] of this._formatItems.entries()) {
            item.setOrnament?.(format === this._settings.display_format ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        }

        for (const [days, item] of this._weeklyWorkdayItems.entries()) {
            item.setOrnament?.(days === this._settings.weekly_workdays ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        }

        for (const [iconName, item] of this._panelIconItems.entries()) {
            item.setOrnament?.(iconName === this._settings.panel_icon ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        }

        this._showWeeklyLimitsItem.setOrnament?.(this._settings.show_weekly_limits ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
    }

    _setPollInterval(minutes) {
        this._runJson([HELPER, 'configure', '--poll-interval', String(minutes), '--json'], payload => {
            this._applySettings(payload);
            this.refresh();
        });
    }

    _setDisplayFormat(format) {
        this._runJson([HELPER, 'configure', '--display-format', format, '--json'], payload => {
            this._applySettings(payload);
            this.refresh();
        });
    }

    _setPanelIcon(iconName) {
        this._runJson([HELPER, 'configure', '--panel-icon', iconName, '--json'], payload => {
            this._applySettings(payload);
            this.refresh();
        });
    }

    _setWeeklyLimits(enabled) {
        const flag = enabled ? '--show-weekly-limits' : '--hide-weekly-limits';
        this._runJson([HELPER, 'configure', flag, '--json'], payload => {
            this._applySettings(payload);
            this.refresh();
        });
    }

    _setWeeklyWorkdays(days) {
        this._runJson([HELPER, 'configure', '--weekly-workdays', String(days), '--json'], payload => {
            this._applySettings(payload);
            this.refresh();
        });
    }

    _decorateDisplay(display) {
        return display;
    }

    _applyIconSettings() {
        const panelIcon = ICON_OPTIONS[this._settings.panel_icon] ?? ICON_OPTIONS.brain;

        this._panelIconGlyph = panelIcon.glyph;
        this._icon.set_text(this._panelIconGlyph);
    }

    _runJson(argv, callback) {
        let proc;
        try {
            proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
        } catch (error) {
            callback({
                ok: false,
                status: 'unknown',
                display: 'Codex: helper hiányzik',
                message: String(error),
            });
            return;
        }

        this._helperProcesses.add(proc);
        let completed = false;
        let timeoutId = 0;
        const finish = payload => {
            if (completed)
                return;
            completed = true;
            if (timeoutId) {
                GLib.Source.remove(timeoutId);
                this._helperTimeoutIds.delete(timeoutId);
                timeoutId = 0;
            }
            this._helperProcesses.delete(proc);
            callback(payload);
        };

        timeoutId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, HELPER_TIMEOUT_SECONDS, () => {
            const firedTimeoutId = timeoutId;
            timeoutId = 0;
            this._helperTimeoutIds.delete(firedTimeoutId);
            try {
                if (!proc.get_if_exited())
                    proc.force_exit();
            } catch (error) {
                // The communicate callback may be racing this watchdog.
            }
            finish({
                ok: false,
                status: 'timeout',
                display: 'Codex: időtúllépés',
                message: 'Helper timed out while refreshing Codex usage.',
            });
            return GLib.SOURCE_REMOVE;
        });
        this._helperTimeoutIds.add(timeoutId);

        proc.communicate_utf8_async(null, null, (source, result) => {
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (stdout && stdout.trim()) {
                    finish(JSON.parse(stdout.trim()));
                    return;
                }
                finish({
                    ok: false,
                    status: 'unknown',
                    display: 'Codex: nincs válasz',
                    message: 'Helper returned no JSON.',
                });
            } catch (error) {
                finish({
                    ok: false,
                    status: 'unknown',
                    display: 'Codex: hibás válasz',
                    message: 'Helper returned invalid JSON.',
                });
            }
        });
    }

    _runCommand(argv) {
        try {
            Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
        } catch (error) {
            Main.notify('Codex Session Widget', String(error));
        }
    }
});

export default class CodexSessionExtension extends Extension {
    enable() {
        this._indicator = new CodexSessionIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator, 1, 'right');
        this._indicator.start();
    }

    disable() {
        if (this._indicator) {
            this._indicator.stop();
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}