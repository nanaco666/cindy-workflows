# Bug status workflow

Use this workflow before drafting any Filo Bug or reliability reply. The repository state, not remembered release status or a previous support reply, is authoritative.

## 1. Split and identify the defects

- Read the complete thread and list every distinct broken outcome.
- Capture the minimum search facts for each: subsystem, visible symptom or error, platform, app version, and meaningful reproduction detail.
- Treat two symptoms as separate until repository evidence shows the same root cause.

## 2. Search before writing

Search the configured canonical and related repositories for:

1. exact error text and distinctive user wording;
2. subsystem plus symptom, in Chinese and English where useful;
3. matching open and closed Issues;
4. open, closed, and merged PRs;
5. Issue–PR relationships, merge commit, release/tag, and shipped-version evidence.

Judge same root cause semantically. Prefer updating one existing carrier over creating a second Issue. Immediately before creating an Issue, repeat the search against current repository state.

## 3. Check version applicability before choosing status

For every Bug message that contains an app version, create a `bug_version_checks[]` entry and compare the customer's reproducing version with the first verified release that contains the candidate fix. Compare only the same product platform and release channel.

| Version relationship | Required conclusion and action |
|---|---|
| Customer version is older than the same-platform fix release | `update_to_newer_fix`; it is valid to name the newer released version and ask the customer to update and retest |
| Customer version is equal to or newer than the same-platform fix release and the failure still occurs | `regression_or_fix_not_effective`; the old PR/Release does not prove completion. Re-search the current Issue/PR state and add this reproduction to an open carrier, or create an accurate regression Issue when no carrier exists |
| Candidate fix is for a different platform | `different_platform`; it cannot prove the customer's platform is fixed |
| Platform or versions cannot be reliably compared, or no applicable release exists | `unverified` or `no_applicable_release`; use `review-required` rather than claiming resolution |

Do not reopen a closed Issue automatically. Add the new evidence where repository policy permits, create a regression Issue when appropriate, or route the case for human review. A post-release reproduction reply may say the case is being rechecked only after the current run records a verified Issue/PR action ID.

## 4. Choose the verified status

| Repository state | Required internal action | Customer-facing status |
|---|---|---|
| Fix is released in a known version and is newer than the customer's same-platform reproducing version | Verify the release contains the merged PR and the version comparison passes | State that it is released, include a customer-readable PR/Issue ticket number, ask the user to update and retest |
| PR is merged but not verified as released | No additional write unless the user adds new evidence | State that `PR ticket #N` / `PR 工单 #N` is merged and waiting for release; do not expose tag terminology |
| PR is open or awaiting merge | Add new reproduction evidence to the linked Issue or PR only when it is not already present | State that the problem is being handled in `PR ticket #N` / `PR 工单 #N`; give no merge or release date |
| Issue exists but no resolving PR exists | Add one concise, non-duplicate comment containing the new version/platform/reproduction evidence and a request for development prioritization | State that it is recorded as `Issue ticket #N` / `Issue 工单 #N` and that the new evidence was sent to the developers for expedited handling |
| No matching Issue or PR exists | Create a redacted Bug Issue in the configured repository with the allowed type/client labels | State that `Issue ticket #N` / `Issue 工单 #N` was created and the problem was sent to the developers for expedited handling |
| Search, permission, or write fails | Make no repository claim | Mark `review-required`; do not create a customer draft that implies progress |

Issue creation or a new evidence/priority comment is the auditable developer notification. Do not write “notified,” “escalated,” or “expedited” unless that action succeeded in the current run. Do not repeatedly comment when the same evidence is already present.

Every non-released Bug reply must add a `follow_up` block to the manifest with a stable `tracking_key`, one of `recorded`, `being_handled`, or `merged_waiting_release`, and `next_check_at`. The periodic queue rechecks it until a named published version contains the fix. Closing an Issue or merging a PR does not by itself authorize a released reply.

## 5. Issue write boundary

When creating an Issue:

- use a concise Chinese title and body;
- remove customer names, addresses, message IDs, private links, and unrelated quoted content;
- include app version, platform, observable failure, impact, reproduction facts, and whether diagnostic material is available;
- use only labels allowed by the local policy;
- do not assign or mention an individual developer unless the repository already defines that ownership;
- do not close/reopen Issues, modify code, create or edit PRs, or promise priority/date.

When updating an existing Issue or PR, add only genuinely new evidence. Preserve the original report; do not overwrite another reporter's description.

## 6. Draft structure

Use this shape, adapting naturally to the sender's language:

```text
Hi <name>,

Thanks for reaching out. <Specific symptom or impact> is tracked as Issue ticket #N for reference.

<Verified repository status with customer-readable Issue/PR ticket wording. State whether it is recorded, being handled, merged and waiting for release, or released.>

<One necessary next step, only when useful.>

Thanks again for the detailed report.

Best,

Filo Support
```

For Chinese, use the same rhythm with `Issue 工单 #N` / `PR 工单 #N`, then close with `祝好，` and `Filo Support`. When the only verified carrier is a PR, adapt the opening reference to that PR instead of inventing an Issue number. If no carrier exists yet because a repository gate failed, do not use this template or imply that the problem was recorded.

Do not include GitHub links because the repositories are private. Numbers are evidence identifiers for the user and the support team.

For an email containing multiple defects, use one short bullet per defect with its own Issue/PR status. Never imply that one fix covers every reported problem unless the repository proves a shared root cause.

## 7. Human-decision boundary

Concrete feature requests follow the redacted Feature ticket and product-review workflow in `scenario-playbook.md`; they still remain `review-required` and draft-only. Broad product plans, pricing, subscriptions, paid operations, commercial policy, and roadmap decisions require human judgment without creating a product commitment or announcing a plan. Partnership, press, influencer, sponsorship, and special-commercial-term mail is outside the support reply templates: classify it as `no-reply` and create no draft.
