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
    panel_icon: 'brain',
};
const POLL_INTERVALS = [1, 5, 10, 15];
const DISPLAY_FORMATS = ['verbose', 'compact'];
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

        this._label = new St.Label({
            text: 'Codex: töltés…',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'codex-session-label',
        });

        this._applyIconSettings();

        this._box.add_child(this._icon);
        this._box.add_child(this._label);
        this.add_child(this._box);

        this._statusItem = new PopupMenu.PopupMenuItem('Állapot: töltés…', {reactive: false});
        this._sessionItem = new PopupMenu.PopupMenuItem('Session: töltés…', {reactive: false});
        this._resetItem = new PopupMenu.PopupMenuItem('Reset: töltés…', {reactive: false});
        this._updatedItem = new PopupMenu.PopupMenuItem('Frissítve: nincs', {reactive: false});
        this._sourceItem = new PopupMenu.PopupMenuItem('Forrás: nincs', {reactive: false});
        this._messageItem = new PopupMenu.PopupMenuItem('Üzenet: nincs', {reactive: false});
        this.menu.addMenuItem(this._statusItem);
        this.menu.addMenuItem(this._sessionItem);
        this.menu.addMenuItem(this._resetItem);
        this.menu.addMenuItem(this._updatedItem);
        this.menu.addMenuItem(this._sourceItem);
        this.menu.addMenuItem(this._messageItem);
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._addPollIntervalItems();
        this._addFormatItems();
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
        const display = payload?.display || 'Codex: ismeretlen hiba';
        this._label.set_text(this._decorateDisplay(display));
        this._statusItem.label.set_text(`Állapot: ${payload?.status || 'unknown'}`);
        this._sessionItem.label.set_text(`Session: ${payload?.percent ?? 'n/a'}%${weeklyPercent !== null && weeklyPercent !== undefined ? ` / ${weeklyPercent}%` : ''}`);
        this._resetItem.label.set_text(`Reset: ${payload?.reset_time_local || 'nincs'} (${payload?.remaining_human_hu || 'n/a'})${weeklyResetDate ? ` / ${weeklyResetDate}` : ''}`);
        this._updatedItem.label.set_text(`Frissítve: ${payload?.last_updated ? payload.last_updated.slice(11, 16) : 'nincs'}`);
        this._sourceItem.label.set_text(`Forrás: ${payload?.source_label || 'nincs'}`);
        this._messageItem.label.set_text(`Üzenet: ${payload?.message || 'nincs'}`);
    }

    _applySettings(settings) {
        if (!settings)
            return;

        const next = {
            poll_interval_minutes: POLL_INTERVALS.includes(settings.poll_interval_minutes) ? settings.poll_interval_minutes : this._settings.poll_interval_minutes,
            display_format: DISPLAY_FORMATS.includes(settings.display_format) ? settings.display_format : this._settings.display_format,
            show_weekly_limits: typeof settings.show_weekly_limits === 'boolean' ? settings.show_weekly_limits : this._settings.show_weekly_limits,
            panel_icon: Object.prototype.hasOwnProperty.call(ICON_OPTIONS, settings.panel_icon) ? settings.panel_icon : this._settings.panel_icon,
        };

        const changed = next.poll_interval_minutes !== this._settings.poll_interval_minutes || next.display_format !== this._settings.display_format || next.show_weekly_limits !== this._settings.show_weekly_limits || next.panel_icon !== this._settings.panel_icon;
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
