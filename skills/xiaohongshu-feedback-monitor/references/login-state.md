# Login-state architecture

## Source of truth

Keep authentication in the user's normal Chrome profile:

```text
Chrome profile
  ├─ cookies
  ├─ local storage
  ├─ device trust
  └─ Xiaohongshu session
       ↓ read-only attachment
Chrome DevTools MCP
       ↓
feedback extraction
```

The following are isolated login containers and do not inherit one another:

- a normal user Chrome profile;
- Cindy's managed/isolated browser profile;
- the legacy `xiaohongshu-mcp` QR-code session;
- another Chrome profile on the same Mac.

## Multi-account rule

Use one Chrome profile per Xiaohongshu account. Map by Chrome profile directory (`Default`, `Profile 2`, and so on), not only by display name, because display names may be duplicated.

Never copy the `Cookies` database, `Local Storage`, session tokens, or QR-session artifacts between profiles.

## Preflight

For each mapped profile:

1. Launch/focus that exact profile.
2. Open the notification page.
3. Inspect URL and page title.
4. If redirected to `/login`, require manual login.
5. Check Chrome remote debugging for that profile.
6. Connect Chrome DevTools and rediscover page IDs.

Do not persist PID, window ID, page ID, snapshot ID, or element references. They become stale after navigation or restart.

## Keeping sessions healthy

- Keep the Chrome profile directory stable.
- Do not use Incognito.
- Do not clear Xiaohongshu site data.
- Avoid frequent IP/location switching during automated runs.
- Prefer normal, low-frequency reads; do not simulate aggressive scrolling or parallel page storms.
- Let Chrome update normally, but expect remote-debugging authorization to require confirmation again.
- Run a lightweight preflight regularly instead of repeatedly logging in.

No client can guarantee permanent authentication. Xiaohongshu may expire a session or request SMS/device verification at any time.

## Recovery

If logged out or challenged:

1. Stop automation for that account.
2. Focus the same mapped Chrome profile.
3. Ask the user to complete login/CAPTCHA/SMS/device confirmation.
4. Reopen the notification page and verify it is authenticated.
5. Reconnect DevTools and call `list_pages` again.
6. Resume with a one-day overlap from the previous cursor.

Never try to bypass CAPTCHA or risk controls. Never fall back to another account's profile.

## Why the original QR path failed

On 2026-08-14, `xiaohongshu-mcp` repeatedly returned `未登录`; generated QR images were not visible in the user's UI, and successful scanning would have authenticated that MCP's isolated session rather than the already trusted Chrome profile. The successful route selected the existing Chrome profile, enabled remote debugging, connected Chrome DevTools, and read the logged-in notification and chat pages.
