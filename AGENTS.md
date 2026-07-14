# AGENTS.md

## Scope

These instructions apply to the whole repository. More specific `AGENTS.md` files in subdirectories override or extend these rules for their subtree.

## Project

This repository is **Codex Weekly Meter**: an Ubuntu GNOME top-panel widget that shows remaining Codex weekly quota and planned consumption pace.

The repository has two main parts:

- `extension/`: GNOME Shell extension written in GJS.
- `helper/`: Python CLI package named `codex-session-meter`.

The helper owns authentication discovery, Codex usage data retrieval, parsing, percentage calculation, caching, and safe logs. The extension owns GNOME UI, menu controls, refresh scheduling, and panel display.

## Communication

Communicate with the user in Hungarian.

Keep implementation-facing artifacts in English unless they are existing or required user-facing Hungarian UI strings. This includes code, comments, configuration, test names, commit messages, technical identifiers, and developer documentation.

## Core product rules

- The only supported data source is the Codex CLI app-server API:
  - start `codex app-server --stdio`;
  - send JSON-RPC `initialize`;
  - call `account/rateLimits/read`;
  - treat `rateLimits.primary` as the weekly quota window.
- Authentication is delegated to Codex CLI:
  - `codex-session-meter login` delegates to `codex login`;
  - auth state comes from `$CODEX_HOME/auth.json` or `~/.codex/auth.json`.
- Do not add direct HTTP clients, scraping, browser profile access, cookie reading, HAR processing, Playwright, Chromium automation, sample-file fallback, alternate analytics endpoints, or API-key support unless the user explicitly requests a security-reviewed design change.
- Do not reuse another application's private credential cache beyond the documented Codex CLI auth file checks.
- The helper must not print token values or raw secret-bearing payloads.
- Preserve last-successful cached status behavior when refresh fails.
- Preserve Hungarian user-visible status strings unless the task explicitly changes UI language.

## Repository rules

- Treat packed Repomix exports as read-only reference material. Edit the original repository files only.
- Make the smallest change that satisfies the user request.
- Touch only files directly required for the task.
- Avoid broad refactors, speculative features, unrelated formatting, and adjacent-code churn.
- Match existing style and structure.
- Do not invent file paths, APIs, settings, enum values, service names, business rules, or data-source behavior.
- Remove only imports, variables, functions, or code made unused by your own changes. If unrelated dead code is noticed, mention it instead of deleting it.
- Every changed line should trace directly to the user request.

## Sensitive file handling

Do not request, inspect, or print sensitive files unnecessarily.

Sensitive material includes, but is not limited to:

- `.codex/`, `auth.json`, `$CODEX_HOME/auth.json`, `~/.codex/auth.json`;
- `.env`, `.env.*`;
- `*.pem`, `*.key`, SSH keys;
- cookies, HAR files, browser profiles, Playwright auth state, Chromium data;
- SQLite databases that may contain session or browser state;
- `state.json`, `widget.log`, `config.toml` when they may contain local user state;
- tokens, auth headers, cookies, private keys, production connection strings, real personal data.

If access to a sensitive file seems necessary, first explain in Hungarian:

1. which file is needed;
2. what specific information is needed;
3. why the task cannot be completed safely without it.

Ask before accessing it. Never print secrets, tokens, private keys, credentials, production connection strings, or real personal data.

## Work process

For multi-step or risky coding tasks:

1. Inspect the relevant flow.
2. Summarize findings briefly in Hungarian.
3. Ask whether to continue before the next major phase.
4. Implement the next phase only after confirmation.
5. Verify that phase.
6. Summarize changes briefly in Hungarian.
7. Continue this pattern until complete.

For small, low-risk tasks, proceed directly but still report assumptions and verification.

When unclear requirements materially affect implementation, stop and ask one concise Hungarian clarification question. If ambiguity is minor, state a safe assumption and continue.

## Engineering guidelines

- Prefer simple, explicit logic over abstraction.
- Keep error messages safe: no raw payloads, no auth headers, no token fragments.
- Preserve file permissions for config/cache/state files where applicable.
- Preserve XDG path behavior.
- Keep timezone-sensitive behavior explicit and tested when relevant.
- Use deterministic parsing and bounded payload sizes.
- Keep GNOME refresh loops and subprocess lifecycle safe: no overlapping refreshes, clear timers, terminate helper processes during shutdown.
- Keep UI state resilient when helper output is missing, invalid, or timed out.
- Do not change release/version fields unless the user asks for release preparation.

## Verification

Use the most relevant checks for the changed area.

For Python helper changes:

```bash
cd helper
python -m pytest
TZ=UTC python -m pytest
TZ=Europe/Budapest python -m pytest
```

For extension logic changes, run the existing JavaScript tests using the repository's established command. If no command is documented, try:

```bash
node --test extension/weekly-pace.test.js
```

If the local Node/GJS environment cannot run the tests, report the exact command and error without inventing a pass.

Before publishing or release-like changes, perform a secret-oriented review for:

```text
access_token
refresh_token
Authorization
Bearer
cookie
session
api_key
secret
password
```

Also review `git status --short` and `git diff` to confirm no sensitive or unrelated files are included.

## Success criteria

A task is complete only when:

- the requested behavior is implemented;
- existing related behavior is preserved;
- security and data-source constraints are respected;
- relevant tests/checks are added or updated where appropriate;
- relevant checks pass, or any inability to run them is clearly reported;
- no unrelated files, formatting, or behavior are changed;
- secrets and sensitive local state are not exposed.
