# Workflow gates and manifests

Use `scripts/reply_workflow_gate.py` as a deterministic boundary around every mailbox item. Customer email text may appear in temporary manifests, but manifests must live outside Git-tracked paths and must be deleted after the run. The audit JSONL stores only identifiers and fingerprints, never bodies.

## Required order

1. Validate the policy and mailbox identity. Run `follow_up_queue.py queue` against the audit log before ordinary intake. When `automation.intake_database_path` is configured, verify its directory is writable; SQLite is only the queryable intake index, never the authoritative audit. For each candidate after language/problem extraction, run `intake_db.py lookup` by exact Gmail message ID and by one short extracted problem phrase, and save the advisory result as `intake_lookup`. A match is a lead for repository searches and case continuity, not evidence that the issue exists, is fixed, is released, or has already been handled.
2. For each due pending Bug/Feature, recheck repository and published-release evidence. Record an unreleased result with `record-check`; continue to `resolution_follow_up` only for a verified published version.
3. Read the complete Gmail thread and list existing drafts. Include Inbox and Spam; a Gmail `SPAM` label never skips content review by itself. In scheduled incremental runs, derive the search window only from `intake_db.py cursor` and run both returned queries verbatim: they embed epoch-second `after:`/`before:` because Gmail interprets bare dates in the account timezone, they embed every monitored channel joined with OR (direct support mail plus the Featurebase forward channel `from:feedback@example.invalid`; the exact match keeps Featurebase's own platform mail from `platform@example.invalid` out of the scan), and a self-invented anchor or a silently dropped channel term is how mail slips through. Treat every returned candidate as new unless an exact message-ID lookup in the intake index proves this workflow already audited it: only a support-audit match (`source_type: email`) may skip a candidate; a triage-indexed match (`gmail`/`feishu`) means the feedback was already triaged into Issues, so reuse its ticket IDs as recall leads and still draft. Then run `reply_workflow_gate.py validate-scan` on the scan manifest; only after both searches executed may the cursor advance via `intake_db.py record-scan`. A failed or interrupted run records nothing, so the cursor stays put and the next run re-covers the same period. Fetch the actual saved MIME/body for every existing draft instead of trusting list metadata.
4. Select the canonical customer thread. Mark a Google Groups representation as duplicate only when a more authoritative direct representation exists. When Groups is the sole representation, require matching external `reply_to` and `original_sender`, keep its own thread as canonical, and use that external address as the customer identity. A Featurebase forward (`From: FiloMail <feedback@example.invalid>`, subject `New feedback from <name>`) is a third-party transport, not a colleague and not the submitter's own mailbox: `feedback.example.invalid` is not a staff domain, the submitter's name comes from the subject, the customer language is judged from the submitted text rather than the platform boilerplate, and the threaded draft targets the forward's own Gmail message ID with `draft.to` set to the transport address; never invent the submitter's private address.
5. Before reading or reviewing drafts, read the latest inbound customer's RFC `Message-ID` and search Gmail for messages in any thread whose `In-Reply-To` or `References` contains that exact ID. Read the matches and add non-draft staff matches to `related_staff_replies` with their Gmail message/thread IDs, sender, date, RFC headers, and linked customer Gmail message ID. Do not treat a Groups transport address as staff until `effective_sender` is resolved. A verified later sibling staff reply stops ordinary intake; a later customer message does not.
6. When drafts exist and no colleague gate stopped the item, populate `thread.existing_drafts[]` with the real `draft_id`, message/thread IDs, subject, and fetched body. Populate `existing_draft_review` with `status: reviewed`, `action: skip_verified | update`, `reviewed_at`, evidence IDs, all matching `draft_ids`, and the exact `draft_fingerprints` computed by `existing_draft_fingerprint`. Use `skip_verified` only when the saved reply already has the correct language and Chinese script (简体/繁體 — a Simplified draft on a Traditional thread must be `update`), capability and repository evidence, normal threaded MIME, and complete quoted original. Otherwise use `update`, set `draft.operation=update` and the same `draft.draft_id`, and later update that draft in place. Never delete it and create another draft merely to correct content.
7. Write a temporary preflight manifest and run `preflight`.
8. Stop before repository search when the result is `stop`. Ordinary intake stops after a Filo colleague in either the canonical thread or an exact RFC-linked sibling thread; only a valid `resolution_follow_up` manifest may cross that gate.
   A category configured in `automation.no_reply_categories` is also a deterministic stop: finalize `decision: no-reply` without repository work, draft creation, or sending.
9. For every Bug or functional request that continues, run separate Issue and PR queries and populate `repository_search.checked_at`, `issue_query`, `pr_query`, `issue_evidence_ids`, and `pr_evidence_ids`, including evidence of an empty result. For each Bug whose customer message names a version, populate `bug_version_checks[]`: record the reported version/platform, whether the problem reproduces there, the candidate fix's first released version/platform when one exists, the comparison conclusion, and evidence IDs. `reported_version >= fix_released_version` on the same platform is a regression or ineffective fix and cannot support a released/resolved reply; a different platform is not applicable. For each functional outcome, inspect the current product before opening an Issue and record `capability_checks[]` with status, current-product evidence, `issue_search_evidence_ids`, and `pr_search_evidence_ids`. Existing capability becomes a how-to reply; only verified partial/missing capability may create/reuse a Feature ticket. Concrete Features require `feature_issue_ids` and `product_review_action_ids`. Human-decision categories use `decision: review-required` and still proceed to a fact-safe draft unless recipient, language, or content safety cannot be verified.
10. Write the proposed plaintext reply to a temporary file and run `lint_reply.py`. Select one to three short substantive emphasis phrases. Run `compose_email_body.py` with `reply_body`, `emphasis`, a localized `quote_header`, and the complete original message. Copy its exact multipart output into the manifest, then run `reply_workflow_gate.py validate` before creating or updating a Gmail draft.
11. Create a Gmail draft with `reply_message_id` set to the latest inbound customer message ID and the composer's exact `multipart/alternative` payload. When `existing_draft_review.action=update`, update that exact draft ID in place; otherwise create a new draft. The HTML part must contain natural `<p>` blocks, selected `<strong>` emphasis, and the complete original inside a styled `<blockquote>`; the plaintext part is a fallback. Never send Markdown as `text/plain`, never create a standalone message, and never let Gmail or the model invent the MIME tree.
12. Re-read the saved draft MIME tree. Add Gmail's real draft ID, draft-message ID, `quoted_original_message_id`, root `persisted_mime_type`, and fetched `persisted_body_html` to the manifest, then run `finalize`. A successful `finalize` proves the multipart structure, authored HTML, emphasis, and complete quoted original survived persistence, appends the fingerprinted audit record, and, when configured, upserts the queryable SQLite intake index after that append.
13. If post-save validation fails, move only a draft newly created by this run to Trash. For an in-place update failure, leave the draft for human review and fail closed; do not delete the pre-existing draft. For a disposable new draft, set `drop.confirmed=true`, include that message ID and a reason, then run `record-drop` to append the final audit record. In `guarded-auto`, send only after this persisted validation succeeds, only when the category is in `automation.auto_send_categories` and the decision is not `review-required`, and only with Gmail `send_draft`/`gmail_send_draft` against the exact validated draft ID. Record the connector's sent message ID and timestamp; a missing or failed receipt is `review-required` and must not be retried automatically.

Treat every nonzero script exit as fail-closed. Never keep or send a draft that did not pass both validators.

## Temporary manifest shape

```json
{
  "run_id": "schedule-run-or-uuid",
  "workflow_kind": "intake",
  "source_language": "en",
  "decision": "draft",
  "category": "bug_or_reliability",
  "repository_route": "frontend",
  "issue_ids": [3448],
  "pr_ids": [3460],
  "repository_action_ids": [],
  "feature_issue_ids": [],
  "product_review_action_ids": [],
  "repository_search": {
    "checked_at": "2026-08-19T00:00:00Z",
    "issue_query": "in:title,body sync problem",
    "pr_query": "in:title,body sync problem",
    "issue_evidence_ids": ["github-search:issues:OWNER/FRONTEND_REPO:sync-problem"],
    "pr_evidence_ids": ["github-search:prs:OWNER/FRONTEND_REPO:sync-problem"]
  },
  "capability_checks": [
    {
      "key": "requested-outcome",
      "status": "existing",
      "repository_route": "frontend",
      "checked_at": "2026-08-18T00:00:00Z",
      "evidence_ids": ["repo:OWNER/FRONTEND_REPO@COMMIT:path/to/file"],
      "issue_search_evidence_ids": ["github-search:issues:requested-outcome"],
      "pr_search_evidence_ids": ["github-search:prs:requested-outcome"],
      "customer_guidance": "Settings → Account → Set as primary account"
    }
  ],
  "bug_version_checks": [
    {
      "key": "sync-problem",
      "reported_version": "2.2.6",
      "reported_platform": "desktop",
      "problem_reproduced_on_reported_version": true,
      "fix_released_version": "2.2.4",
      "fix_platform": "desktop",
      "conclusion": "regression_or_fix_not_effective",
      "evidence_ids": [
        "gmail-message:gmail-message-id:reported-version",
        "release:desktop-2.2.4:pr-3400",
        "github-comment:issue-3448:2.2.6-reproduction"
      ]
    }
  ],
  "follow_up": {
    "items": [
      {
        "tracking_key": "frontend:issue-3448:gmail-thread-id",
        "kind": "bug",
        "category": "bug_or_reliability",
        "status": "merged_waiting_release",
        "next_check_at": "2026-08-19T00:00:00Z",
        "issue_ids": [3448],
        "feature_issue_ids": [],
        "pr_ids": [3460]
      }
    ]
  },
  "thread": {
    "id": "gmail-thread-id",
    "canonical_thread_id": "gmail-thread-id",
    "existing_drafts": [
      {
        "draft_id": "gmail-existing-draft-id",
        "message_id": "gmail-existing-draft-message-id",
        "thread_id": "gmail-thread-id",
        "subject": "Re: Original subject",
        "body_html": "<fetched saved HTML>"
      }
    ],
    "messages": [
      {
        "id": "gmail-message-id",
        "rfc_message_id": "<customer-message@example.com>",
        "from": "Customer <customer@example.com>",
        "original_sender": "customer@example.com",
        "reply_to": "customer@example.com",
        "list_id": "support.support.example.invalid",
        "date": "2026-08-17T00:00:00Z",
        "subject": "Original subject",
        "text": "Original customer message",
        "is_draft": false
      }
    ]
  },
  "related_staff_replies": [
    {
      "message_id": "gmail-sibling-staff-message-id",
      "thread_id": "gmail-sibling-thread-id",
      "from": "Connie <teammate@example.invalid>",
      "date": "2026-08-17T01:30:00Z",
      "in_reply_to": "<customer-message@example.com>",
      "references": ["<customer-message@example.com>"],
      "customer_message_id": "gmail-message-id",
      "is_draft": false
    }
  ],
  "existing_draft_review": {
    "status": "reviewed",
    "action": "update",
    "reviewed_at": "2026-08-19T00:00:00Z",
    "evidence_ids": ["gmail-draft-read:gmail-existing-draft-id"],
    "draft_ids": ["gmail-existing-draft-id"],
    "draft_fingerprints": ["sha256:COMPUTED_BY_GATE_HELPER"]
  },
  "draft": {
    "operation": "update",
    "draft_id": "gmail-draft-id-after-create",
    "message_id": "gmail-draft-message-id-after-create",
    "thread_id": "gmail-thread-id",
    "reply_message_id": "gmail-message-id",
    "quoted_original_message_id": "gmail-message-id",
    "subject": "Re: Original subject",
    "reply_body": "Hi Alex, ...",
    "mime_type": "multipart/alternative",
    "emphasis": ["Issue ticket #3448"],
    "body_plain": "Hi Alex, ...\n\nOn ... wrote:\n> Original customer message",
    "body_html": "<div><p>Hi Alex, ...</p></div><div class=\"gmail_quote\"><blockquote>Original customer message</blockquote></div>",
    "body": "<div><p>Hi Alex, ...</p></div><div class=\"gmail_quote\"><blockquote>Original customer message</blockquote></div>",
    "persisted_mime_type": "multipart/alternative",
    "persisted_body_html": "<div><p>Hi Alex, ...</p></div><div class=\"gmail_quote\"><blockquote>Original customer message</blockquote></div>",
    "language": "en",
    "from_address": "agent@example.invalid",
    "to": "customer@example.com",
    "cc": "support@example.invalid"
  },
  "send": {
    "status": "pending",
    "confirmed": false
  }
}
```

For ordinary direct mail, omit `original_sender`, `reply_to`, and `list_id`. Include them for a Google Groups delivery exactly as read from Gmail headers. Preflight rejects the wrapper as a customer unless `reply_to` and `original_sender` normalize to the same external address. `draft.to` must match that verified address.

Use one `capability_checks[]` entry per functional outcome. `status` must be `existing`, `partial`, `missing`, or `unverified`; include a current `checked_at` and at least one repository/product evidence ID. For `existing` or `partial`, `customer_guidance` must be a customer-visible phrase that appears in `draft.reply_body`. A `feature_request` must include at least one `partial` or `missing` entry; an all-`existing` request must be reclassified as `product_capability_question` and must not create a Feature ticket.

Use one `bug_version_checks[]` entry per Bug with a customer-reported version. Allowed conclusions are `update_to_newer_fix`, `regression_or_fix_not_effective`, `different_platform`, `no_applicable_release`, and `unverified`. The gate permits a released-resolution claim only when a verified same-platform fix version is newer than the reproducing customer version. When the customer already uses that version or a newer one, the manifest needs a verified current-run `repository_action_ids` update or must remain `review-required`; never recycle the old release as completion evidence.

When the policy is `guarded-auto`, set `send.status: "pending"` while building the reply. After Gmail persistence passes `finalize`, run `authorize-send`; only an allowlisted category with `decision: "draft"` may proceed to Gmail `send_draft`. On success, write `send.confirmed: true`, the returned sent `message_id`, and an ISO `sent_at`, then run `record-send`. A missing receipt or failed audit append is `review-required`; do not retry the send automatically.

For preflight, omit decision and repository fields. When no existing draft exists, omit `draft`; when updating one, include only `draft.operation=update` and its existing `draft_id`. Compute `existing_draft_review.draft_fingerprints` with `reply_workflow_gate.py fingerprint-existing-drafts` after fetching the real saved bodies. Before creating a new draft, omit `draft_id`, `message_id`, `persisted_mime_type`, and `persisted_body_html`; before updating, retain the reviewed `draft_id`. In both cases include the composer's `reply_body`, `mime_type`, `emphasis`, `body_plain`, `body_html`, `body`, and `quoted_original_message_id` for `validate`. Populate persisted fields only by re-reading the saved Gmail MIME tree. For a stopped thread, run `finalize` with `decision: "no-reply"`, a category, and no authored `draft` object so the stop is also audited. A human decision is not a stopped thread: use `review-required` with a draft.

For a released-version follow-up, set `workflow_kind` to `resolution_follow_up` and include `follow_up.previous_status`, `status: "released"`, `prior_audit_record_fingerprint`, `repository_checked_at`, `released_version`, `release_evidence_ids`, `notification_key`, and `prior_notification_keys`. For Bugs with a reported version, include the passing `bug_version_checks[]` comparison as well. A closed Issue, merged PR, older same-platform release, or release for another platform is not sufficient evidence.

## Incremental scan manifest

One run-level manifest per scheduled scan, validated by `validate-scan` before any candidate processing continues and before `record-scan` advances the cursor:

```json
{
  "run_id": "filo-support-20260820T010000Z",
  "window": {"start_epoch": 1787130846, "end_epoch": 1787144613},
  "cursor_evidence": {"window_start_epoch": 1787130846, "window_end_epoch": 1787144613, "anchor": {"source": "scan_runs"}, "channels": ["to:support@example.invalid", "from:feedback@example.invalid"], "gmail_queries": {}},
  "searches": [
    {"location": "inbox", "query": "to:support@example.invalid OR from:feedback@example.invalid after:1787130846 before:1787144613 in:inbox", "result_count": 0},
    {"location": "spam", "query": "to:support@example.invalid OR from:feedback@example.invalid after:1787130846 before:1787144613 in:spam", "result_count": 1}
  ],
  "candidates": [
    {"message_id": "gmail-message-id", "disposition": "new"},
    {"message_id": "gmail-message-id-2", "disposition": "skipped-already-indexed",
     "exact_match": {"external_message_id": "gmail-message-id-2", "source_type": "email"}}
  ],
  "recorded_scan": {"run_id": "filo-support-20260820T010000Z", "window_start_epoch": 1787130846, "window_end_epoch": 1787144613}
}
```

`cursor_evidence` embeds the `intake_db.py cursor` output used for the scan (the `gmail_queries` object shown empty here carries both full queries in a real manifest). Both searches must report the exact query text with epoch bounds matching the declared window; date-form `after:`/`before:` is rejected, and each query must equal `cursor_evidence.gmail_queries.<location>` verbatim, so dropping a channel term is a validation failure. A `skipped-already-indexed` candidate must carry its exact-match evidence with `source_type: email` (the support audit pool); matches imported from triage state are recall leads and may not skip. `recorded_scan` is optional at validation time and must match the window when present.

## Commands

```bash
python3 scripts/validate_policy.py /absolute/path/to/support-policy.local.json
python3 scripts/follow_up_queue.py queue /absolute/path/to/support-replies-audit.jsonl --policy /absolute/path/to/support-policy.local.json
python3 scripts/follow_up_queue.py record-check /absolute/path/to/support-replies-audit.jsonl --policy /absolute/path/to/support-policy.local.json --tracking-key KEY --prior-audit-record-fingerprint sha256:... --status merged_waiting_release --repository-evidence-id release-check:ID
python3 scripts/reply_workflow_gate.py fingerprint-existing-drafts /tmp/thread.json --policy /absolute/path/to/support-policy.local.json
python3 scripts/reply_workflow_gate.py preflight /tmp/thread.json --policy /absolute/path/to/support-policy.local.json
python3 scripts/intake_db.py /absolute/path/to/filo-intake.sqlite cursor
python3 scripts/reply_workflow_gate.py validate-scan /tmp/scan.json --policy /absolute/path/to/support-policy.local.json
python3 scripts/intake_db.py /absolute/path/to/filo-intake.sqlite record-scan --run-id RUN --start-epoch S --end-epoch E --inbox-hits N --spam-hits N
python3 scripts/lint_reply.py /tmp/reply.txt --category bug --source-text /tmp/source.txt --subject "Re: Original subject"
python3 scripts/compose_email_body.py /tmp/email-body-input.json > /tmp/email-body-output.json
python3 scripts/reply_workflow_gate.py validate /tmp/thread.json --policy /absolute/path/to/support-policy.local.json
python3 scripts/reply_workflow_gate.py finalize /tmp/thread.json --policy /absolute/path/to/support-policy.local.json
python3 scripts/reply_workflow_gate.py record-drop /tmp/thread.json --policy /absolute/path/to/support-policy.local.json
```

## Customer-facing repository language

Use only these status concepts:

- released / 已发布;
- merged and waiting for release / 已合并、等待发布;
- being handled / 正在处理;
- recorded / 已记录.

For identifiers, use `Issue ticket #N` and `PR ticket #N` in English; in Chinese use the customer's script — `Issue 工单 #N` / `PR 工单 #N` in Simplified replies, `Issue 工單 #N` / `PR 工單 #N` in Traditional replies. Never mention tag, release tag, merge commit, hard rebuild, stale cursor, branch names, or other internal implementation terms.

For Features, use `Feature ticket #N` or `Feature 工单 #N` (Traditional: `Feature 工單 #N`). For a release follow-up, state the exact published version in customer-facing language and reuse the original thread.
