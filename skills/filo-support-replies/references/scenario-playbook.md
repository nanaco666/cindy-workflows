# Scenario playbook

## Decision table

| Path | What matters | Default action | Continue when | Stop or escalate when |
|---|---|---|---|---|
| Existing capability / how-to | Requested outcome, current settings path, constraints | Verify current client/server behavior, then give the exact steps; do not create a Feature ticket | The customer cannot find the control or reports the documented path does not work | Capability evidence is contradictory or the path fails → review or Bug triage |
| Sincere suggestion | Underlying job, benefit, tradeoff | Reflect the idea, give honest status, ask one useful question or record it | New use case, constraint, or evidence appears | No status exists → review; never invent roadmap |
| Concrete feature request | User-visible capability and expected behavior | First prove the capability is partial/missing; then search duplicates, create/reuse a redacted Feature ticket, and route it to product review | The request is specific enough to assess and record without more private data | Capability is unverified, repository write/review routing fails, or product commitment is requested → review without claiming action |
| Bug or reliability | Observable failure, impact, minimum reproduction, verified Issue/PR/release state | Follow `bug-status-workflow.md`; update or create the proper Issue before claiming progress | The customer sends new evidence after the latest Filo reply | Latest message is from Filo, repository evidence is unavailable, or security/privacy/account impact exists → stop or review |
| Free-AI or policy concern | Effect on the person's workflow and verified policy | Acknowledge effect, state policy once, give remaining choices without hard selling | A new policy question or concrete product idea appears | Repeated fairness debate with no new facts → close |
| Billing/refund/account | Correctness, ownership, access, deadlines | Prepare a fact-safe threaded acknowledgment using the manual-handoff shape in `voice-and-boundaries.md` and route to the authorized owner | Until the operational issue is resolved | Always `review-required` for final decisions; omit the draft only when recipient or safe wording cannot be verified |
| Partnership/press/exception | Concrete proposal, audience, deliverables, authority | `no-reply`; do not create a draft | None | Always close without a customer draft |
| Repeated loop | Whether anything materially changed | One brief closing reply if not already closed | A new fact changes handling | After clear closure and no new information → `no-reply` |
| Abuse/spam/safety | Unresolved service issue and credible risk | Read enough content to distinguish a real support request from actual spam; ignore insults and answer a real service issue once | New service evidence appears | Confirmed spam/automation with no service issue → no reply; threat, self-harm, security, legal, or safety risk → review/escalate |

A Gmail `SPAM` label is not a classification decision. Include labeled messages in intake, read their content safely, and apply the normal Bug/Feature/support workflow when the message is actionable. Do not move, relabel, or delete it unless separately authorized. Likewise, a Google Groups wrapper is not automatically a duplicate: use it when it is the sole representation and its external Reply-To and original sender match; skip it only when a more authoritative representation exists.

## Sincere product feedback

Do not treat a thoughtful suggestion as a policy complaint simply because it asks Filo to change direction.

Use this sequence:

1. State what the idea would improve for the user.
2. Say which part seems useful, difficult, or not yet proven.
3. Give the actual current status.
4. Ask one question only if its answer would affect evaluation.
5. Record or route the feedback when authorized.

Useful language:

- “你提的重点是……”
- “这个思路能解决的是……”
- “这里的取舍在于……”
- “目前我们还没有决定这样做，所以我不能把它说成计划；但这个使用场景值得单独记录。”

Do not promise that “the team will seriously consider it” unless there is a real intake process. Prefer stating the concrete action taken.

## Concrete feature requests

Treat a specific requested capability differently from a broad roadmap question. Before drafting:

1. Extract each user-visible outcome and inspect the current client, server, product docs, settings labels, and verified policy.
2. Record a `capability_checks[]` item with `existing`, `partial`, `missing`, or `unverified` plus evidence IDs. If the outcome already exists, answer with the exact settings path and constraints; user confusion is not a Feature.
3. Only for a verified partial/missing outcome, search both open/closed Issues and PRs in the routed repository, recording separate evidence even when either search returns no match.
4. Reuse a semantic duplicate; otherwise create one redacted Feature Issue with the configured labels.
5. Ensure the configured product-review label/action is present. Record its action ID in `product_review_action_ids`.
6. Keep the missing capability `review-required` and draft only: the ticket records the request but does not promise scope, priority, or delivery.
7. Say only that `Feature ticket #N` / `Feature 工单 #N` was recorded and that the Filo product team was asked to review it, then thank the sender for the suggestion. Use the compact ticketed-acknowledgment shape from `voice-and-boundaries.md`: one rephrased problem sentence, the ticket sentence, thanks — no replay of the request's details.

If duplicate search or the repository write fails, do not claim the request was recorded or routed.

## Existing draft review

Treat a saved Gmail draft as unverified work, not as proof that the thread was handled. Fetch and read the actual draft, then compare it with the latest customer message and current product/repository evidence.

- Use `skip_verified` only when the draft is in the customer's language, replies to the correct message, visibly quotes the original, gives current capability guidance, and cites the verified Issue/PR/Feature state.
- Use `update` when any of those facts or formatting checks are missing. Update the same Gmail draft ID in place; do not delete it and create a new draft.
- Bind the review to every saved draft ID and the content fingerprints produced from the fetched saved drafts. A generic note such as “draft checked” is not evidence.
- If the latest effective non-draft sender is a Filo colleague, stop before draft review or repository work for ordinary intake.

## Free-to-Plus AI transition

Load the current verified policy. Do not rely on remembered dates, quotas, plan names, or exceptions.

The reply should usually contain:

- one sentence recognizing what the change disrupts;
- one clear statement of what changes and what remains available;
- at most one brief reason;
- the options that genuinely exist;
- a close or a focused product-feedback question.

Do not:

- lead with cost accounting;
- repeatedly say the policy is “sustainable” without answering the sender;
- imply that a user who cannot pay is less valuable;
- push Plus after the sender clearly says it is unaffordable;
- offer private credits or grandfathering without an approved rule;
- debate whether leaving for a competitor is rational.

When a sender proposes a thoughtful alternative—trial usage, per-action purchase, BYOK, education pricing, a grace period—separate acknowledgment from commitment. Explain what problem the idea would solve, then state the current boundary.

## Bugs and product failures

Policy and entitlement never reduce the seriousness of a genuine bug. A free user and a Plus user get the same factual triage standard.

Before ordinary Bug/Feature intake, inspect the latest non-draft Gmail message. If any `@support.example.invalid` colleague sent it, stop with `no-reply`; never generate an automated correction to that colleague's response. Continue only when the customer wrote again afterward. The sole exception is an audited `resolution_follow_up` after a verified published version; it is a new status notification, not a correction.

Follow [bug-status-workflow.md](bug-status-workflow.md) before drafting. Search Issue and PR state for every distinct defect, update or create the tracker when authorized, and cite it as a customer-readable ticket without a private link.

- Identify the broken outcome and its impact.
- Ask only for information not already present.
- Once enough information exists, stop making the user repeat it.
- If a work item is created, verify it before saying so.
- If an Issue already exists without a resolving PR, add the new evidence and an explicit prioritization request before saying developers were notified again.
- If no matching Issue exists, create one before saying a work item was opened.
- If a PR is merged but not released, say it should arrive in the next release; do not say the live version is fixed.
- If the customer still reproduces on the same platform at a version equal to or newer than the release that first contained the candidate fix, treat the report as a regression or ineffective fix. Re-search and update/create the correct carrier; never reply that the old fix already solved it.
- Only recommend updating when the customer's version is older than a verified same-platform fix release. A release on iOS cannot prove a Desktop report is fixed, and vice versa.
- If a message reports several defects, answer and track each one separately.
- Once a defect is recorded, reply with the compact ticketed-acknowledgment shape from `voice-and-boundaries.md`: confirm receipt, rephrase the problem in one sentence (never quote the sender's clauses back), give the ticket and verified status, and close. Do not re-enumerate the customer's reported details; `lint_reply.py` rejects verbatim replays as errors.
- Do not promise a later update unless a real owner or tracking mechanism exists. Without one, simply say that no more information is needed from the user now.
- Contact the user again only for one specific missing detail or a meaningful status change that is actually tracked.
- Never promise a fix date without an approved owner and timeline.

Concrete feature requests use the capability check and Feature ticket workflow above. Broad product plans, roadmap choices, pricing, subscriptions, and operations policy remain bounded product decisions; state the verified current option and an approved “no current plan” boundary directly when available instead of escalating a question that already has a settled answer.

## Released-version follow-up

Run `scripts/follow_up_queue.py queue` on the audit log at the configured interval. For every due pending Bug/Feature:

- search the repository and release records again;
- if still pending, record the check with `record-check` and a new evidence ID, then schedule the next check;
- if the Issue is closed or PR merged but no published version contains the change, keep it pending;
- only when a named published version contains the relevant fix/feature, use `workflow_kind: resolution_follow_up`, include the prior audit fingerprint and release evidence IDs, and draft a reply in the original thread;
- for a Bug, also compare the customer's recorded reproducing platform/version with that published fix. If the customer version is equal or newer, keep or reopen tracking through a verified repository action instead of sending a resolution follow-up;
- name the released version and ask the customer to update/retest only when useful;
- do not create a second draft for the same `notification_key`.

This narrow follow-up may proceed when the latest thread message is from Filo, but all canonical-thread, language, existing-draft, validation, and draft-only rules still apply.

Two rounds are not a cap for a progressing investigation. Five evidence-rich replies may be appropriate; a second repetitive policy argument may already deserve closure.

## High-risk mail

Always require human review before sending a substantive decision about:

- charges, refunds, chargebacks, invoices, or payment disputes;
- login, account ownership, account recovery, deletion, or data export;
- privacy, security, vulnerability reports, or suspected compromise;
- legal demands, regulators, law enforcement, or threats of litigation;
- journalists, public statements, coordinated campaigns, or viral incidents;
- partnerships, sponsorships, influencers, or special commercial terms (these are `no-reply`, not draftable support cases);
- self-harm, threats, harassment, or credible safety concerns;
- compensation, grandfathering, gifts, credits, or exceptions not explicitly authorized.

For the remaining high-risk categories, the Agent should prepare a threaded `review-required` acknowledgment that accurately names the request and what remains undecided, but must not decide the outcome. Partnership/press/exception mail is the explicit no-draft exception: record `no-reply` and do not write a customer response.

For manual operations (refunds, account changes, invoice corrections), use the manual-handoff shape in `voice-and-boundaries.md`: the request needs manual handling by a team member, it has been routed/reminded, and it will be handled on working days. “已转交提醒”/“routed” wording is allowed only when this run recorded the manual item in the audit log and the run report's 人工事项 list; never state the outcome, an amount, or a specific date.

Do not ask for passwords, one-time codes, full card or bank details, identity documents, security logs, or other sensitive material through ordinary email unless an approved policy explicitly requires that exact channel. Leave the secure verification step to the authorized owner.

## Repeated disagreement and abuse

Do not mirror hostility or diagnose motive. Extract any unresolved service question and answer it once.

No new information includes:

- repeating the same conclusion in stronger language;
- asking the same policy question with different wording;
- naming competitors;
- announcing an intention to uninstall or leave;
- demanding that Filo “admit” the policy is unfair;
- insults unconnected to a new service fact.

New information includes:

- a concrete workflow or accessibility impact not previously described;
- evidence that published policy and product behavior differ;
- a new billing, account, privacy, or security fact;
- a requested item that Filo previously asked the user to provide;
- a real change in issue or release status.

Once closed, silence is a valid support outcome. Do not send a final message merely to have the last word.
