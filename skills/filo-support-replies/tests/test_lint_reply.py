from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lint_reply.py"


class LintReplyTests(unittest.TestCase):
    def run_lint(self, source: str, reply: str, *extra: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "source.txt"
            reply_path = Path(tmp) / "reply.txt"
            source_path.write_text(source, encoding="utf-8")
            reply_path.write_text(reply, encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(reply_path),
                    "--source-text",
                    str(source_path),
                    *extra,
                ],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_wrong_language_is_error(self) -> None:
        result = self.run_lint(
            "The inbox is empty after tapping a notification.",
            "Hi Alex，\n\n这个问题已经记录为 Issue 工单 #3448。\n\n感谢你的反馈。\nFilo Support",
            "--category",
            "bug",
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("does not match source language", result.stdout)

    def test_internal_term_is_error(self) -> None:
        result = self.run_lint(
            "The inbox is empty after tapping a notification.",
            "Hi Alex,\n\nThe release tag is not ready. This is recorded as Issue ticket #3448.\n\nThanks.\nFilo Support",
            "--category",
            "bug",
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("internal release terminology", result.stdout)

    def test_customer_readable_english_ticket_passes(self) -> None:
        result = self.run_lint(
            "The inbox is empty after tapping a notification.",
            "Hi Alex,\n\nThis is recorded as Issue ticket #3448 and is being handled.\n\nThanks for the detailed report.\nFilo Support",
            "--category",
            "bug",
            "--subject",
            "Re: Sync problem",
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_feature_reply_requires_customer_readable_feature_ticket(self) -> None:
        result = self.run_lint(
            "Please keep unread mail at the top of the inbox.",
            "Hi Alex,\n\nWe recorded the request and asked the product team to review it.\n\nThanks for the suggestion.\nFilo Support",
            "--category",
            "feature",
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Feature reply must include", result.stdout)

    def test_customer_readable_feature_ticket_passes(self) -> None:
        result = self.run_lint(
            "Please keep unread mail at the top of the inbox.",
            "Hi Alex,\n\nWe recorded your unread-first request as Feature ticket #1011 and asked the Filo product team to review it.\n\nThanks for the suggestion.\nFilo Support",
            "--category",
            "feature",
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_report_like_multi_part_reply_is_warning(self) -> None:
        result = self.run_lint(
            "How can I add an HTML signature? I would also prefer a one-time purchase.",
            "Hi William,\n\nFilo Desktop currently supports rich-text signatures, but not raw HTML. We recorded Feature ticket #1005.\n\nFilo Plus currently offers monthly and yearly billing.\n\nThanks for explaining both needs.\nFilo Support",
            "--category",
            "feature",
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("'currently' appears more than once", result.stdout)
        self.assertIn("abstract closing", result.stdout)

    def test_warm_multi_part_reply_passes(self) -> None:
        result = self.run_lint(
            "How can I add an HTML signature? I would also prefer a one-time purchase.",
            "Hi William,\n\nThanks for explaining what you're trying to set up. Pasting an existing HTML signature would save you from rebuilding it by hand, and I can see why a one-time payment could be more appealing than another subscription.\n\nFor the signature, Filo Desktop already lets you create a rich-text signature in Settings → Signature. What it doesn't support yet is raw HTML, so we've recorded Feature ticket #1005 for product review.\n\nOn pricing, Filo Plus is available with monthly or yearly billing. We don't offer a one-time purchase, and we don't currently plan to add one.\n\nThanks again for taking the time to share both requests.\nFilo Support",
            "--category",
            "feature",
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_compact_ticket_first_reply_with_signoff_passes(self) -> None:
        result = self.run_lint(
            "I can't unlink Slack from the work account I can no longer access.",
            "Hi Chris,\n\nThanks for reaching out. We've recorded the account-unlinking request as Issue ticket #3508 for reference.\n\nThis change can't be completed from the signed-out account. The request is now recorded for the account team to review; we don't have a completion date to confirm yet.\n\nThanks for your patience while the request is reviewed.\n\nBest,\n\nFilo Support",
            "--category",
            "bug",
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_ai_assistant_signature_is_error(self) -> None:
        result = self.run_lint(
            "Please help unlink the account.",
            "Hi Chris,\n\nThanks for reaching out. This is recorded as Issue ticket #3508.\n\nBest,\n\nFilo's AI Support Assistant",
            "--category",
            "bug",
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("AI-assistant signature", result.stdout)

    def test_untracked_teammate_soon_followup_is_warning(self) -> None:
        result = self.run_lint(
            "Please help unlink the account.",
            "Hi Chris,\n\nThanks for reaching out. This is recorded as Issue ticket #3508.\n\nI've passed this to a teammate, and they will follow up here soon.\n\nBest,\n\nFilo Support",
            "--category",
            "bug",
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("future teammate follow-up", result.stdout)
        self.assertIn("handoff must be backed", result.stdout)

    def test_chinese_detail_replay_is_error(self) -> None:
        source = (
            "最近每次打开邮件都要等待好几秒才能显示内容，摘要也一直生成失败，"
            "版本 2.2.5，Windows 11。"
        )
        replay = (
            "Hi 小王，\n\n你提到的问题已经收到。最近每次打开邮件都要等待好几秒才能显示内容，"
            "摘要也一直生成失败，我们已经记录为 Issue 工单 #3377。\n\n感谢你的反馈。\nFilo Support"
        )
        result = self.run_lint(source, replay, "--category", "bug")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("echoes the customer's wording verbatim", result.stdout)

    def test_english_detail_replay_is_error(self) -> None:
        source = (
            "Every time I open a message the body takes several seconds to render and "
            "the AI summary always fails with generation error on Windows."
        )
        replay = (
            "Hi Alex,\n\nThanks for reaching out. Every time I open a message the body "
            "takes several seconds to render, and we've recorded this as Issue ticket #3400.\n\n"
            "Thanks.\nFilo Support"
        )
        result = self.run_lint(source, replay, "--category", "bug")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("echoes the customer's wording verbatim", result.stdout)

    def test_compact_rephrased_chinese_bug_reply_passes(self) -> None:
        source = (
            "最近每次打开邮件都要等待好几秒才能显示内容，摘要也一直生成失败，"
            "版本 2.2.5，Windows 11。"
        )
        compact = (
            "Hi 小王，\n\n这个问题已经收到：打开邮件较慢且摘要生成失败。"
            "已记录为 Issue 工单 #3377，正在处理。\n\n感谢你的反馈。\nFilo Support"
        )
        result = self.run_lint(source, compact, "--category", "bug")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_ni_ti_dao_de_replay_pattern_is_warning(self) -> None:
        result = self.run_lint(
            "摘要无法生成，请帮忙看看。", "Hi 小王，\n\n你提到的问题已收到，已记录为 Issue 工单 #3377。\n\n感谢。\nFilo Support", "--category", "bug"
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("replay pattern", result.stdout)

    def test_manual_handoff_phrase_requires_backing(self) -> None:
        result = self.run_lint(
            "我上个月的订阅扣款想申请退款，麻烦处理一下。",
            "Hi 小李，\n\n退款请求需要团队成员人工处理，已转交提醒给相关同事，会在工作日内处理。\n\n感谢你的耐心。\nFilo Support",
            "--category",
            "other",
        )
        self.assertIn("handoff actually occurred", result.stdout)

    def test_padded_ticketed_reply_is_compact_warning(self) -> None:
        result = self.run_lint(
            "The inbox is empty after tapping a notification.",
            "Hi Alex,\n\nThis is recorded as Issue ticket #3448.\n\nThe inbox can be empty when sync stops.\n\nWe are checking the sync path now.\n\nA fix is in progress with the developers.\n\nThanks.\nFilo Support",
            "--category",
            "bug",
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("should stay compact", result.stdout)

    def test_simplified_reply_to_traditional_customer_is_error(self) -> None:
        result = self.run_lint(
            "點擊通知以後收件匣是空的，重新整理也沒有恢復。",
            "Hi 小王，\n\n这个问题已经收到：点击通知后收件箱是空的。已记录为 Issue 工单 #3448，正在处理。\n\n感谢你的反馈。\nFilo Support",
            "--category",
            "bug",
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("Traditional (繁體)", result.stdout)
        self.assertIn("customer's script", result.stdout)

    def test_matching_traditional_reply_passes(self) -> None:
        result = self.run_lint(
            "點擊通知以後收件匣是空的，重新整理也沒有恢復。",
            "Hi 小王，\n\n這個問題已經收到：點擊通知後收件匣是空的。已記錄為 Issue 工單 #3448，正在處理。\n\n感謝你的反饋。\nFilo Support",
            "--category",
            "bug",
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_traditional_canned_phrases_still_warn(self) -> None:
        result = self.run_lint(
            "點擊通知以後收件匣是空的，重新整理也沒有恢復。",
            "Hi 小王，\n\n這個問題已經收到：點擊通知後收件匣是空的。已記錄為 Issue 工單 #3448，正在處理。請您耐心等待。\n\n感謝您寶貴的反饋。\nFilo Support",
            "--category",
            "bug",
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("generic acknowledgment", result.stdout)
        self.assertIn("waiting request", result.stdout)


if __name__ == "__main__":
    unittest.main()
