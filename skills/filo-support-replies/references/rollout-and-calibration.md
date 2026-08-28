# Rollout and calibration

## Goal

Use automation to absorb volume without turning every sender into a ticket number. Preserve extra attention for messages that contain real product insight, new evidence, or an unresolved operational issue.

## Set up policy first

1. Copy `assets/support-policy.example.json` to a project-local `support-policy.local.json`.
2. Replace the approver and source-of-truth placeholders.
3. Reverify every dated plan, quota, entitlement, and exception.
4. Keep `reply_mode` set to `draft` during calibration. After the owner explicitly approves a narrow allowlist and the validation criteria below are met, a project-local policy may switch to `guarded-auto`; the Skill default and example policy remain `draft`.
5. Run `scripts/validate_policy.py` and resolve every error or staleness warning.
6. Connect the mailbox separately. Never place credentials in the policy file or Skill.

## Calibrate on historical threads

Use 20–30 recent closed threads with personal data redacted. Do not send anything.

Ensure the sample includes:

- sincere suggestions;
- free-AI or pricing objections;
- a user who cannot afford Plus;
- a long-time user reacting to the change;
- bugs with incomplete and then complete evidence;
- repeated arguments with no new facts;
- billing, refund, account, privacy, or security mail;
- Gmail `SPAM`-labeled messages that contain real support requests, plus content-confirmed spam or automated mail;
- Chinese and English threads.

For each output, have the maintainer mark:

- `specific-enough`: the reply proves the thread was read;
- `too-cold`: correct but dismissive;
- `too-soft`: empathy obscures the answer or boundary;
- `missed-idea`: failed to articulate the useful center of a suggestion;
- `false-promise`: implied action, timeline, compensation, or roadmap without evidence;
- `wrong-stop`: closed a progressing conversation;
- `wrong-continue`: prolonged a no-new-information loop;
- `wrong-escalation`: sent or stopped a message that required an owner.
- `wrong-repo-status`: misstated Issue, PR, merge, release, or shipped-version state.
- `missing-tracker`: sent a Bug reply without the required Issue/PR lookup and number.
- `missed-defect`: answered only one of several failures in the same message.
- `replied-after-staff`: created a draft when the latest non-draft sender was `@support.example.invalid`.
- `wrong-language`: reply language did not match the latest inbound customer message.
- `wrong-thread`: created a standalone draft or targeted a duplicate representation instead of the canonical Gmail thread/message.
- `dropped-groups-only-customer`: treated the sole verified Google Groups delivery as a duplicate or colleague reply even though Reply-To and original sender matched the customer.
- `missing-review-draft`: omitted a safe `review-required` draft merely because a human must approve the substantive decision.
- `missing-visible-original`: kept a draft whose saved body did not visibly quote the complete original customer message, even if its thread ID or RFC headers were correct.
- `internal-jargon`: exposed tag, release tag, merge commit, hard rebuild, stale cursor, or similar implementation language.
- `missing-audit-identity`: audit record omitted a required Gmail/repository ID or deterministic fingerprint.
- `missing-feature-ticket`: acknowledged a concrete Feature without a verified Feature ticket and product-review action ID.
- `premature-release-follow-up`: treated a closed Issue or merged PR as released without a verified published version.
- `duplicate-release-follow-up`: created more than one draft for the same thread/ticket/version notification key.

Revise policy or examples when the same error appears twice. Do not compensate by adding a universal paragraph to every reply.

## Shadow the live queue

Run in `draft` for at least two representative business days, including one high-volume day if possible.

Compare the Agent's decision with the maintainer's actual action. Before automatic sending, require:

- zero unverified promises;
- zero automatic replies to always-review categories;
- zero replies after a thread was clearly closed without new information;
- zero drafts when the latest non-draft sender is a Filo colleague;
- zero language mismatches;
- zero standalone or duplicate-thread drafts, and zero saved drafts missing the visible quoted original;
- zero skipped Groups-only customer requests when the external Reply-To/original sender pair is verified;
- zero review-required items without a safe draft unless the audit names the specific recipient, language, or safety gate that blocked drafting;
- zero customer-facing internal implementation terms;
- zero concrete Feature acknowledgments without a Feature ticket and auditable product-review routing;
- zero released replies without a named published version and release evidence;
- zero duplicate release-follow-up notification keys;
- every kept or dropped draft has a final audit record with explicit IDs and fingerprints;
- all sincere suggestions reflect a concrete user need or tradeoff;
- all Bug follow-ups recognize meaningful new evidence;
- all Bug progress claims match repository Issue/PR/release state;
- all Bug replies include the relevant Issue/PR number without a private link;
- all multi-defect messages receive separate tracking and status for each defect;
- policy replies use the current verified facts;
- the maintainer agrees with the send/no-send decision on at least 95% of low-risk threads.

Disagreement on a high-risk thread is not part of the 5% allowance; it blocks auto-send for that category.

## High-volume triage order

Process queues in this order:

1. Security, privacy, account access, payment, refund, and credible safety issues → human owner.
2. New Bug evidence or a Filo action already owed → continue the operational thread.
3. Sincere product suggestions with a concrete workflow or tradeoff → give a substantive acknowledgment.
4. Clear first-time policy questions → concise verified answer.
5. Repeated no-new-information loops, abuse without a service issue, content-confirmed spam, and automated mail → close or no reply. A Gmail `SPAM` label alone never decides this.

Do not push thoughtful suggestions to the bottom merely because they are not urgent. Batch them separately so the Agent has room to articulate the idea instead of pasting the policy response.

## Enable guarded auto-send narrowly

Start with an empty allowlist. Add one category at a time only after shadow performance is stable.

Reasonable first candidates, if policy is fully verified:

- a first-time, single-question request about a confirmed plan boundary;
- a simple request for one missing Bug detail;
- a factual status update whose underlying Issue state was just verified;
- an acknowledgment that a well-formed suggestion was recorded, when the actual record was verified.

Keep these in review:

- emotionally complex or highly personal messages;
- long-time users describing lost workflows;
- sincere proposals that deserve product judgment;
- repeated disagreement where tone determines whether to close;
- every category listed under `always_review_categories`.

Automatic sending is a policy permission, not an Agent decision. The Agent must not expand its allowlist, change its mode, or loosen review categories. Every auto-sent item must first be created as a normal threaded Gmail draft, pass the persisted MIME/quoted-original gate, and then be sent with `gmail_send_draft` using the exact verified draft ID. A send receipt (sent message ID and timestamp) must be recorded; a missing receipt fails closed.

The current project policy uses `guarded-auto` only for `bug_or_reliability` and `product_capability_question`. Feature requests, product plans, pricing or paid-operation questions, billing, account, privacy/security, legal, and compensation remain draft-only for human review. Partnership, press, influencer, sponsorship, and special-commercial-term messages are configured as `no-reply` and do not receive a draft.

## Daily quality check during the transition

Review a small sample from each decision class:

- 5 sent/drafted policy replies;
- all sincere suggestions;
- all `review-required` decisions;
- all closed or `no-reply` threads;
- any thread where the user wrote again after a closing reply.

Pause guarded auto-send for the affected category if any reply:

- states a stale or wrong policy fact;
- invents an internal action or promise;
- mistakes useful new information for repetition;
- becomes defensive, judgmental, or sales-heavy;
- exposes private user classification;
- repeatedly sounds like the same template.

Keep drafting available while the category is recalibrated. Do not disable the entire support workflow for one isolated category unless the shared policy source is unreliable.
