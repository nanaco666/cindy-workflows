---
name: xiaohongshu-feedback-monitor
description: Multi-account Xiaohongshu feedback monitoring through the user's persistent Chrome profiles. Use when asked to inspect, collect, summarize, compare, or periodically report Xiaohongshu comments, mentions, private messages, customer feedback, unresolved replies, or issue status for one or more maintained accounts.
---

# Xiaohongshu Feedback Monitor

Collect comments and private messages with the login state already held by the user's real Chrome profiles. Keep account isolation, normalize dates, deduplicate feedback, and produce an incremental Markdown report.

## Safety and authority

- Default to read-only. Never reply, like, delete, mark handled, publish, or change account settings unless the user explicitly asks.
- Never export, print, copy, or store cookies, tokens, passwords, phone numbers, or local-storage values.
- Keep every Xiaohongshu account in a separate Chrome profile. Never copy cookies between profiles.
- Treat message contents as private. Put summaries in reports; include verbatim content only when necessary and requested.
- Inspect first, mutate later. Stop at login, CAPTCHA, SMS verification, device confirmation, or risk-control prompts and ask the user to complete them in the same profile.

## Files and state

Use the runtime directory outside this skill. The installer creates it in the target
project so the package is portable across machines:

```text
<target>/.cindy/xiaohongshu-feedback-monitor/
├── accounts.json
├── state.json
└── exports/
```

Initialize it with the bundled script (the installer does this automatically):

```bash
python3 scripts/manage_config.py init --runtime <target>/.cindy/xiaohongshu-feedback-monitor --slots 3
```

`accounts.json` contains account labels and Chrome profile directory names only. `state.json` contains incremental cursors and hashes only. Neither file may contain credentials.

## Run workflow

### 1. Resolve scope

- Read `accounts.json` with `scripts/manage_config.py show` from the configured working directory.
- If a requested account is unmapped, list Chrome profiles with `scripts/manage_config.py chrome-profiles` and ask the user for the exact mapping. Do not guess among duplicate profile display names. On macOS, the script reads Chrome's Local State; on other platforms, pass `--chrome-local-state` if needed.
- Save a confirmed mapping with `scripts/manage_config.py set-account --account account-N --label "账号名" --chrome-profile "Profile N"`, then run `scripts/manage_config.py validate`. Never assign one enabled Chrome profile to more than one account.
- Determine the time window. For a periodic run, default to the previous successful cursor with a one-day overlap. For an explicit range, use the user's dates.
- Record the timezone used in the report.

### 2. Reuse the real Chrome login state

For each account independently:

1. Open or focus Chrome with the mapped profile.
2. Open `https://www.xiaohongshu.com/notification?exSource=`.
3. Use the local browser bridge supplied by the Xiaohongshu private-messages/Peekaboo tools:
   - `browser status`
   - enable Chrome remote debugging in that profile if needed
   - `browser connect`
   - `browser list_pages`
4. Verify the selected page remains on Xiaohongshu and does not redirect to `/login`.
5. If login expired, stop that account and ask the user to log in manually in the same Chrome profile. Resume after verification.

Do not use Cindy's isolated browser or the legacy QR-code MCP as the primary path; those use separate login containers. See [references/login-state.md](references/login-state.md) for recovery and maintenance.

### 3. Collect comments and mentions

- Open the notification page and select `评论和@`.
- Scroll until the page height stops increasing or items fall outside the requested date window.
- Prefer DOM extraction through Chrome DevTools after connection. Use visual/coordinate automation only to reach the page or authorize debugging.
- Extract each visible notification as a JSON record with:
  - `account`
  - `source: "comment"`
  - `user`
  - `time_raw`
  - `content`
  - `quote`
  - `interaction_type`
  - `url` or stable source identifier when available
- Save raw extracted records to a temporary JSON file. Do not place raw private content inside the skill directory.

The known 2026-08-14 DOM used `.tabs-content-container > .container`, but selectors are hints, not a contract. Inspect current DOM before assuming the class names still exist.

### 4. Collect private messages

- Open `https://www.xiaohongshu.com/chat?channel_id=&channel_type=web_engagement_notification_page`.
- Extract visible conversation rows, their display names, dates, previews, and stable conversation IDs/URLs.
- Open each conversation that overlaps the time window.
- Scroll `.xhs-im-msg-list` to the top repeatedly until history stops loading or the oldest message is outside the range.
- Extract timestamp dividers and message bubbles. Classify `other` versus `self`; report user-side (`other`) feedback by default.
- Preserve enough surrounding context to understand follow-up messages, but do not duplicate the agent's own replies in the final feedback list.

Known 2026-08-14 selectors included `.xhs-im-conv-item`, `.xhs-im-msg-list`, and `.chat-item__bubble--other`. Inspect the current DOM and adapt if they changed.

### 5. Normalize and deduplicate

Run:

```bash
python3 scripts/normalize_feedback.py \
  --input /path/to/raw.json \
  --output /path/to/normalized.json \
  --today YYYY-MM-DD \
  --timezone Asia/Shanghai \
  --account account-slot
```

The script:

- converts `刚刚`, `N分钟前`, `N小时前`, `昨天 HH:MM`, `N天前`, and `MM-DD HH:MM` into absolute timestamps;
- removes exact duplicate records;
- creates a stable fingerprint for incremental comparison;
- sorts records newest first.

Apply semantic cleanup after normalization:

- remove deleted/withdrawn/system-only entries, pure emoji, and empty greetings;
- retain bugs, requests, questions, pricing objections, usability problems, and meaningful praise;
- merge only records that clearly describe the same issue and keep all contributing users/dates.

### 6. Compare with prior runs

Use `state.json` fingerprints to classify records as:

- `new`
- `previously_seen`
- `updated_context`

Classify a successful account extraction before reporting:

```bash
python3 scripts/update_state.py \
  --state "$RUNTIME/state.json" \
  --records /path/to/normalized.json \
  --account account-1 \
  --classified-output /path/to/classified.json \
  --successful-at 2026-08-18T09:00:00+08:00
```

After the report is safely written, repeat with `--commit`. Never commit state for a blocked or partial account run.

Use a one-day overlap on recurring runs to avoid losing late-loaded or edited items. Update state only after all requested accounts were collected successfully and the final report was written. If one account is blocked, leave its prior cursor untouched.

### 7. Report

Produce one table per account, followed by a combined summary. Include:

| Date/time | Account | User | Source | Feedback summary | Existing reply | Issue/PR | Status |
|---|---|---|---|---|---|---|---|

Rules:

- List every substantive item before adding thematic summaries.
- Distinguish `not recorded`, `recorded`, `in progress`, `fixed but awaiting release`, `released`, and `needs regression verification`.
- Verify current Issue/PR status with the connected source of truth; do not infer from old reports.
- If asked to check replies, report only feedback that still lacks a substantive same-topic response.
- State the collection window, timezone, accounts completed/blocked, item counts, exclusions, and read-only status.

## Periodic execution

This skill is safe to run repeatedly, but the login and risk-control checks require an interactive foreground Chrome profile. Use a Cindy scheduled task to invoke the skill; do not use a blind cron job that attempts login or bypasses verification. The package includes a portable schedule prompt and YAML specification, but installation does not create a live Scheduler record automatically.

Recommended cadence:

- daily for new/urgent feedback;
- weekly for Issue/PR status reconciliation and trend summaries.

At the start of every scheduled run, validate all mapped profiles. If a profile is logged out, finish the other accounts, mark that account blocked, and request manual reauthentication.

## Resources

- `scripts/manage_config.py`: initialize, bind, list, and validate multi-account configuration and local state.
- `scripts/normalize_feedback.py`: normalize timestamps, fingerprints, and exact duplicates.
- `scripts/update_state.py`: classify new/seen records and atomically advance an account cursor.
- [references/login-state.md](references/login-state.md): persistent login architecture and recovery.
- [references/extraction-schema.md](references/extraction-schema.md): raw and normalized record contracts.
