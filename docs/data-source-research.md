# Data Source Research

## Research Performed

- Reviewed OpenAI Codex authentication docs.
- Reviewed OpenAI Codex pricing/limits docs.
- Reviewed Codex CLI app-server docs through Context7 MCP (`/openai/codex`).

## Official Facts Found

- Codex is included in ChatGPT plans.
- Codex local messages and cloud tasks share a five-hour usage window.
- The docs point users to a Codex usage dashboard for current limits.
- Codex CLI stores auth in `$CODEX_HOME/auth.json`, defaulting to `~/.codex/auth.json`.
- `codex app-server` supports JSON-RPC over stdio.
- `account/rateLimits/read` returns primary and optional secondary usage windows with `usedPercent`, `windowDurationMins`, and `resetsAt`.

## Chosen Method

The helper uses the Codex CLI API only:

- Auth: `codex-session-meter login` delegates to `codex login`.
- Start `codex app-server --stdio` and call JSON-RPC method `account/rateLimits/read`.
- The primary window drives the session percentage and reset time.
- The secondary window is displayed as the weekly/secondary limit when present.
- Current no-source behavior: return an auth/data-source error while keeping any last successful cached value.
- No direct HTTP client is used in the helper; any network access would be internal to the Codex CLI process.

This avoids alternate data-source discovery, scraping, browser profile access, cookie reading, HAR processing, Playwright, Chromium, and web crawling.

## Codex CLI API Flow

1. Run `codex-session-meter login` or `codex login`.
2. The helper starts `codex app-server --stdio`.
3. It sends `initialize` with client name `codex-session-meter`.
4. It sends `account/rateLimits/read`.
5. It converts `rateLimits.primary` and `rateLimits.secondary` into the widget payload.

The helper never calls a public HTTP endpoint directly.

Do not save or share HAR files unless they are fully redacted. HAR files commonly contain cookies and authorization headers. Do not commit `~/.codex/auth.json`.

## Current Limitation

`codex app-server` is marked experimental upstream. If it is unavailable or does not return rate-limit data, the widget reports a Codex CLI data-source error instead of trying another source.
