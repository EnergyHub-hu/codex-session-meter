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

This delegates to `codex login`. Complete the normal Codex CLI sign-in flow, then run:

```bash
codex-session-widget auth-status
```

The helper only checks whether the Codex CLI auth file exists and contains an access token. It does not print the token and does not read browser profiles, cookies, HAR files, Playwright state, or Chromium data.

To reset Codex CLI auth, use:

```bash
codex-session-widget logout
codex-session-widget login
```

or run the Codex CLI commands directly:

```bash
codex logout
codex login
```

## Panel Shows `Codex: adatforrás kell`

Auth appears present, but the Codex CLI API did not return rate-limit data. Run `codex doctor` and `codex app-server --help` to verify the installed CLI supports the app-server API.

The only data source is `codex app-server --stdio` with JSON-RPC method `account/rateLimits/read`. There is no sample file, browser profile, cookie, or alternate data-source path.

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
