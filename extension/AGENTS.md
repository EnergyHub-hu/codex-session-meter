# extension/AGENTS.md

## Scope

These instructions apply to `extension/` and all files below it.

## Component

`extension/` contains the GNOME Shell extension written in GJS.

It is responsible for:

- top-panel indicator UI;
- daily pace dot and weekly quota label;
- refresh scheduling;
- invoking the `codex-session-meter` helper;
- menu actions for refresh, login, logs, poll interval, display format, weekly workdays, and panel icon.

## GNOME/GJS constraints

- Target GNOME Shell versions are `45`, `46`, `47`, and `48`.
- Use existing GJS import style:
  - `gi://...` imports for GNOME libraries;
  - `resource:///org/gnome/shell/...` imports for Shell modules.
- Keep extension logic compatible with GNOME Shell extension lifecycle:
  - create UI in `enable`;
  - remove timers, terminate helper processes, destroy UI in `disable`;
  - avoid refresh loops that survive disable.
- Do not introduce browser, Playwright, Chromium, or direct network dependencies into the extension.
- The extension should call the local helper at `~/.local/bin/codex-session-meter`.

## UI and behavior rules

- Preserve the panel display concept:
  - daily remaining percent;
  - weekly remaining percent;
  - local weekly reset date.
- Preserve the daily limit dot class mapping produced by `dailyLimitIndicatorLevel`.
- Preserve compact and verbose display formats unless the task explicitly changes them.
- Preserve supported poll intervals: `1`, `5`, `10`, `15` minutes.
- Preserve supported weekly workdays: `1` through `7`.
- Preserve supported panel icon options unless the task explicitly changes icon behavior.
- Keep user-visible Hungarian strings where the existing UI is Hungarian.
- Keep implementation-facing identifiers and comments in English.

## Helper interaction rules

- Run helper commands through `Gio.Subprocess`.
- Parse only JSON returned by helper `refresh --json` and `configure ... --json`.
- Handle helper missing, timeout, empty response, and invalid JSON safely.
- Do not display raw stderr or raw helper payloads in the panel.
- Avoid overlapping refresh calls with the `_running` guard.
- Maintain helper timeout behavior and process cleanup.
- When settings are returned by the helper, validate them against extension-side allowed values before applying them.

## JavaScript logic rules

- Keep pure calculation logic in `weekly-pace.js` when possible.
- Keep UI lifecycle and GNOME integration in `extension.js`.
- Avoid mixing test-only logic into GNOME UI code.
- Avoid broad style rewrites; follow the existing compact GJS style.
- Use explicit fallback values for missing payload fields.

## Testing

For changes to weekly pace, display formatting, or indicator level mapping, update `extension/weekly-pace.test.js`.

Run the repository's established JavaScript test command. If no command is documented, try from the repository root:

```bash
node --test extension/weekly-pace.test.js
```

If Node cannot execute the ESM-style test in the local environment, report the exact command and error. Do not change module packaging solely to make tests run unless the user requested test infrastructure work.

For GNOME UI lifecycle changes, provide manual verification steps, for example:

```bash
./install.sh
gnome-extensions enable codex-session-meter@local
```

Then verify enabling, disabling, refresh, login action, logs action, and no surviving refresh loop after disable.

## Success criteria for extension work

- Panel label and dot remain stable with valid helper payloads.
- Missing/invalid helper responses degrade gracefully.
- Settings menu reflects current selected values.
- Timers and helper subprocesses are cleaned up on disable.
- Relevant JavaScript tests or manual checks are run and reported.
- No sensitive data is displayed in the panel or menu.
