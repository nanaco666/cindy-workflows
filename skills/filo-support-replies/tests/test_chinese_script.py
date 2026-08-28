from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "chinese_script.py"
SPEC = importlib.util.spec_from_file_location("chinese_script", SCRIPT)
assert SPEC and SPEC.loader
chinese_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(chinese_script)


class ChineseScriptTests(unittest.TestCase):
    def test_classification(self) -> None:
        cases = [
            ("點擊通知以後收件匣是空的，重新整理也沒有恢復。", "hant"),
            ("点击通知以后收件箱是空的，刷新也没有恢复。", "hans"),
            ("The inbox is empty after tapping a notification.", "unknown"),
            ("Hi 陳先生，已收到。", "unknown"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(chinese_script.chinese_script(text), expected)

    def test_pairs_are_wellformed(self) -> None:
        pairs = chinese_script._PAIRS
        self.assertTrue(all(len(pair) == 2 for pair in pairs))
        self.assertTrue(all(pair[0] != pair[1] for pair in pairs))
        # a backwards pair would leak a Simplified char into the Traditional set
        self.assertFalse(
            chinese_script.SCRIPT_ONLY_SIMPLIFIED & chinese_script.SCRIPT_ONLY_TRADITIONAL
        )
        # shared characters must not count as Simplified evidence
        self.assertFalse(
            chinese_script.AMBIGUOUS_SIMPLIFIED & chinese_script.SCRIPT_ONLY_SIMPLIFIED
        )

    def test_normalize_keeps_shared_checks_working(self) -> None:
        self.assertEqual(
            chinese_script.normalize_simplified("已記錄為 Issue 工單 #3448，正在處理，等待發布"),
            "已记录为 Issue 工单 #3448，正在处理，等待发布",
        )
        self.assertEqual(
            chinese_script.normalize_simplified("請您耐心等待，我們會盡快聯繫您"),
            "请您耐心等待，我们会尽快联系您",
        )

    def test_mismatch_error(self) -> None:
        error = chinese_script.script_mismatch_error(
            "這是繁體的問題描述，請協助處理。", "这个问题已经收到，正在处理。"
        )
        self.assertIsNotNone(error)
        self.assertIn("Traditional (繁體)", error)
        self.assertIn("customer's script", error)
        self.assertIsNone(
            chinese_script.script_mismatch_error("这个问题已经收到。", "正在处理。")
        )
        self.assertIsNone(
            chinese_script.script_mismatch_error(
                "點擊通知以後收件匣是空的。", "這個問題已經收到，正在處理。"
            )
        )


if __name__ == "__main__":
    unittest.main()
