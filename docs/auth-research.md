# Authentication Research

## Findings

- Official Codex docs say Codex supports `Sign in with ChatGPT` and API-key login.
- Codex cloud requires ChatGPT sign-in.
- Existing Codex tools own their own credential caches.
- Reusing another application's credential cache would couple this widget to private implementation details.
- Browser profiles, cookie stores, session state files, token caches, and HAR files are sensitive and must not be used as widget data sources.

## Implementation Decision

The helper does not ask for API keys. It uses Codex CLI authentication through `codex login` and reads auth status from the Codex CLI auth file.

Primary local flow:

```bash
codex-session-meter login
```

Logout flow:

```bash
codex-session-meter logout
```

`login` delegates to `codex login`. Codex CLI stores auth in `$CODEX_HOME/auth.json`, defaulting to `~/.codex/auth.json`. The helper checks only file presence and whether an access token field exists; it does not print token values.

The helper does not use browser profiles, cookies, HAR files, Playwright state, or Chromium data as auth inputs.

Do not add browser profile scraping, cookie reading, HAR processing, Playwright, Chromium, or API-key support.

## Security Notes

- Do not commit Codex auth files, cookies, or HAR files.
- Do not paste tokens, cookies, auth headers, or full responses into issues or chats.
- Do not add API-key support for this widget; the target product data is ChatGPT/Codex account usage, not OpenAI Platform usage.
