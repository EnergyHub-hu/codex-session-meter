# helper/AGENTS.md

## Scope

These instructions apply to `helper/` and all files below it.

## Component

`helper/` contains the Python package and CLI for `codex-session-meter`.

It is responsible for:

- settings validation and persistence;
- Codex CLI auth status checks;
- calling `codex app-server --stdio`;
- JSON-RPC request/response handling;
- converting Codex rate-limit data into normalized widget payloads;
- cache and log handling;
- CLI commands used by the GNOME extension.

## Python constraints

- Support Python `>=3.10`.
- Keep dependencies minimal. Do not add new runtime dependencies unless the task clearly requires them.
- Preserve `tomli` compatibility for Python versions below 3.11.
- Keep package metadata in `helper/pyproject.toml` consistent.
- Do not edit generated `_version.py`; it is managed by `setuptools-scm` and ignored by Git.
- Prefer `pathlib`, typed helper functions, explicit exceptions, and small pure functions where practical.

## Data-source and auth rules

- The helper must use Codex CLI app-server only:
  - command: `codex app-server --stdio`;
  - method: `account/rateLimits/read`;
  - source label: `Codex CLI API` where applicable.
- Do not add direct OpenAI HTTP calls, browser scraping, cookies, HAR parsing, Playwright, Chromium, or API-key authentication.
- `login` must delegate to `codex login`.
- `logout` may delegate to `codex logout`, but must not delete the Codex CLI auth file itself.
- Auth summary may report whether an access token exists, but must never expose token values.
- If Codex CLI API fails and no token is present, return `auth_required`.
- If Codex CLI API fails while auth appears present, return a safe data-source/parse-style error and preserve any last successful cached value.

## File and permission rules

- Config directory: `~/.config/codex-session-meter`.
- Cache directory: `~/.cache/codex-session-meter`.
- Data directory: `~/.local/share/codex-session-meter`.
- Auth file: `$CODEX_HOME/auth.json` or `~/.codex/auth.json`.
- Settings file must be TOML and restricted to supported values.
- Config/cache/data directories should be `0700`.
- Persisted settings and state should be `0600`.
- Logs must avoid raw responses, tokens, cookies, authorization headers, and secret-bearing payloads.

## Payload and parsing rules

- Keep analytics payload parsing bounded by `MAX_ANALYTICS_PAYLOAD_CHARS`.
- Prefer structured JSON parsing before HTML fallback in parser utilities.
- Do not include raw invalid payload content in exceptions or logs.
- Treat `rateLimits.primary.usedPercent` and `rateLimits.primary.resetsAt` as required for weekly payload creation.
- Clamp displayed percentages safely where existing formatter behavior requires it.
- Preserve local timezone formatting for reset dates and remaining time.

## CLI behavior

Preserve the existing CLI command set unless the user explicitly changes it:

```text
status
refresh
settings
configure
login
logout
auth-status
open-logs
```

For JSON output, print normalized JSON with `ensure_ascii=False`.

For non-JSON output, keep concise display-oriented messages.

## Testing

For any helper change, add or update focused tests under `helper/tests/`.

Run, from `helper/`:

```bash
python -m pytest
TZ=UTC python -m pytest
TZ=Europe/Budapest python -m pytest
```

Use monkeypatching for filesystem, subprocess, time, and auth behavior. Do not require real Codex CLI auth or real network access in tests.

If a test would touch real token state, skip or isolate it. Existing auth tests are intentionally disabled because they can interfere with local token state.

## Success criteria for helper work

- CLI behavior remains backward compatible unless explicitly changed.
- No secrets or raw sensitive payloads are printed or logged.
- Settings validation rejects unsupported values.
- Cache and last-success behavior are preserved.
- Codex app-server subprocesses are cleaned up on success, error, and timeout.
- Relevant helper tests pass in UTC and Europe/Budapest.
