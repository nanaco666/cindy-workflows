from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "intake_db.py"
SPEC = importlib.util.spec_from_file_location("intake_db", SCRIPT)
assert SPEC and SPEC.loader
intake_db = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = intake_db
SPEC.loader.exec_module(intake_db)


class IntakeDatabaseTests(unittest.TestCase):
    def test_support_record_is_idempotent_and_scores_sender(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            db = intake_db.init_db(database)
            record = {
                "workflow_kind": "intake",
                "timestamp": "2026-08-19T01:00:00Z",
                "source_message_id": "gmail-1",
                "thread_id": "thread-1",
                "source_message_fingerprint": "sha256:source-1",
                "category": "bug_or_reliability",
                "tracking_status": "being_handled",
                "repository_route": "frontend",
                "issue_ids": [1007],
                "pr_ids": [1011],
                "sender_name": "Alex",
                "sender_email": "alex@example.com",
            }
            first = intake_db.import_support_record(db, record)
            second = intake_db.import_support_record(db, record)
            self.assertEqual(first["feedback_id"], second["feedback_id"])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM source_messages").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM engagement_events").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT points FROM person_engagement").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT level FROM person_levels").fetchone()[0], "observer")
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM feedback_tickets ft JOIN tickets t ON t.ticket_id=ft.ticket_id "
                    "WHERE t.repository='OWNER/FRONTEND_REPO' AND t.number IN (1007,1011)"
                ).fetchone()[0],
                2,
            )

    def test_feedback_decision_import_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "reportedDecisionFingerprints": {
                            "decision-1": {
                                "decision": "create",
                                "reason": "Windows notifications are missing",
                                "sourceMessageId": "gmail-2",
                                "observedAt": "2026-08-19T02:00:00Z",
                                "issue": "OWNER/FRONTEND_REPO#1009",
                                "senderName": "Blake",
                                "senderEmail": "blake@example.com",
                                "engagementPoints": 1,
                            }
                        }
                    },
                ),
                encoding="utf-8",
            )
            db = intake_db.init_db(database)
            first = intake_db.import_feedback_state(db, state_path)
            second = intake_db.import_feedback_state(db, state_path)
            self.assertEqual(first["imported"], 1)
            self.assertEqual(second["imported"], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM source_messages").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM engagement_events").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT points FROM person_engagement").fetchone()[0], 1)

    def test_feedback_decision_prefers_real_array_source_id_and_ticket_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "reportedDecisionFingerprints": {
                            "decision-array": {
                                "decision": "await-release",
                                "reason": "Body rendering is fixed but unreleased",
                                "sourceMessageIds": ["message-real-1", "message-real-2"],
                                "sourceType": "feishu",
                                "observedAt": "2026-08-19T03:00:00Z",
                                "pr": "OWNER/FRONTEND_REPO#1008",
                                "releaseStatus": "merged-unreleased",
                            }
                        }
                    },
                ),
                encoding="utf-8",
            )
            db = intake_db.init_db(database)
            result = intake_db.import_feedback_state(db, state_path)
            self.assertEqual(result["imported"], 1)
            self.assertEqual(
                tuple(
                    db.execute(
                        "SELECT external_message_id, source_type FROM source_messages"
                    ).fetchone()
                ),
                ("message-real-1", "feishu"),
            )
            self.assertEqual(
                db.execute(
                    "SELECT state FROM tickets WHERE kind='pr' AND number=1008"
                ).fetchone()[0],
                "merged_waiting_release",
            )

    def test_invalid_records_do_not_create_partial_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = intake_db.init_db(Path(tmp) / "intake.sqlite")
            with self.assertRaisesRegex(ValueError, "source_message_id"):
                intake_db.ingest(db, {"content_fingerprint": "sha256:x", "reason": "missing id"})
            self.assertEqual(db.execute("SELECT COUNT(*) FROM feedback_items").fetchone()[0], 0)

    def test_lookup_returns_exact_and_similar_matches_with_tickets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            db = intake_db.init_db(database)
            first = intake_db.ingest(
                db,
                {
                    "source_type": "gmail",
                    "source_message_id": "message-old",
                    "thread_id": "thread-old",
                    "content_fingerprint": "sha256:old",
                    "problem_summary": "Gmail transport_error stops new mail",
                    "reason": "Gmail transport_error stops new mail",
                    "occurred_at": "2026-08-18T00:00:00Z",
                    "issue": "OWNER/FRONTEND_REPO#1021",
                    "engagement_points": 1,
                },
            )
            exact = intake_db.lookup(db, "message-old", source_type="gmail")
            similar = intake_db.lookup(db, "transport_error", source_type="gmail")
            self.assertEqual(exact["exact_source_matches"][0]["feedback_id"], first["feedback_id"])
            self.assertTrue(similar["similar_matches"])
            self.assertEqual(similar["tickets"][0]["number"], 1021)
            self.assertEqual(
                similar["decision_guidance"],
                "advisory_only_verify_against_authoritative_state",
            )

    def test_lookup_treats_email_and_gmail_as_one_source_pool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = intake_db.init_db(Path(tmp) / "intake.sqlite")
            intake_db.ingest(
                db,
                {
                    "source_type": "email",
                    "source_message_id": "audit-message",
                    "content_fingerprint": "sha256:audit",
                    "problem_summary": "summary generation fails on Windows",
                },
            )
            intake_db.ingest(
                db,
                {
                    "source_type": "gmail",
                    "source_message_id": "feedback-message",
                    "content_fingerprint": "sha256:feedback",
                    "problem_summary": "opening mail takes seconds",
                },
            )
            from_email_pool = intake_db.lookup(db, "feedback-message", source_type="email")
            from_gmail_pool = intake_db.lookup(db, "audit-message", source_type="gmail")
            self.assertEqual(len(from_email_pool["exact_source_matches"]), 1)
            self.assertEqual(len(from_gmail_pool["exact_source_matches"]), 1)

    def test_cursor_and_record_scan_advance_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = intake_db.init_db(Path(tmp) / "intake.sqlite")

            bootstrapped = intake_db.cursor(db)
            self.assertEqual(bootstrapped["anchor"]["source"], "bootstrap")
            self.assertGreater(
                bootstrapped["window_end_epoch"] - bootstrapped["window_start_epoch"],
                60 * 60 * 24,
            )
            self.assertEqual(
                bootstrapped["channels"],
                ["to:support@example.invalid", "from:feedback@example.invalid"],
            )
            for location, query in bootstrapped["gmail_queries"].items():
                self.assertIn("to:support@example.invalid OR from:feedback@example.invalid", query)
                self.assertIn("after:", query)
                self.assertIn(f"in:{location}", query)
            with self.assertRaisesRegex(ValueError, "scan channel"):
                intake_db.cursor(db, channels=["  "])

            intake_db.ingest(
                db,
                {
                    "source_type": "email",
                    "source_message_id": "message-1",
                    "content_fingerprint": "sha256:cursor",
                    "problem_summary": "summary generation fails",
                    "timestamp": "2026-08-19T09:14:06Z",
                },
            )
            # Indexer activity (audit import, triage sync) must not advance the
            # scan window: rows can be recorded long after the mail arrived.
            after_ingest = intake_db.cursor(db)
            self.assertEqual(after_ingest["anchor"]["source"], "bootstrap")
            self.assertEqual(
                after_ingest["window_start_epoch"],
                after_ingest["window_end_epoch"] - intake_db.DEFAULT_SCAN_BOOTSTRAP_LOOKBACK_SECONDS,
            )
            fallback = after_ingest

            recorded = intake_db.record_scan(
                db,
                run_id="run-1",
                window_start_epoch=fallback["window_start_epoch"],
                window_end_epoch=fallback["window_end_epoch"],
                inbox_hits=0,
                spam_hits=1,
            )
            self.assertTrue(recorded["recorded"])
            advanced = intake_db.cursor(db)
            self.assertEqual(advanced["anchor"]["source"], "scan_runs")
            self.assertEqual(advanced["anchor"]["run_id"], "run-1")
            self.assertEqual(
                advanced["window_start_epoch"],
                fallback["window_end_epoch"] - intake_db.DEFAULT_SCAN_OVERLAP_SECONDS,
            )

            repeat = intake_db.record_scan(
                db,
                run_id="run-1",
                window_start_epoch=fallback["window_start_epoch"],
                window_end_epoch=fallback["window_end_epoch"],
            )
            self.assertEqual(repeat["scan_runs_total"], 1)

            with self.assertRaisesRegex(ValueError, "run_id"):
                intake_db.record_scan(db, run_id="", window_start_epoch=1, window_end_epoch=2)
            with self.assertRaisesRegex(ValueError, "0 <= start"):
                intake_db.record_scan(db, run_id="run-2", window_start_epoch=9, window_end_epoch=9)


if __name__ == "__main__":
    unittest.main()
