import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class CodexSessionPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({title: 'Codex Session Widget'});
        const row = new Adw.ActionRow({
            title: 'Configuration',
            subtitle: 'Edit ~/.config/codex-session-widget/config.toml for a discovered https://chatgpt.com or *.openai.com json_endpoint, and use the panel menu for poll interval, display format, and weekly limit visibility.',
        });
        group.add(row);
        page.add(group);
        window.add(page);

        const sizeGroup = new Gtk.SizeGroup({mode: Gtk.SizeGroupMode.HORIZONTAL});
        sizeGroup.add_widget(row);
    }
}
