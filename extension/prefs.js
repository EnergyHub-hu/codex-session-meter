import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class CodexSessionPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({title: 'Codex Session Meter'});
        const row = new Adw.ActionRow({
            title: 'Configuration',
            subtitle: 'The data source is Codex CLI only. Use the panel menu for poll interval, display format, icon, and weekly limit visibility.',
        });
        group.add(row);
        page.add(group);
        window.add(page);

        const sizeGroup = new Gtk.SizeGroup({mode: Gtk.SizeGroupMode.HORIZONTAL});
        sizeGroup.add_widget(row);
    }
}
