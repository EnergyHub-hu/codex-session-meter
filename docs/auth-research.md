# Authentication Research

## Findings

- Official Codex docs say Codex supports `Sign in with ChatGPT` and API-key login.
- Codex cloud requires ChatGPT sign-in.
- Existing Codex tools own their own credential caches.
- Reusing another application's credential cache would couple this widget to private implementation details.
- Any browser profile, cookie store, session state, token cache, or HAR file is sensitive and must be treated like a password.

## Implementation Decision

The helper does not ask for API keys. It uses Codex CLI authentication through `codex login` and reads auth status from the Codex CLI auth file.

Primary local flow:

```bash
codex-session-widget login
```

Logout flow:

```bash
codex-session-widget logout
```

`login` delegates to `codex login`. Codex CLI stores auth in `$CODEX_HOME/auth.json`, defaulting to `~/.codex/auth.json`.

Treat the browser profile and session state as secrets and do not log them.

## Security Notes

- Do not commit Codex auth files, cookies, or HAR files.
- Do not paste tokens, cookies, auth headers, or full responses into issues or chats.
- Do not add API-key support for this widget; the target product data is ChatGPT/Codex account usage, not OpenAI Platform usage.
