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

The helper uses the Codex CLI API first:

- Auth: `codex-session-widget login` delegates to `codex login`.
- Preferred: start `codex app-server --stdio` and call JSON-RPC method `account/rateLimits/read`.
- The primary window drives the session percentage and reset time.
- The secondary window is displayed as the weekly/secondary limit when present.
- Development fallback: authenticated JSON endpoint configured as `json_endpoint` in `~/.config/codex-session-widget/config.toml`.
- Development fallback: captured `sample_file` containing JSON or HTML from the analytics page, stored under `~/.config/codex-session-widget/samples/`.
- Current no-source behavior: return an auth/data-source error while keeping any last successful cached value.

This avoids scraping, browser profile access, cookie reading, HAR processing, Playwright, Chromium, and web crawling. The parser fallback still handles likely JSON reset fields such as `reset_at`, `resetAt`, `resetsAt`, `resetTime`, `nextReset`, and timestamp variants.

## Codex CLI API Flow

1. Run `codex-session-widget login` or `codex login`.
2. The helper starts `codex app-server --stdio`.
3. It sends `initialize` with client name `codex-session-widget`.
4. It sends `account/rateLimits/read`.
5. It converts `rateLimits.primary` and `rateLimits.secondary` into the widget payload.

Do not save or share HAR files unless they are fully redacted. HAR files commonly contain cookies and authorization headers. Do not commit `~/.codex/auth.json`.

## Current Limitation

`codex app-server` is marked experimental upstream, so the helper keeps the older `json_endpoint` and `sample_file` paths as development fallbacks.
