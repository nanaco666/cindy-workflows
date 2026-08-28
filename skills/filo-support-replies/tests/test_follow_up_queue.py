from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "follow_up_queue.py"
SPEC = importlib.util.spec_from_file_location("follow_up_queue", SCRIPT)
assert SPEC and SPEC.loader
queue = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(queue)


def config() -> dict:
    return {
        "check_interval_hours": 24,
        "eligible_categories": ["bug_or_reliability", "feature_request"],
        "pending_statuses": ["recorded", "being_handled", "merged_waiting_release"],
    }


def pending_record(**overrides: object) -> dict:
    record = {
        "schema_version": 3,
        "timestamp": "2026-08-16T00:00:00Z",
        "workflow_kind": "intake",
        "thread_id": "thread-1",
        "source_message_id": "customer-1",
        "source_language": "en",
        "category": "bug_or_reliability",
        "repository_route": "frontend",
        "issue_ids": [1043],
        "feature_issue_ids": [],
        "pr_ids": [1059],
        "tracking_key": "frontend:1043:thread-1",
        "tracking_status": "merged_waiting_release",
        "next_check_at": "2026-08-17T00:00:00Z",
    }
    record.update(overrides)
    return record


class FollowUpQueueTests(unittest.TestCase):
    def test_due_pending_record_is_extracted_without_body(self) -> None:
        record = pending_record()
        items, notified = queue.queue_items(
            [record], config(), datetime(2026, 8, 18, tzinfo=timezone.utc)
        )
        self.assertEqual(notified, set())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["previous_status"], "merged_waiting_release")
        self.assertTrue(items[0]["prior_audit_record_fingerprint"].startswith("sha256:"))
        self.assertNotIn("body", items[0])

    def test_not_due_record_is_not_extracted(self) -> None:
        record = pending_record(next_check_at="2026-08-19T00:00:00Z")
        items, _ = queue.queue_items(
            [record], config(), datetime(2026, 8, 18, tzinfo=timezone.utc)
        )
        self.assertEqual(items, [])

    def test_multiple_tracking_items_are_queued_independently(self) -> None:
        record = pending_record(
            tracking_key=None,
            tracking_status=None,
            next_check_at=None,
            tracking_items=[
                {
                    "tracking_key": "frontend:issue-1043:thread-1",
                    "kind": "bug",
                    "status": "merged_waiting_release",
                    "next_check_at": "2026-08-17T00:00:00Z",
                    "issue_ids": [1043],
                    "feature_issue_ids": [],
                    "pr_ids": [1059],
                },
                {
                    "tracking_key": "frontend:feature-3490:thread-1",
                    "kind": "feature",
                    "status": "recorded",
                    "next_check_at": "2026-08-17T00:00:00Z",
                    "issue_ids": [],
                    "feature_issue_ids": [3490],
                    "pr_ids": [],
                },
            ],
        )
        items, _ = queue.queue_items(
            [record], config(), datetime(2026, 8, 18, tzinfo=timezone.utc)
        )
        by_kind = {item["kind"]: item for item in items}
        self.assertEqual(set(by_kind), {"bug", "feature"})
        self.assertEqual(by_kind["bug"]["issue_ids"], [1043])
        self.assertEqual(by_kind["feature"]["feature_issue_ids"], [3490])

    def test_resolution_record_suppresses_pending_item_and_tracks_notification(self) -> None:
        pending = pending_record()
        released = pending_record(
            timestamp="2026-08-18T01:00:00Z",
            workflow_kind="resolution_follow_up",
            tracking_status="released",
            notification_key="thread-1:issue-1043:desktop-v2.3.0",
            decision="draft",
            draft_disposition="kept",
        )
        items, notified = queue.queue_items(
            [pending, released], config(), datetime(2026, 8, 18, 2, tzinfo=timezone.utc)
        )
        self.assertEqual(items, [])
        self.assertIn("thread-1:issue-1043:desktop-v2.3.0", notified)

    def test_record_check_rejects_stale_cas_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            policy = Path(tmp) / "policy.json"
            record = pending_record()
            audit.write_text(json.dumps(record) + "\n", encoding="utf-8")
            policy.write_text(
                json.dumps({"schema_version": 3, "follow_up": {"enabled": True, **config()}}),
                encoding="utf-8",
            )
            args = type(
                "Args",
                (),
                {
                    "audit": audit,
                    "tracking_key": record["tracking_key"],
                    "prior_audit_record_fingerprint": "sha256:" + "0" * 64,
                    "status": "merged_waiting_release",
                    "repository_checked_at": "2026-08-18T00:00:00Z",
                    "next_check_at": None,
                    "repository_evidence_id": ["release-check:none"],
                    "run_id": "run-1",
                },
            )()
            with self.assertRaisesRegex(ValueError, "audit record changed"):
                queue.record_check(args, json.loads(policy.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
