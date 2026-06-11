# Troubleshooting

## Panel Shows `Codex: helper hiányzik`

GNOME Shell cannot find `codex-session-widget`.

Check:

```bash
~/.local/bin/codex-session-widget status --json
```

If that works, make sure `~/.local/bin` is in the PATH visible to GNOME Shell, then log out and back in.

## Panel Shows `Codex: bejelentkezés kell`

Run:

```bash
codex-session-widget login
```

A dedicated browser window opens. Sign in to ChatGPT/Codex there, then close the browser window so the helper can save its standalone session state.

If Chromium is missing, reinstall with `./install.sh` or run:

```bash
~/.local/share/codex-session-widget/venv/bin/python -m playwright install chromium
```

To reset the widget-owned session:

```bash
codex-session-widget logout
codex-session-widget login
```

## Panel Shows `Codex: adatforrás kell`

Auth appears present, but the Codex CLI API did not return rate-limit data. Run `codex doctor` and `codex app-server --help` to verify the installed CLI supports the app-server API. Optional fallback sources can still be configured with `json_endpoint` or `sample_file` in `~/.config/codex-session-widget/config.toml`.

## GNOME Extension Does Not Appear

Run:

```bash
gnome-extensions list | grep codex-session-widget
gnome-extensions enable codex-session-widget@local
```

If it still does not appear, log out/in or use Extension Manager.

## Inspect Logs

```bash
codex-session-widget open-logs
```

or:

```bash
less ~/.cache/codex-session-widget/widget.log
```

Logs should avoid raw payloads, cookies, authorization headers, and other secrets.
