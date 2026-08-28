from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compose_email_body.py"
SPEC = importlib.util.spec_from_file_location("compose_email_body", SCRIPT)
assert SPEC and SPEC.loader
compose = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compose)


class ComposeEmailBodyTests(unittest.TestCase):
    def test_builds_standard_gmail_multipart_html(self) -> None:
        result = compose.build(
            {
                "reply_body": (
                    "Hi Mariya,\n\n"
                    "Open Settings → Account and choose Set as primary account.\n\n"
                    "The primary account can't be changed again for 30 days.\n\n"
                    "Thanks for clearly describing the setup you need.\n\n"
                    "Filo Support"
                ),
                "emphasis": ["Settings → Account", "30 days"],
                "quote_header": "On the original message wrote:",
                "original_text": "Hi Filo team,\nPlease help with <account> migration.",
            }
        )
        self.assertEqual(result["mime_type"], "multipart/alternative")
        self.assertEqual(len(result["payload"]["parts"]), 2)
        self.assertEqual(result["payload"]["parts"][0]["mime_type"], "text/plain")
        self.assertEqual(result["payload"]["parts"][1]["mime_type"], "text/html")
        self.assertIn("<strong>Settings → Account</strong>", result["body_html"])
        self.assertIn("<strong>30 days</strong>", result["body_html"])
        self.assertIn("<blockquote", result["body_html"])
        self.assertIn("&lt;account&gt;", result["body_html"])
        self.assertIn("> Please help with <account> migration.", result["body_plain"])

    def test_rejects_whole_paragraph_emphasis_that_overlaps(self) -> None:
        with self.assertRaisesRegex(ValueError, "overlap"):
            compose.build(
                {
                    "reply_body": "Hi Alex,\n\nOpen Settings → Account today.\n\nThanks.\n\nFilo Support",
                    "emphasis": ["Open Settings → Account today.", "Settings → Account"],
                    "quote_header": "On the original message wrote:",
                    "original_text": "Help me.",
                }
            )

    def test_rejects_greeting_signoff_or_signature_emphasis(self) -> None:
        for phrase in ("Hi Alex,", "Best,", "祝好，", "Filo Support"):
            with self.subTest(phrase=phrase), self.assertRaisesRegex(ValueError, "greeting, sign-off, or signature"):
                compose.build(
                    {
                        "reply_body": "Hi Alex,\n\nOpen Settings → Account.\n\nThanks.\n\nBest,\n\n祝好，\n\nFilo Support",
                        "emphasis": [phrase],
                        "quote_header": "On the original message wrote:",
                        "original_text": "Help me.",
                    }
                )


if __name__ == "__main__":
    unittest.main()
