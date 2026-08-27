import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {calculateWeeklyPace, calculateSessionPace, compactPanelComponents, dailyLimitIndicatorLevel, limitIndicatorColor, resolveDailyRemainingPercent} from './weekly-pace.js';

const DEFAULT_SETTINGS = {
    poll_interval_minutes: 1,
    show_session: true,
    show_daily: true,
    show_weekly: true,
    weekly_workdays: 5,
    panel_icon: 'brain',
    display_mode: 'pace',
};
const POLL_INTERVALS = [1, 5, 10, 15];
const WEEKLY_WORKDAYS = [1, 2, 3, 4, 5, 6, 7];
const DISPLAY_MODES = ['pace', 'absolute'];
const DISPLAY_MODE_LABELS = {pace: 'Ütem', absolute: 'Abszolút'};
const PANEL_COMPONENTS = [
    {key: 'session', setting: 'show_session', label: '5 órás limit', flag: 'show-session'},
    {key: 'daily', setting: 'show_daily', label: 'Napi limit', flag: 'show-daily'},
    {key: 'weekly', setting: 'show_weekly', label: 'Heti limit', flag: 'show-weekly'},
];
const ICON_OPTIONS = {
    none: {label: 'Nincs', glyph: ''},
    brain: {label: '🧠 Agy', glyph: '🧠'},
    robot: {label: '🤖 Robot', glyph: '🤖'},
    chip: {label: '💾 Chip', glyph: '💾'},
    circuit: {label: '⚙️ Áramkör', glyph: '⚙️'},
    atom: {label: '⚛️ Atom', glyph: '⚛️'},
    terminal: {label: '🖥️ Terminál', glyph: '🖥️'},
    fire: {label: '🔥 Tűz', glyph: '🔥'},
    boom: {label: '💥 Boom', glyph: '💥'},
    star: {label: '⭐ Star', glyph: '⭐'},
    sparkle: {label: '✨ Ragyogás', glyph: '✨'},
};
const HELPER = GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', 'codex-session-meter']);
const HELPER_TIMEOUT_SECONDS = 20;

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
        this._visibilityItems = new Map();
        this._weeklyWorkdayItems = new Map();
        this._panelIconItems = new Map();
        this._displayModeItems = new Map();
        this._panelComponents = null;
        this._fallbackDisplay = 'Codex: töltés…';

        this._box = new St.BoxLayout({
            style_class: 'codex-session-box',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._sessionGroup = new St.BoxLayout({
            style_class: 'codex-session-box',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._sessionLimitDot = new St.Widget({
            style_class: 'codex-session-daily-limit-dot codex-session-daily-limit-unknown',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._sessionLabel = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'codex-session-label',
        });
        this._sessionGroup.add_child(this._sessionLimitDot);
        this._sessionGroup.add_child(this._sessionLabel);

        this._dailyGroup = new St.BoxLayout({
            style_class: 'codex-session-box',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._dailyLimitDot = new St.Widget({
            style_class: 'codex-session-daily-limit-dot codex-session-daily-limit-unknown',
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._dailyLabel = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'codex-session-label',
        });
        this._dailyGroup.add_child(this._dailyLimitDot);
        this._dailyGroup.add_child(this._dailyLabel);

        this._weeklyGroup = new St.BoxLayout({
            y_align: Clutter.ActorAlign.CENTER,
        });
        this._weeklyLabel = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'codex-session-label',
        });
        this._weeklyGroup.add_child(this._weeklyLabel);

        this._componentWidgets = new Map([
            ['session', {group: this._sessionGroup, label: this._sessionLabel}],
            ['daily', {group: this._dailyGroup, label: this._dailyLabel}],
            ['weekly', {group: this._weeklyGroup, label: this._weeklyLabel}],
        ]);

        this._icon = new St.Label({
            text: ICON_OPTIONS[this._settings.panel_icon].glyph,
            style_class: 'codex-session-icon',
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._label = new St.Label({
            text: this._fallbackDisplay,
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'codex-session-label',
        });

        this._box.add_child(this._icon);
        this._box.add_child(this._sessionGroup);
        this._box.add_child(this._dailyGroup);
        this._box.add_child(this._weeklyGroup);
        this._box.add_child(this._label);
        this.add_child(this._box);

        this._statusItem = new PopupMenu.PopupMenuItem('Állapot: töltés…', {reactive: false});
        this._sessionItem = new PopupMenu.PopupMenuItem('Heti keret: töltés…', {reactive: false});
        this._resetItem = new PopupMenu.PopupMenuItem('Reset: töltés…', {reactive: false});
        this._sessionResetItem = new PopupMenu.PopupMenuItem('5 órás reset: nincs', {reactive: false});
        this._updatedItem = new PopupMenu.PopupMenuItem('Frissítve: nincs', {reactive: false});
        this._sourceItem = new PopupMenu.PopupMenuItem('Forrás: nincs', {reactive: false});
        this._messageItem = new PopupMenu.PopupMenuItem('Üzenet: nincs', {reactive: false});
        this.menu.addMenuItem(this._statusItem);
        this.menu.addMenuItem(this._sessionItem);
        this.menu.addMenuItem(this._resetItem);
        this.menu.addMenuItem(this._sessionResetItem);
        this.menu.addMenuItem(this._updatedItem);
        this.menu.addMenuItem(this._sourceItem);
        this.menu.addMenuItem(this._messageItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._addPollIntervalItems();
        this._addVisibilityItems();
        this._addWeeklyWorkdayItems();
        this._addIconItems();
        this._addDisplayModeItems();
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
        this._updatePanelComponents();
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
        const weeklyPercent = payload?.weekly_percent;
        const weeklyResetDate = payload?.weekly_reset_date_local;
        const display = payload?.display || 'Codex: ismeretlen hiba';
        const dailyRemainingPercent = this._dailyRemainingPercent(payload);
        const sessionPace = calculateSessionPace({
            sessionPercent: payload?.session_percent,
            sessionResetAt: payload?.session_reset_at,
            lastUpdated: payload?.last_updated,
            sessionWindowMins: payload?.session_window_mins,
        });
        const isPace = this._settings.display_mode === 'pace';
        const sessionDisplayPercent = isPace ? sessionPace : payload?.session_used_percent;
        this._statusItem.label.set_text(`Állapot: ${payload?.status || 'unknown'}`);
        this._applyLimitDot(this._sessionLimitDot, sessionDisplayPercent);
        this._applyLimitDot(this._dailyLimitDot, dailyRemainingPercent);
        this._panelComponents = compactPanelComponents({
            sessionPercent: sessionDisplayPercent,
            sessionResetTime: isPace ? payload?.session_reset_time_local : null,
            dailyRemainingPercent: isPace ? dailyRemainingPercent : null,
            weeklyPercent,
            weeklyResetDate,
        });
        this._fallbackDisplay = display;
        this._updatePanelComponents();
        this._sessionItem.label.set_text(`Heti keret: ${weeklyPercent ?? 'n/a'}%`);
        this._resetItem.label.set_text(`Reset: ${weeklyResetDate || 'nincs'}`);
        this._sessionResetItem.label.set_text(`5 órás reset: ${payload?.session_reset_time_local || 'nincs'}`);
        this._updatedItem.label.set_text(`Frissítve: ${payload?.last_updated ? payload.last_updated.slice(11, 16) : 'nincs'}`);
        this._sourceItem.label.set_text(`Forrás: ${payload?.source_label || 'nincs'}`);
        this._messageItem.label.set_text(`Üzenet: ${payload?.message || 'nincs'}`);
    }

    _dailyRemainingPercent(payload) {
        const workdays = WEEKLY_WORKDAYS.includes(this._settings.weekly_workdays) ? this._settings.weekly_workdays : DEFAULT_SETTINGS.weekly_workdays;
        const value = resolveDailyRemainingPercent({
            quotaRemainingPercent: Number(payload?.weekly_percent),
            resetAt: payload?.weekly_reset_at,
            lastUpdated: payload?.last_updated,
            workdays,
        });
        return value === null ? null : Math.round(value);
    }

    _applyLimitDot(dot, remainingPercent) {
        dot.set_style_class_name(`codex-session-daily-limit-dot codex-session-daily-limit-${dailyLimitIndicatorLevel(remainingPercent)}`);
        const color = limitIndicatorColor(remainingPercent);
        dot.set_style(color ? `background-color: ${color};` : '');
    }

    _updatePanelComponents() {
        const components = this._panelComponents || {};
        const isPace = this._settings.display_mode === 'pace';
        let enabledCount = 0;
        let dataCount = 0;
        for (const component of PANEL_COMPONENTS) {
            if (!this._settings[component.setting])
                continue;
            if (component.key === 'daily' && !isPace)
                continue;
            enabledCount++;
            if (components[component.key])
                dataCount++;
        }

        const showFallback = enabledCount > 0 && dataCount === 0;
        for (const component of PANEL_COMPONENTS) {
            const widget = this._componentWidgets.get(component.key);
            const visible = Boolean(this._settings[component.setting]) && !showFallback && (component.key !== 'daily' || isPace);
            widget.group.visible = visible;
            if (visible)
                widget.label.set_text(components[component.key] || '–');
        }
        this._label.visible = showFallback;
        if (showFallback)
            this._label.set_text(this._fallbackDisplay);
    }

    _calculateWeeklyPace(payload) {
        const quotaRemainingPercent = Number(payload?.weekly_percent);
        const workdays = WEEKLY_WORKDAYS.includes(this._settings.weekly_workdays) ? this._settings.weekly_workdays : DEFAULT_SETTINGS.weekly_workdays;

        return calculateWeeklyPace({
            quotaRemainingPercent,
            resetAt: payload?.weekly_reset_at,
            lastUpdated: payload?.last_updated,
            workdays,
        });
    }

    _applySettings(settings) {
        if (!settings)
            return;

        const next = {
            poll_interval_minutes: POLL_INTERVALS.includes(settings.poll_interval_minutes) ? settings.poll_interval_minutes : this._settings.poll_interval_minutes,
            show_session: typeof settings.show_session === 'boolean' ? settings.show_session : this._settings.show_session,
            show_daily: typeof settings.show_daily === 'boolean' ? settings.show_daily : this._settings.show_daily,
            show_weekly: typeof settings.show_weekly === 'boolean' ? settings.show_weekly : this._settings.show_weekly,
            weekly_workdays: WEEKLY_WORKDAYS.includes(settings.weekly_workdays) ? settings.weekly_workdays : this._settings.weekly_workdays,
            panel_icon: Object.prototype.hasOwnProperty.call(ICON_OPTIONS, settings.panel_icon) ? settings.panel_icon : this._settings.panel_icon,
            display_mode: DISPLAY_MODES.includes(settings.display_mode) ? settings.display_mode : this._settings.display_mode,
        };

        const changed = next.poll_interval_minutes !== this._settings.poll_interval_minutes || next.show_session !== this._settings.show_session || next.show_daily !== this._settings.show_daily || next.show_weekly !== this._settings.show_weekly || next.weekly_workdays !== this._settings.weekly_workdays || next.panel_icon !== this._settings.panel_icon || next.display_mode !== this._settings.display_mode;
        this._settings = next;
        this._refreshSeconds = this._settings.poll_interval_minutes * 60;
        this._applyPanelIcon();
        this._syncMenuState();
        this._updatePanelComponents();

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

    _addVisibilityItems() {
        const visibilityMenu = new PopupMenu.PopupSubMenuMenuItem('Panel megjelenítés');
        for (const component of PANEL_COMPONENTS) {
            const item = new PopupMenu.PopupSwitchMenuItem(component.label, true);
            item.connect('toggled', (source, state) => this._setComponentVisible(component, state));
            visibilityMenu.menu.addMenuItem(item);
            this._visibilityItems.set(component.key, item);
        }
        this.menu.addMenuItem(visibilityMenu);
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

    _addDisplayModeItems() {
        const displayModeMenu = new PopupMenu.PopupSubMenuMenuItem('Megjelenítés módja');
        for (const mode of DISPLAY_MODES) {
            const item = new PopupMenu.PopupMenuItem(DISPLAY_MODE_LABELS[mode]);
            item.connect('activate', () => this._setDisplayMode(mode));
            displayModeMenu.menu.addMenuItem(item);
            this._displayModeItems.set(mode, item);
        }
        this.menu.addMenuItem(displayModeMenu);
    }

    _syncMenuState() {
        for (const [minutes, item] of this._pollIntervalItems.entries()) {
            item.setOrnament?.(minutes === this._settings.poll_interval_minutes ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        }

        for (const component of PANEL_COMPONENTS) {
            const item = this._visibilityItems.get(component.key);
            item?.setToggleState?.(Boolean(this._settings[component.setting]));
        }

        for (const [days, item] of this._weeklyWorkdayItems.entries()) {
            item.setOrnament?.(days === this._settings.weekly_workdays ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        }

        for (const [iconName, item] of this._panelIconItems.entries()) {
            item.setOrnament?.(iconName === this._settings.panel_icon ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        }

        for (const [mode, item] of this._displayModeItems.entries()) {
            item.setOrnament?.(mode === this._settings.display_mode ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        }

    }

    _setPollInterval(minutes) {
        this._runJson([HELPER, 'configure', '--poll-interval', String(minutes), '--json'], payload => {
            this._applySettings(payload);
            this.refresh();
        });
    }

    _setComponentVisible(component, state) {
        this._runJson([HELPER, 'configure', `${state ? '--' : '--no-'}${component.flag}`, '--json'], payload => {
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

    _setPanelIcon(iconName) {
        this._runJson([HELPER, 'configure', '--panel-icon', iconName, '--json'], payload => {
            this._applySettings(payload);
            this.refresh();
        });
    }

    _setDisplayMode(mode) {
        this._runJson([HELPER, 'configure', '--display-mode', mode, '--json'], payload => {
            this._applySettings(payload);
            this.refresh();
        });
    }

    _applyPanelIcon() {
        const icon = ICON_OPTIONS[this._settings.panel_icon];
        this._icon.set_text(icon.glyph);
        this._icon.visible = this._settings.panel_icon !== 'none';
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
