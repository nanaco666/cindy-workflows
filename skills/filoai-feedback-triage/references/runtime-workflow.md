# One-round runtime workflow

## Contents

1. Open and validate
2. Bound the round
3. Read Gmail
4. Read Feishu
5. Triage candidates
6. Write safely
7. Save state
8. Report and notify
9. Fail closed

## 1. Open and validate

1. Set the session title to `FiloAI · Gmail+飞书反馈查重与 Issue 分诊`.
2. Read `.cindy/filo-support-automation/feedback-triage.local.json`.
3. Run `scripts/validate-config.mjs` or enforce the same validation.
4. Select `state.shadowFile` for SHADOW or `state.liveFile` for LIVE.
5. Read and validate state version, mode, Gmail watermark, Feishu chat ID/position/message/time, array/object fields, real trailing newline, configured retention bounds, and absence of a state lock or temporary-file residue.
6. Confirm the configured Gmail and Feishu identities match the connected sources.
7. Resolve GitHub remote default branches live.

If config, state, identity, source connection, or watermarks are invalid, skip all writes and go to `Fail closed`.

## 2. Bound the round

Honor all configured limits:

- maximum wall time;
- maximum external reads;
- maximum deeply processed candidates;
- maximum GitHub writes.

Track counters in the run summary. When a limit is reached, stop taking new candidates, finish any already-started state-safe action, save successful source watermarks, and report the remaining count.

## 3. Read Gmail

1. Compute the scan start as `gmailWatermarkTime - overlapMinutes`.
2. Query the complete bounded window with Gmail scope `in:anywhere -in:trash`, then read metadata and content across the full window, paging as needed. Do not use Inbox, Unread, category, or Spam labels as the coverage boundary.
3. Exclude GitHub/CI/system/marketing mail from candidates only after reading enough content to classify it. A Filo support or Google Group message may be incorrectly labeled `SPAM`; the `SPAM` label alone is never a reason to skip an engineering candidate or advance past it unseen.
4. Preserve Featurebase/FiloMail feedback emails from `feedback@example.invalid`, including subjects such as `New feedback from ...`, even when Gmail marks them Marketing, Promotions, or Spam. Read the body first and classify the business content before exclusion.
5. Deduplicate by Message-ID and normalized content SHA-256.
6. Deep-process up to the configured candidate limit.
7. Treat the Gmail watermark as a fully covered time boundary, not the timestamp of the newest message. After the complete bounded window has been paged and read successfully, advance it to the round's scan upper bound even when no message exists exactly at that time. If coverage is incomplete, freeze it at or before the first failed or unpaged gap.
8. A processed source ID is not proof of completed triage. Every examined engineering-feedback item must also have a content fingerprint and a persisted decision fingerprint (`create`, `supplement`, `no-register`, `await-release`, or `human-review`) before it may be treated as handled. Record every examined engineering candidate in `lastRun.engineeringCandidateFingerprints`; the state transaction rejects the save if any listed fingerprint has no corresponding decision record.

Never alter read/unread, labels, archive, star, delete, or any other mailbox state.

## 4. Read Feishu

1. Read top-level messages strictly after `feishuWatermarkPosition`.
2. For a likely feedback item, read the minimum necessary root/thread neighbors.
3. Deduplicate with message ID, root/thread ID, and normalized content fingerprint.
4. Record the maximum fully covered position, message ID, and time.
5. Do not advance beyond a failed page or unresolved ordering gap.

Never send, reply, react, mention, or DM.

## 5. Triage candidates

For each new candidate, apply `references/domain-policy.md` in order:

1. determine whether it is engineering feedback;
2. classify Bug, New requirement, Product decision, release question, or non-engineering;
3. preserve a short, redacted statement of what the reporter actually said; never silently expand an inference into a reported fact;
4. run the shared intake lookup after extracting the source message/thread ID and a short problem phrase:

   ```bash
   python3 {{FILO_SUPPORT_SKILL_DIR}}/scripts/intake_db.py \\
     <config.insights.databasePath> lookup "<message-or-thread-id>" --source-type <sourceType>
   python3 {{FILO_SUPPORT_SKILL_DIR}}/scripts/intake_db.py \\
     <config.insights.databasePath> lookup "<problem-phrase>" --source-type <sourceType>
   ```

   Record exact/similar feedback IDs and linked Issue/PR IDs as advisory evidence. SQLite is not authoritative: re-verify every carrier and status against live GitHub and saved authoritative state, and never skip a required search or decision because SQLite returned a match;
5. run the self-diagnosis pass from `domain-policy.md`, even when the source is only one sentence: recover platform/version/workflow clues from the same thread, inspect current product capability and settings, trace the most likely code path, and test plausible causes against repository evidence;
6. search canonical and related Issues;
7. search open/recently merged PRs and checks;
8. read relevant remote-default-branch code and recent changes;
9. inspect release/verification evidence;
10. map the responsible layers;
11. decide `create`, `supplement`, `no-register`, `await-release`, or `human-review`.

Do not use source brevity as a shortcut to `human-review` or a thin Issue. A one-line report may still support a useful carrier after repository inspection. Ask for reporter-only details only when they would distinguish materially different causes, ownership, or acceptance criteria and cannot be recovered from the thread, product behavior, repository, or release evidence. Record whether those details block engineering work or can arrive later.

Record evidence, target, and a stable decision fingerprint before any write. Every persisted engineering decision must also contain the fields needed by the local intake index: `sourceMessageId` or `sourceMessageIds`, `sourceType` (`gmail`, `feishu`, `discord`, or `other`), a short redacted `reason`, `observedAt`, and verified `senderName`/`senderEmail` when the source metadata exposes them. Set `engagementPoints: 1` only for a genuine external user message; use `0` for bot/system mail, Filo staff output, true duplicates, and automated status messages. Never guess a missing identity.

## 6. Write safely

### SHADOW

Perform no GitHub write. Store a proposed action containing:

- redacted source summary and time;
- classification and client scope;
- deduplication searches and carriers found;
- remote code/release evidence;
- proposed title, labels, and body/comment;
- exact reason for the decision fingerprint.

### LIVE

Before each write, reread the target's live state. Re-run the decisive GitHub search if meaningful time has passed.

- `create`: create one canonical Issue using the required template and allowed labels.
- `supplement`: add one Chinese comment with only the new fact, time node, and impact; organize labels only if this Issue was updated now.
- all other decisions: perform no write.

For `create` and `supplement`, reject proposed text that merely restates the feedback plus a generic list of possible causes. The proposal must show what was checked, what each check ruled in or out, the strongest current hypothesis with calibrated confidence, and the smallest remaining reporter-only question, if any. Missing reporter details belong in the Issue body as `待用户补充` and do not automatically block creation.

After a successful write, record the resulting Issue URL/number and fingerprint. If the write response is ambiguous, reread GitHub before retrying. Never blindly retry.

If a duplicate or unexpected write is discovered, stop all further writes for the round.

## 7. Save state

Maintain source independence:

- update Gmail watermark only after complete successful Gmail coverage;
- update Feishu watermark only after complete successful Feishu coverage;
- append processed IDs/fingerprints only for items actually examined;
- append reported decision fingerprints and resulting Issue references;
- reconcile examined engineering candidates so none has only a processed source ID without a decision fingerprint;
- store proposed actions in SHADOW state;
- prune oldest IDs/fingerprints to configured bounds;
- set `lastSuccessfulScanAt`, `lastEffectiveAdditionAt`, and `lastRun` accurately.

State persistence is a compare-and-swap transaction. Immediately after reading the selected state, capture its exact byte hash with `scripts/save-state.mjs --current-sha256 <target-state.json>` and retain that hash for the round. Describe append-only source IDs/fingerprints, decision records, watermarks, and `lastRun` in a small run-update JSON; generate the complete candidate state with `scripts/prepare-next-state.mjs <current-state.json> <run-update.json> <next-state.json>`, then persist it only with `scripts/save-state.mjs <target-state.json> <next-state.json> <expected-current-sha256>`.

The helper is the sole permitted state writer. It acquires a single-writer lock, validates the current and next schemas, rejects mode/chat/initialization changes, rejects backward watermarks and removed decision fingerprints, verifies the expected current hash before staging and again before rename, serializes with a real trailing newline, fsyncs, atomically renames, and validates the saved file again. A hash mismatch, lock, temporary-file residue, invalid transition, or post-write mismatch fails closed and must never be bypassed with a direct file edit or ad-hoc shell/JavaScript writer. Do not construct state JSON or newline escapes inside nested shell command strings. Do not write secrets.

If GitHub write succeeds and state persistence fails, report the target Issue explicitly so the next run can deduplicate from live GitHub.

After `save-state.mjs` reports success, run:

```bash
node <skill-dir>/scripts/sync-intake-db.mjs <config.local.json> <saved-state.json>
```

The SQLite database configured by `config.insights.databasePath` is a query layer only. The CAS state JSON remains authoritative for watermarks, deduplication, and decisions. A database sync failure must be reported but must not trigger mailbox writes, GitHub writes, or a state rollback. Do not invent missing historical sender identities or message IDs while indexing; index only fields actually persisted in the saved state.

## 8. Report and notify

Produce a concise Chinese summary:

- mode and scan windows;
- Gmail/Feishu items scanned and candidate counts;
- create/supplement/no-register/await-release/human-review counts;
- targets and reasons for actionable decisions;
- old and new source watermarks;
- limits consumed and remaining work;
- failures or degraded paths;
- in SHADOW, `若为 LIVE 会执行` actions.

Call the current-run silence tool for an idle successful round. Call the current-run notify tool only for the cases allowed in `domain-policy.md`. Do not send Feishu, email, or Slack.

## 9. Fail closed

- A source failure freezes only that source's watermark.
- A GitHub read failure blocks all GitHub writes.
- An invalid state, wrong account/chat/repository, or missing initial watermark blocks the entire round.
- A preflight error blocks the round.
- A tool refusal or permission error must not be bypassed with another channel.
- Never reconstruct watermarks from guesses or silently full-scan history.
- Never modify the schedule or config from a scheduled run.

Persist only trustworthy partial state, describe the exact human action needed, request a desktop notification, and end the round.
