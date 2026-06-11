# Codex Session Widget

Ubuntu GNOME top-panel widget for showing local Codex five-hour session progress.

Target display:

```text
Session: 62% / 89% | Reset: 14:35 (1ó 54p) / 05.29.
```

The repository contains two parts:

- `extension/`: a GNOME Shell extension written in GJS that displays the panel label, lets you set the poll interval, format, and weekly limit visibility from the menu, and refreshes on the selected interval.
- `helper/`: a Python CLI named `codex-session-widget` that owns authentication discovery, data fetching/parsing, percentage calculation, cache, and safe logs.

## Current Data-Source Status

The helper uses the Codex CLI app-server API as its primary data source. It starts `codex app-server --stdio` and calls the JSON-RPC method `account/rateLimits/read`, which returns the current primary and secondary rate-limit windows.

- Auth comes from the normal Codex CLI login at `~/.codex/auth.json` or `$CODEX_HOME/auth.json`.
- Codex usage data comes only from `codex app-server --stdio` and `account/rateLimits/read`.
- No scraping, browser profile access, cookie reading, HAR processing, Playwright, or Chromium dependency is used for normal operation.

If Codex CLI auth is missing, the widget shows `Codex: bejelentkezés kell`.

See `docs/data-source-research.md` for the exact research notes and next steps.

## Install

Requirements:

- Ubuntu GNOME Shell 45-48.
- `python3`, `python3-venv`, `pip` support.
- `gnome-extensions` CLI or Extension Manager.
- OpenAI Codex CLI available as `codex`.

Install locally, without root:

```bash
./install.sh
```

Enable:

```bash
  gnome-extensions enable codex-session-widget@local
```

If GNOME does not load it immediately, log out/in, or use Extension Manager.

## Helper Commands

```bash
codex-session-widget status --json
codex-session-widget refresh --json
codex-session-widget settings --json
codex-session-widget configure --poll-interval 5 --display-format compact --hide-weekly-limits --json
codex-session-widget login
codex-session-widget logout
codex-session-widget auth-status
codex-session-widget open-logs
```

`login` delegates to `codex login`. The widget reads the Codex CLI auth status and calls the Codex CLI app-server API; it does not use browser scraping.

The Python helper uses semantic versioning, currently `0.2.1`. The GNOME Shell `metadata.json` `version` field is a separate integer extension package version.

## Configuration

The data source is not configurable. The helper relies only on the Codex CLI app-server API.

Menu-controlled preferences are stored in `~/.config/codex-session-widget/settings.toml`.

```toml
poll_interval_minutes = 1
display_format = "verbose"
show_weekly_limits = true
panel_icon = "brain"

# panel_icon values: brain, robot, chip, circuit, atom, terminal, fire, boom, star, sparkle
```

Never commit captured HAR files, cookies, Codex auth files, tokens, auth headers, or full raw responses.

## Cache And Logs

- Last successful state: `~/.cache/codex-session-widget/state.json`
- Logs: `~/.cache/codex-session-widget/widget.log`
- Settings: `~/.config/codex-session-widget/settings.toml`

Logs avoid raw payloads, cookies, authorization headers, and other secrets.

## Before Publishing

1. Run `python -m pytest` from `helper/`, or the project virtualenv equivalent.
2. Run `TZ=UTC python -m pytest` and `TZ=Europe/Budapest python -m pytest` from `helper/`.
3. Run a secret scan for `access_token`, `refresh_token`, `Authorization`, `Bearer`, `cookie`, `session`, `api_key`, `secret`, and `password`.
4. Review `git status --short` and `git diff` before publishing.
5. Check that no `auth.json`, HAR, cookie dump, sqlite DB, `state.json`, `widget.log`, `.env`, `.pem`, or `.key` file is tracked.
6. Verify local config/cache directories are not committed: `~/.config/codex-session-widget/` and `~/.cache/codex-session-widget/`.

## Manual Verification Checklist

1. Install extension with `./install.sh`.
2. Start with no auth and verify `bejelentkezés kell` or `adatforrás kell` appears.
3. Run `codex-session-widget login` or `codex login`.
4. Run `codex-session-widget refresh --json` and verify `source_label` is `Codex CLI API` and reset time appears.
5. Enable the extension and wait at least one refresh cycle.
6. Disconnect network and verify graceful error with last successful value kept.
7. Re-enable network and verify recovery.
8. Disable extension and verify no refresh loop remains.

## Uninstall

```bash
./uninstall.sh
```

This removes the extension, helper virtualenv, and command symlink. It keeps config/cache files so debug samples are not deleted unexpectedly. Run `codex-session-widget logout` before uninstalling if you want to log out of Codex CLI.
