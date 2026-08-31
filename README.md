# Codex Weekly Meter

Ubuntu GNOME top-panel extension for tracking the remaining Codex quota and the planned consumption pace.

The panel can show three independently configurable components:

- **5-hour session**: remaining percentage and its local reset time.
- **Daily pace**: the percentage of today's planned budget that remains. Values above 100% mean consumption is below the planned pace; negative values mean it is above the planned pace.
- **Weekly quota**: remaining percentage and the local weekly reset date.

The repository contains two parts:

- `extension/`: GNOME Shell extension written in GJS. It renders the panel and menu, schedules refreshes, and invokes the helper.
- `helper/`: Python CLI named `codex-session-meter`. It discovers Codex CLI auth, retrieves and normalizes quota data, manages settings and cache, and writes safe logs.

## Data Source And Privacy

The helper uses the Codex CLI app-server API only. It starts `codex app-server --stdio`, sends JSON-RPC `initialize`, then calls `account/rateLimits/read`. The returned `rateLimits.primary` window is treated as the weekly quota.

- Authentication comes from the normal Codex CLI login at `$CODEX_HOME/auth.json` or `~/.codex/auth.json`.
- The helper delegates `login` and `logout` to the Codex CLI; it never prints token values.
- No direct HTTP client, scraping, browser-profile access, cookie reading, HAR processing, Playwright, or Chromium dependency is used.
- If a refresh fails, the helper preserves the last successful cached status when available.

If Codex CLI authentication is missing, the panel shows `Codex: bejelentkezés kell`.

See `docs/data-source-research.md` for the data-source design and `docs/auth-research.md` for authentication research notes.

## Install

Requirements:

- Ubuntu GNOME Shell 45-48.
- `python3` with `venv` and `pip` support.
- OpenAI Codex CLI available as `codex`.
- `gnome-extensions` CLI or Extension Manager.

Install locally without root:

```bash
./install.sh
```

Enable the extension:

```bash
gnome-extensions enable codex-session-meter@local
```

Sign in, if needed, and check that quota data can be read:

```bash
codex-session-meter login
codex-session-meter refresh --json
```

GNOME Shell must be able to find `~/.local/bin/codex-session-meter`. If the extension does not appear or the helper is missing, log out and back in, then enable it again with Extension Manager or `gnome-extensions`.

## Panel Menu

Open the panel indicator to:

- refresh quota data immediately;
- start the Codex CLI login flow;
- open the safe local log;
- select a polling interval of 1, 5, 10, or 15 minutes;
- show or hide the session, daily, and weekly panel components independently;
- set the daily pace horizon to 1-7 calendar days;
- select a panel icon.

The daily pace horizon controls how the weekly quota is allocated for pace calculations. It does not change the quota window returned by Codex.

## Helper Commands

### Status And Authentication

```bash
codex-session-meter status --json
codex-session-meter refresh --json
codex-session-meter auth-status
codex-session-meter login
codex-session-meter logout
```

`status` reads the cached state; `refresh` reads the Codex CLI API and updates the cache on success. `login` delegates to `codex login`, and `logout` delegates to `codex logout`.

### Settings

```bash
codex-session-meter settings --json
codex-session-meter configure --poll-interval 5 --json
codex-session-meter configure --no-show-session --weekly-workdays 5 --panel-icon terminal --json
```

Supported `configure` options:

```text
--poll-interval 1|5|10|15
--show-session / --no-show-session
--show-daily / --no-show-daily
--show-weekly / --no-show-weekly
--weekly-workdays 1..7
--panel-icon none|brain|robot|chip|circuit|atom|terminal|fire|boom|star|sparkle
--display-mode pace|absolute
```

`display_mode` is stored and returned by the helper, but the current GNOME extension does not apply it to the panel. It therefore has no visible effect yet.

### Logs And Diagnostics

```bash
codex-session-meter open-logs
codex-session-meter debug
codex-session-meter debug --no-color --width 80
codex-session-meter debug --copy
```

`debug` provides a terminal view of the session, daily, and weekly pace calculations. `--copy` renders the diagnostic output to a supported clipboard command without printing it.

## Configuration And Local Files

Settings are stored in `~/.config/codex-session-meter/settings.toml`:

```toml
poll_interval_minutes = 1
show_session = true
show_daily = true
show_weekly = true
weekly_workdays = 5
panel_icon = "brain"
display_mode = "pace"
```

Local paths:

- Settings: `~/.config/codex-session-meter/settings.toml`
- Last successful state: `~/.cache/codex-session-meter/state.json`
- Logs: `~/.cache/codex-session-meter/widget.log`

The helper creates its configuration, cache, and data directories with owner-only permissions. Logs avoid raw payloads, cookies, authorization headers, and other secrets.

Never commit Codex auth files, tokens, headers, cookies, HAR files, full raw responses, local state, or logs.

## Troubleshooting

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for detailed instructions.

| Panel message | Meaning | First check |
| --- | --- | --- |
| `Codex: helper hiányzik` | GNOME Shell cannot find the helper. | Run `~/.local/bin/codex-session-meter status --json` and ensure `~/.local/bin` is in GNOME Shell's PATH. |
| `Codex: bejelentkezés kell` | Codex CLI authentication is missing. | Run `codex-session-meter login`, then `codex-session-meter auth-status`. |
| `Codex: adatforrás kell` | Auth appears present, but the Codex CLI API did not return rate-limit data. | Run `codex doctor` and `codex app-server --help`. |

The only supported data source remains `codex app-server --stdio` with `account/rateLimits/read`; the widget does not fall back to another source.

## Development And Publishing

The helper uses semantic versioning. The GNOME Shell `metadata.json` `version` field is a separate integer extension package version.

Before publishing:

1. Run `python -m pytest` from `helper/`.
2. Run `TZ=UTC python -m pytest` and `TZ=Europe/Budapest python -m pytest` from `helper/`.
3. Run `node --test extension/weekly-pace.test.js` from the repository root.
4. Scan for `access_token`, `refresh_token`, `Authorization`, `Bearer`, `cookie`, `session`, `api_key`, `secret`, and `password`.
5. Review `git status --short` and `git diff`; confirm that no auth, cache, log, `.env`, key, certificate, or browser-data file is included.

Changes are recorded in [CHANGELOG.md](CHANGELOG.md).

## Uninstall

```bash
./uninstall.sh
```

This disables and removes the extension, helper virtual environment, and command symlink. It retains `~/.config/codex-session-meter` and `~/.cache/codex-session-meter` for safety. Run `codex-session-meter logout` before uninstalling if you also want to sign out of Codex CLI.
