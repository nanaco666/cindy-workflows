# Synthetic examples

These examples are patterns, not fixed templates. Replace every product fact with the current verified policy.

## 1. Sincere proposal during the free-AI transition

User:

> 我理解 AI 有成本，但完全关掉以后，新用户根本不知道 Plus 值不值得。能不能每周保留几次摘要或待办提取？

Better reply:

> 你提的重点不是单纯想继续免费使用，而是担心用户在付费前没有机会判断 AI 是否适合自己的工作流。这个问题确实存在，而“保留少量体验次数”能解决的也正是体验门槛。
>
> 目前已经确定的调整仍会按现行方案执行，我们现在不能承诺免费周额度。不过你这个场景说明，“付费前体验机制”解决的是一个独立问题，不应简单归到价格抱怨里。如果方便补充一个信息：你觉得最能帮助用户判断价值的是摘要、待办提取，还是写作？这个答案会直接影响这种体验是否有效。

Why it works: it articulates the product value in the idea, preserves the current boundary, and asks one consequential question.

## 2. Long-time user feels betrayed

User:

> 我从最早就开始用了，现在突然把 AI 关掉，感觉你们根本不在乎老用户。

Better reply:

> 你已经把 AI 用进了原来的工作方式，所以这次变化对你不是一个普通的套餐调整，而是会直接打断已经形成的习惯。我们没有为老用户保留免费的 AI 权益，这一点不会因为你使用时间更久而改变，我也不想用模糊的话让你期待一个目前不存在的例外。
>
> 免费版的核心邮件功能仍会保留；需要 AI 的功能会按当前政策转入 Plus。你对老用户过渡方式的意见我们会作为独立反馈记录，但这封邮件里我不能承诺补偿或延期。

Why it works: it acknowledges the real loss without fake agreement or an invented concession.

## 3. User cannot afford Plus

User:

> 我是学生，现在真的付不起 Plus。

Better reply:

> 明白，这种情况下继续推荐升级对你没有帮助。你仍然可以免费使用 Filo 的核心邮件功能，但当前政策下 AI 功能不会继续包含在免费版里，我们也没有可以单独提供的学生额度。
>
> 如果学生方案或其他正式政策以后上线，我们会通过公开渠道说明；目前我不想给你一个并不存在的期待。

Why it works: it does not guilt, upsell, or invite a negotiation the team cannot honor.

## 4. Bug report keeps progressing after two rounds

User, third reply:

> 我又试了一次，只有 Gmail 的别名发件会失败；直接用主地址可以，macOS 版本是 2.8.1。

Better reply:

> 这个补充很关键：问题现在已经缩小到 Gmail 别名发件，而不是所有发件都失败。我们已有主地址成功、别名失败以及 macOS 2.8.1 这三个条件，不需要你再重复前面的步骤。
>
> 这些信息已经足够让下一步排查聚焦在别名发件路径上，不需要你再重复前面的步骤。目前也不需要你继续补材料。

Why it works: the third round is justified because it materially narrows the bug, and the reply does not invent a follow-up promise.

## 5. Repeated policy argument after a clear answer

User:

> 所以你们就是不承认这在逼人付费？别的产品都比你们大方。

Closing reply, if the thread has not already been closed:

> 我们已经说明了当前调整和免费版仍保留的范围，也理解你不接受这个决定。你这封邮件没有带来需要重新判断的新事实，我们目前也没有不同的方案可以提供，所以这条沟通先在这里结束。如果政策发生变化，我们会通过正式渠道公布。

If an equivalent closing reply was already sent: choose `no-reply`.

## 6. English product feedback

User:

> Instead of removing AI from Free entirely, why not let people bring their own API key? I don't need you to pay for my usage.

Better reply:

> You're separating two things that are easy to conflate: access to Filo's AI workflows and who pays the model cost. A bring-your-own-key option could preserve those workflows for people who are comfortable managing their own provider account, so the idea addresses a real gap in an all-or-nothing plan.
>
> It isn't part of the currently approved transition, so I can't present it as a planned option. I've recorded it specifically as a BYOK proposal rather than a request for free hosted usage. The main product question for us is how much setup and support complexity that option would introduce.

Why it works: it demonstrates independent product understanding and does not imply roadmap commitment.

## 7. Generic AI-sounding draft

Avoid:

> Thank you for your valuable feedback. We completely understand your frustration and sincerely apologize for any inconvenience. Your feedback is very important to us and has been shared with the relevant team. Please feel free to reach out if you have any other questions.

Problems:

- no detail proves the message was read;
- “completely understand” overclaims;
- “shared with the team” may be false;
- no answer or boundary exists;
- the final sentence needlessly invites another round.

## 8. Bug with a merged but unreleased fix

Repository evidence:

- matching Issue `#3410`;
- fixing PR `#3422` is merged;
- no release/tag contains the merge yet.

Better reply:

> Hi Alex,
>
> Thanks for reporting that the message body disappears after closing the reply editor.
>
> This is tracked as Issue ticket #3410, and the fix has been merged in PR ticket #3422. It is not in the current release yet, so it should arrive with the next version rather than requiring another workaround from you.
>
> Thanks again for including the app version and reproduction steps.
> Filo Support

Why it works: it distinguishes merged from released and gives auditable identifiers without exposing private links.

## 9. Bug with an open PR

Better reply:

> Hi Alex,
>
> Thanks for the detailed report about Gmail sync stopping after the update.
>
> The issue is being handled in PR ticket #3428. It is still awaiting merge, so we cannot confirm a release version or date yet.
>
> Your details about when synchronization stops have been added to the investigation. Thanks for helping us narrow it down.
> Filo Support

Why it works: “being handled” is backed by a real PR, while the merge and release timing remain bounded.

## 10. Existing Issue without a PR

After adding the new evidence and prioritization request to Issue `#3431`:

> Hi Alex,
>
> Thanks for confirming that the problem still occurs in Filo 2.2.6 on Windows.
>
> This is tracked as Issue ticket #3431. We have added your 2.2.6 reproduction and notified the developers again for expedited handling; there is no resolving PR or confirmed release version yet.
>
> Thanks for the concrete version and platform details.
> Filo Support

Why it works: the notification claim follows an actual repository write and does not invent a timeline.

## 11. No existing Issue

After creating Issue `#3435`:

> Hi Alex,
>
> Thanks for reporting that adding multiple attachments causes sending to fail.
>
> We could not find an existing tracker for this failure, so we created Issue ticket #3435 and notified the developers for expedited handling. We do not have a fix or release date to confirm yet.
>
> Thanks again for helping us identify it.
> Filo Support

Why it works: the reply names the concrete action, does not overstate progress, and keeps product timing with the developers.

## 11A. Customer still reproduces after the older fix release

Customer evidence:

- the problem still occurs on Filo Desktop `2.2.6`;
- the previously matched fix first shipped in Desktop `2.2.4`;
- this run added the `2.2.6` reproduction to Issue `#3431`.

Correct reply:

> Hi Alex,
>
> We received your report that this problem still occurs in Filo Desktop 2.2.6. The earlier fix predates the version you are using, so it cannot be treated as resolving this reproduction.
>
> We have added the new evidence to Issue ticket #3431 and are rechecking it.
>
> Thanks for reporting it.
>
> Best,
>
> Filo Support

Why it works: it treats the newer-version reproduction as regression evidence, cites the verified repository update, and does not recycle an older release as proof that the customer is fixed.

## 12. Colleague already replied

Thread order:

1. Customer reports a Bug.
2. `teammate@example.invalid` replies.

Required result: `no-reply`. Do not evaluate whether Connie's wording or status was perfect, do not search the repository, and do not create a corrective follow-up draft. If the customer later sends a new message, re-enter the workflow from that new inbound message.

## 13. Existing primary-account switch is a how-to, not migration

User asks to move account ownership, settings, todos, automations, and a future subscription from a work Google account to a personal account while keeping the work mailbox connected.

After verifying the current Desktop and server behavior, draft:

> Hi Mariya,
>
> You don't need to create or migrate to a separate Filo account. In Filo Desktop, first connect your personal Gmail if it isn't connected yet. Then open Settings → Account, open the menu next to the personal Gmail, and choose Set as primary account.
>
> Your existing settings, todos, automations, and subscription stay with the same Filo account, and your work Gmail can remain connected. After switching, the primary account can't be changed again for 30 days.
>
> Thanks for clearly outlining the outcome you need.
> Filo Support

Why it works: it checks the current product first, recognizes this as a self-service setting, gives an exact path and constraint, and avoids an unnecessary escalation.

Formatting for the saved Gmail draft: keep the four reply blocks as separate paragraphs. Bold only `Settings → Account → Set as primary account` and `30 days`; leave the greeting, thanks, and `Filo Support` unbolded. Build it with `compose_email_body.py` as a normal Gmail rich-text reply.

## 14. Feature plus pricing decision

When one email asks for raw HTML signature input and a one-time purchase option, treat them separately. Verify that rich-text signatures already exist but raw HTML source input does not, then create/reuse the Feature ticket only for raw HTML. State that Plus currently offers monthly and yearly billing, has no one-time purchase option, and—when this is the approved product boundary—there is no current plan to add one. Do not describe a settled pricing boundary as an unresolved human task.

Avoid a factually correct but report-like reply made of consecutive `Filo currently...` paragraphs. Prefer:

> Hi William,
>
> Thanks for explaining what you're trying to set up. Being able to paste an existing HTML signature would save you from rebuilding it by hand, and I can see why a one-time payment could be more appealing than another subscription.
>
> For the signature, Filo Desktop already lets you create a rich-text signature in Settings → Signature, with formatting, links, and images. What it doesn't support yet is pasting or editing the raw HTML source. We've recorded that request as Feature ticket #1005 and asked the Filo product team to review it.
>
> On pricing, Filo Plus is available with monthly or yearly billing. We don't offer a one-time purchase, and we don't currently plan to add one.
>
> Thanks again for taking the time to share both requests.
> Filo Support

Why it works: it preserves every verified fact, reflects the practical value of both requests, varies the transitions, and sounds like a reply rather than an internal status report.

## 15. Compact acknowledgment with a tracked handoff

Use this shape when the customer mainly needs confirmation that a request requiring internal access has been received and routed. The Issue and account-review routing below must already exist.

English:

> Hi Chris,
>
> Thanks for reaching out. We've recorded the Slack unlinking request as Issue ticket #3508 for reference.
>
> Because the old work account is no longer accessible, this binding can't be removed through the normal account settings. The request has been routed to the account team for review; we don't have a completion date to confirm yet.
>
> Thanks for your patience while the request is reviewed.
>
> Best,
>
> Filo Support

Chinese:

> Hi Chris，
>
> 谢谢你联系我们。解绑原工作账号关联 Slack 的请求已记录为 Issue 工单 #3508，供你后续查询。
>
> 由于原工作账号已经无法登录，这项绑定不能通过常规账号设置自行移除。请求已转交账号团队评审；目前还没有可以确认的完成时间。
>
> 感谢你的耐心等待。
>
> 祝好，
>
> Filo Support

Why it works: the opening confirms receipt and gives a usable reference number; the next paragraph explains the real constraint and verified handoff without internal jargon; the close is warm but does not promise a reply “soon.” It uses the team identity rather than copying a named agent or AI-assistant signature.

If no tracker or routing record exists, remove both claims. A safe review-required version can acknowledge the request and explain that an account review is needed, but it cannot say the case has been passed to a teammate.

## 16. Minimal ticketed acknowledgment

Once a Bug or Feature is confirmed and recorded, this is the default shape — confirmation, one rephrased problem sentence, the ticket with verified status, thanks. No replay of the sender's details, no “你提到的…” + their original wording.

Chinese, after creating Issue `#3377` for a report about slow mail opening and failed summaries:

> Hi 小王，
>
> 这个问题已经收到：打开邮件较慢，摘要生成失败。已记录为 Issue 工单 #3377，正在处理。
>
> 感谢你的反馈。
>
> 祝好，
>
> Filo Support

English, after recording Feature ticket `#1011` for an unread-first inbox request:

> Hi Alex,
>
> Thanks for the suggestion — keeping unread mail at the top of the inbox. We've recorded it as Feature ticket #1011 and asked the Filo product team to review it.
>
> Thanks for taking the time to share it.
>
> Best,
>
> Filo Support

Traditional Chinese, for the same report as the Simplified example above written in 繁體 — the reply must follow the customer's script, so it uses 繁體 throughout, including `Issue 工單 #N`:

> Hi 小王，
>
> 這個問題已經收到：開啟郵件較慢，摘要生成失敗。已記錄為 Issue 工單 #3377，正在處理。
>
> 感謝你的反饋。
>
> 祝好，
>
> Filo Support

Why it works: the customer gets a usable reference and the real status in under four short paragraphs; the problem is summarized in our own words rather than quoted back. The script matches the customer — a Simplified reply to a Traditional customer is rejected by the linter. Bold at most the ticket phrase or one status phrase. If the message reported several issues, give each one a clause and its own ticket number instead of re-enumerating the details.

## 17. Manual-handoff acknowledgment (refund)

A refund cannot be decided or executed by the reply workflow. Name the request, state manual handling, state the routing reminder (only if this run actually recorded the manual item), and give the working-day expectation. No outcome, amount, or date.

> Hi 小李，
>
> 你的退款请求已经收到。这类请求需要团队成员人工处理，已转交提醒给相关同事，会在工作日内处理；处理结果会由同事在你的原邮件里回复。
>
> 感谢你的耐心。
>
> 祝好，
>
> Filo Support

Why it works: it confirms receipt, sets a bounded expectation without promising the outcome, and the routing claim matches a real manual item recorded in this run's audit and report. If no manual item was recorded, drop “已转交提醒” and write only that the request needs manual handling by a team member.
