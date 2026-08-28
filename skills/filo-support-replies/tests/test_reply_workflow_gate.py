from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reply_workflow_gate.py"
COMPOSE_SCRIPT = ROOT / "scripts" / "compose_email_body.py"
SPEC = importlib.util.spec_from_file_location("reply_workflow_gate", SCRIPT)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
COMPOSE_SPEC = importlib.util.spec_from_file_location("compose_email_body", COMPOSE_SCRIPT)
assert COMPOSE_SPEC and COMPOSE_SPEC.loader
compose = importlib.util.module_from_spec(COMPOSE_SPEC)
COMPOSE_SPEC.loader.exec_module(compose)


def policy(audit_path: str = "/tmp/filo-support-audit.jsonl") -> dict:
    return {
        "schema_version": 3,
        "threading": {
            # Synthetic teammate fixtures use support.example.invalid. Keep
            # the Groups transport (`support@example.invalid`) separate so the
            # canonical delivery tests still prove transport is not staff.
            "staff_domains": ["support.example.invalid"],
            "draft_mode": "threaded_reply",
            "require_reply_message_id": True,
            "include_spam_candidates": True,
            "require_visible_quoted_original": True,
            "require_post_save_body_check": True,
            "skip_if_existing_draft": True,
            "require_existing_draft_review": True,
            "allow_existing_draft_update": True,
            "require_repository_search_evidence": True,
            "drop_invalid_drafts": True,
            "allow_verified_google_groups_delivery_as_canonical": True,
            "require_google_groups_reply_to_original_match": True,
            "review_required_create_draft_when_reply_target_verified": True,
        },
        "bug_tracking": {
            "repository_routes": {
                "frontend": {"directory": "frontend", "repository": "OWNER/FRONTEND_REPO"},
                "server": {"directory": "server", "repository": "OWNER/SERVER_REPO"},
            }
        },
        "feature_tracking": {
            "require_capability_check_before_issue": True,
            "existing_capability_action": "reply_with_instructions",
            "unverified_capability_action": "review_required",
        },
        "follow_up": {
            "enabled": True,
            "pending_statuses": ["recorded", "being_handled", "merged_waiting_release"],
            "require_verified_release_version": True,
        },
        "automation": {"audit_log_path": audit_path},
    }


def guarded_auto_policy() -> dict:
    value = policy()
    value.update(
        {
            "reply_mode": "guarded-auto",
            "automation": {
                "auto_send_categories": [
                    "bug_or_reliability",
                    "product_capability_question",
                ],
                "always_review_categories": ["feature_request"],
            },
        }
    )
    return value


def messages(*items: tuple[str, str, str]) -> list[dict]:
    return [
        {
            "id": message_id,
            "from": sender,
            "date": f"2026-08-17T0{index}:00:00Z",
            "subject": "Sync problem",
            "text": text,
            "is_draft": False,
        }
        for index, (message_id, sender, text) in enumerate(items)
    ]


def manifest(thread_messages: list[dict], canonical: str = "thread-1") -> dict:
    return {
        "run_id": "run-20260817-001",
        "thread": {
            "id": "thread-1",
            "canonical_thread_id": canonical,
            "existing_drafts": [],
            "messages": thread_messages,
        },
    }


def add_existing_draft(data: dict) -> dict:
    saved = {
        "draft_id": "draft-existing-1",
        "message_id": "draft-message-existing-1",
        "thread_id": "thread-1",
        "subject": "Re: Sync problem",
        "body": "Hi Alex,\n\nWe are reviewing this.\n\nFilo Support",
    }
    data["thread"]["existing_drafts"] = [saved]
    return data


def add_existing_draft_review(data: dict, action: str) -> dict:
    saved = data["thread"]["existing_drafts"][0]
    data["existing_draft_review"] = {
        "status": "reviewed",
        "action": action,
        "reviewed_at": "2026-08-19T01:00:00Z",
        "evidence_ids": ["gmail-draft-read:draft-existing-1"],
        "draft_ids": [saved["draft_id"]],
        "draft_fingerprints": [gate.existing_draft_fingerprint(saved)],
    }
    if action == "update":
        data["draft"] = {
            "operation": "update",
            "draft_id": saved["draft_id"],
        }
    return data


def add_repository_search(data: dict) -> dict:
    data["repository_search"] = {
        "checked_at": "2026-08-18T05:00:00Z",
        "issue_query": "in:title,body sync problem",
        "pr_query": "in:title,body sync problem",
        "issue_evidence_ids": ["github-search:issues:OWNER/FRONTEND_REPO:sync-problem"],
        "pr_evidence_ids": ["github-search:prs:OWNER/FRONTEND_REPO:sync-problem"],
    }
    return data


def default_emphasis(reply_body: str) -> str:
    for candidate in (
        "Issue ticket #3448",
        "Feature ticket #1011",
        "Filo Desktop 2.3.0",
        "Settings → Account",
        "account review",
        "Issue 工单 #3448",
    ):
        if candidate in reply_body:
            return candidate
    for paragraph in reply_body.split("\n\n"):
        if paragraph and not paragraph.startswith("Hi ") and paragraph != "Filo Support":
            return paragraph.split(".")[0].strip("。")
    raise AssertionError("reply needs an emphasis phrase")


def set_reply_body(data: dict, reply_body: str, emphasis: str | None = None) -> dict:
    draft = data["draft"]
    source_id = draft["reply_message_id"]
    source = next(message for message in data["thread"]["messages"] if message["id"] == source_id)
    built = compose.build(
        {
            "reply_body": reply_body,
            "emphasis": [emphasis or default_emphasis(reply_body)],
            "quote_header": f"On {source['date']}, {source['from']} wrote:",
            "original_text": source["text"],
        }
    )
    draft.update(
        {
            "reply_body": reply_body,
            "mime_type": built["mime_type"],
            "body": built["body_html"],
            "body_plain": built["body_plain"],
            "body_html": built["body_html"],
            "emphasis": built["emphasis"],
            "quoted_original_message_id": source_id,
        }
    )
    return data


def with_visible_original(data: dict) -> dict:
    return set_reply_body(data, data["draft"]["body"])


def add_english_draft(data: dict) -> dict:
    add_repository_search(data)
    data.update(
        {
            "decision": "draft",
            "category": "bug_or_reliability",
            "repository_route": "frontend",
            "issue_ids": [3448],
            "pr_ids": [],
            "repository_action_ids": [],
            "follow_up": {
                "items": [
                    {
                        "tracking_key": "frontend:issue-3448:thread-1",
                        "kind": "bug",
                        "status": "being_handled",
                        "next_check_at": "2026-08-18T00:00:00Z",
                        "issue_ids": [3448],
                        "feature_issue_ids": [],
                        "pr_ids": [],
                    }
                ]
            },
            "draft": {
                "thread_id": "thread-1",
                "reply_message_id": "customer-1",
                "subject": "Re: Sync problem",
                "body": "Hi Alex,\n\nThis problem is recorded as Issue ticket #3448 and is being handled.\n\nThanks for the clear report.\nFilo Support",
                "language": "en",
                "from_address": "agent@example.invalid",
                "to": "alex@example.com",
                "cc": "support@example.invalid",
            },
        }
    )
    return with_visible_original(data)


def add_feature_draft(data: dict) -> dict:
    add_repository_search(data)
    data.update(
        {
            "decision": "review-required",
            "category": "feature_request",
            "repository_route": "frontend",
            "capability_checks": [
                {
                    "key": "unread-first",
                    "status": "missing",
                    "repository_route": "frontend",
                    "checked_at": "2026-08-18T00:00:00Z",
                    "evidence_ids": [
                        "repo:OWNER/FRONTEND_REPO@abc123:desktop/src/components/main/mailList"
                    ],
                    "issue_search_evidence_ids": ["github-search:issues:unread-first"],
                    "pr_search_evidence_ids": ["github-search:prs:unread-first"],
                }
            ],
            "feature_issue_ids": [1011],
            "product_review_action_ids": ["label:issue#1011:needs-human-review"],
            "follow_up": {
                "items": [
                    {
                        "tracking_key": "frontend:feature-1011:thread-1",
                        "kind": "feature",
                        "status": "recorded",
                        "next_check_at": "2026-08-18T00:00:00Z",
                        "issue_ids": [],
                        "feature_issue_ids": [1011],
                        "pr_ids": [],
                    }
                ]
            },
            "draft": {
                "thread_id": "thread-1",
                "reply_message_id": "customer-1",
                "subject": "Re: Unread first",
                "body": "Hi Alex,\n\nWe recorded your unread-first request as Feature ticket #1011 and asked the Filo product team to review it.\n\nThanks for the thoughtful suggestion.\nFilo Support",
                "language": "en",
                "from_address": "agent@example.invalid",
                "to": "alex@example.com",
                "cc": "support@example.invalid",
            },
        }
    )
    return with_visible_original(data)


def add_release_follow_up(
    data: dict,
    *,
    reported_version: str = "2.2.4",
    fix_released_version: str = "2.3.0",
    reported_platform: str = "desktop",
    fix_platform: str = "desktop",
    conclusion: str = "update_to_newer_fix",
) -> dict:
    add_repository_search(data)
    customer = gate.customer_messages(data["thread"], policy())[-1]
    if reported_version not in gate.source_product_versions(customer):
        customer["text"] = f"{customer['text']} I am still affected in version {reported_version}."
    data.update(
        {
            "workflow_kind": "resolution_follow_up",
            "decision": "draft",
            "category": "bug_or_reliability",
            "repository_route": "frontend",
            "issue_ids": [1043],
            "pr_ids": [1059],
            "repository_action_ids": [],
            "bug_version_checks": [
                {
                    "key": "sync-problem",
                    "reported_version": reported_version,
                    "reported_platform": reported_platform,
                    "problem_reproduced_on_reported_version": True,
                    "fix_released_version": fix_released_version,
                    "fix_platform": fix_platform,
                    "conclusion": conclusion,
                    "evidence_ids": [
                        "gmail-message:customer-1:reported-version",
                        f"release:{fix_platform}-{fix_released_version}:pr-1059",
                    ],
                }
            ],
            "follow_up": {
                "tracking_key": "frontend:1043:thread-1",
                "previous_status": "merged_waiting_release",
                "status": "released",
                "prior_audit_record_fingerprint": "sha256:" + "a" * 64,
                "repository_checked_at": "2026-08-18T01:00:00Z",
                "released_version": f"Filo Desktop {fix_released_version}",
                "release_evidence_ids": [
                    f"release:{fix_platform}-{fix_released_version}:pr-1059"
                ],
                "notification_key": (
                    f"thread-1:issue-1043:{fix_platform}-{fix_released_version}"
                ),
                "prior_notification_keys": [],
            },
            "draft": {
                "thread_id": "thread-1",
                "reply_message_id": "customer-1",
                "subject": "Re: Sync problem",
                "body": f"Hi Alex,\n\nThe fix tracked in Issue ticket #1043 and PR ticket #1059 has now been released in Filo Desktop {fix_released_version}. Please update and try it again.\n\nThanks again for reporting it.\nFilo Support",
                "language": "en",
                "from_address": "agent@example.invalid",
                "to": "alex@example.com",
                "cc": "support@example.invalid",
            },
        }
    )
    return with_visible_original(data)


def google_groups_message(
    message_id: str = "group-message-1",
    customer: str = "alex@example.com",
    text: str = "I need help moving my account.",
) -> dict:
    return {
        "id": message_id,
        "from": "Alex via Filo Support <support@support.example.invalid>",
        "original_sender": customer,
        "reply_to": customer,
        "list_id": "support.groups.google.com",
        "date": "2026-08-17T01:00:00Z",
        "subject": "Account help",
        "text": text,
        "is_draft": False,
    }


def add_related_staff_reply(
    data: dict,
    *,
    customer_message_id: str = "customer-1",
    customer_rfc_message_id: str = "<customer-1@example.com>",
    staff_date: str = "2026-08-17T02:00:00Z",
    references: list[str] | None = None,
    sender: str = "Connie <teammate@support.example.invalid>",
) -> dict:
    customer = next(
        item for item in data["thread"]["messages"] if item["id"] == customer_message_id
    )
    customer["rfc_message_id"] = customer_rfc_message_id
    data["related_staff_replies"] = [
        {
            "message_id": "staff-sibling-1",
            "thread_id": "thread-sibling-1",
            "from": sender,
            "date": staff_date,
            "in_reply_to": customer_rfc_message_id,
            "references": references or [customer_rfc_message_id],
            "customer_message_id": customer_message_id,
            "is_draft": False,
        }
    ]
    return data


class WorkflowGateTests(unittest.TestCase):
    def test_auto_send_authorization_allows_allowlisted_bug(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
        )
        data["draft"].update({"draft_id": "draft-1", "message_id": "draft-message-1"})
        self.assertEqual(gate.auto_send_errors(data, guarded_auto_policy()), [])

    def test_auto_send_authorization_rejects_review_required_feature(self) -> None:
        data = add_feature_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please add unread first.")))
        )
        data["draft"].update({"draft_id": "draft-1", "message_id": "draft-message-1"})
        errors = gate.auto_send_errors(data, guarded_auto_policy())
        self.assertTrue(any("not on the auto-send allowlist" in error for error in errors))
        self.assertTrue(any("always-review" in error for error in errors))

    def test_auto_send_authorization_rejects_preexisting_draft_update(self) -> None:
        data = add_english_draft(
            add_existing_draft(
                manifest(
                    messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem."))
                )
            )
        )
        data["draft"].update(
            {"draft_id": "draft-1", "message_id": "draft-message-1", "operation": "update"}
        )
        errors = gate.auto_send_errors(data, guarded_auto_policy())
        self.assertTrue(any("pre-existing" in error for error in errors))

    def test_rfc_linked_sibling_staff_reply_stops_before_draft_review(self) -> None:
        data = add_existing_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
        )
        add_related_staff_reply(data)
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "related-thread-replied-by-filo-colleague")
        self.assertEqual(result["related_staff_reply_message_ids"], ["staff-sibling-1"])
        self.assertEqual(result["existing_draft_review_errors"], [])

    def test_unrelated_sibling_reference_does_not_stop(self) -> None:
        data = manifest(
            messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem."))
        )
        add_related_staff_reply(
            data,
            references=["<another-message@example.com>"],
        )
        data["related_staff_replies"][0]["in_reply_to"] = "<another-message@example.com>"
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 0, result)
        self.assertEqual(result["reason"], "unanswered-customer-message")

    def test_groups_transport_is_not_a_sibling_staff_reply(self) -> None:
        data = manifest(
            messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem."))
        )
        add_related_staff_reply(data, sender="Alex via Filo Support <support@example.invalid>")
        data["related_staff_replies"][0].update(
            {
                "original_sender": "alex@example.com",
                "reply_to": "alex@example.com",
                "list_id": "support.groups.google",
            }
        )
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 0, result)
        self.assertEqual(result["reason"], "unanswered-customer-message")

    def test_customer_after_sibling_staff_reply_continues(self) -> None:
        data = manifest(
            messages(
                ("customer-0", "Alex <alex@example.com>", "Please check the sync problem."),
                ("customer-1", "Alex <alex@example.com>", "It still happens in version 2.2.4."),
            )
        )
        add_related_staff_reply(
            data,
            customer_message_id="customer-1",
            staff_date="2026-08-17T00:30:00Z",
        )
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 0, result)
        self.assertEqual(result["reason"], "unanswered-customer-message")

    def test_resolution_follow_up_may_cross_sibling_staff_gate(self) -> None:
        data = add_release_follow_up(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
        )
        add_related_staff_reply(data)
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 0, result)
        self.assertEqual(result["reason"], "verified-resolution-follow-up")

    def test_validate_rejects_draft_after_sibling_staff_reply(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
        )
        add_related_staff_reply(data)
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(
            any("sibling thread" in error for error in result["validation"]["errors"])
        )

    def test_existing_draft_without_review_stops_preflight(self) -> None:
        data = add_existing_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
        )
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "existing-draft-review-required")

    def test_verified_existing_draft_stops_without_duplicate(self) -> None:
        data = add_existing_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
        )
        add_existing_draft_review(data, "skip_verified")
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "existing-draft-verified")

    def test_reviewed_existing_draft_may_be_updated_in_place(self) -> None:
        data = add_existing_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
        )
        add_existing_draft_review(data, "update")
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 0, result)
        self.assertEqual(result["reason"], "existing-draft-reviewed-update")

    def test_existing_draft_update_requires_operation_and_draft_id(self) -> None:
        for missing in ("operation", "draft_id"):
            with self.subTest(missing=missing):
                data = add_existing_draft(
                    manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
                )
                add_existing_draft_review(data, "update")
                data["draft"].pop(missing)
                result, code = gate.preflight(data, policy())
                self.assertEqual(code, 2)
                self.assertEqual(result["reason"], "existing-draft-review-required")

    def test_existing_draft_review_must_match_saved_content_fingerprint(self) -> None:
        data = add_existing_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
        )
        add_existing_draft_review(data, "skip_verified")
        data["thread"]["existing_drafts"][0]["body"] = "A newer draft body"
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "existing-draft-review-required")
        self.assertTrue(any("fingerprints" in error for error in result["existing_draft_review_errors"]))

    def test_existing_draft_fingerprint_command_returns_id_and_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy_path = Path(tmp) / "policy.json"
            manifest_path = Path(tmp) / "manifest.json"
            policy_path.write_text(json.dumps(policy()), encoding="utf-8")
            data = add_existing_draft(
                manifest(messages(("customer-1", "Alex <alex@example.com>", "Please check the sync problem.")))
            )
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "fingerprint-existing-drafts",
                    str(manifest_path),
                    "--policy",
                    str(policy_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            output = json.loads(completed.stdout)
            self.assertEqual(output["existing_drafts"][0]["draft_id"], "draft-existing-1")
            self.assertRegex(output["existing_drafts"][0]["draft_fingerprint"], r"^sha256:[0-9a-f]{64}$")

    def test_record_drop_rejects_deleting_a_pre_existing_draft_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            policy_path = Path(tmp) / "policy.json"
            manifest_path = Path(tmp) / "manifest.json"
            policy_path.write_text(json.dumps(policy(str(audit))), encoding="utf-8")
            data = add_existing_draft(
                manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty.")))
            )
            add_existing_draft_review(data, "update")
            add_english_draft(data)
            data["draft"].update(
                {
                    "operation": "update",
                    "draft_id": "draft-existing-1",
                    "message_id": "draft-message-existing-1",
                    "persisted_mime_type": "multipart/alternative",
                    "persisted_body_html": data["draft"]["body_html"],
                }
            )
            data["drop"] = {
                "confirmed": True,
                "message_id": "draft-message-existing-1",
                "reason": "post-save validation failed",
            }
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "record-drop", str(manifest_path), "--policy", str(policy_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("must not be moved to Trash", completed.stdout)
            self.assertFalse(audit.exists())

    def test_gmail_spam_label_is_still_a_candidate(self) -> None:
        data = manifest(
            messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification."))
        )
        data["thread"]["messages"][0]["label_ids"] = ["SPAM", "CATEGORY_FORUMS", "UNREAD"]
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 0, result)
        self.assertEqual(result["reason"], "unanswered-customer-message")

    def test_partnership_category_stops_as_no_reply_before_draft(self) -> None:
        data = manifest(
            messages(("customer-1", "Alex <alex@example.com>", "We would like to discuss a partnership."))
        )
        data["category"] = "partnership_or_special_terms"
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "category-policy-no-reply")

    def test_partnership_category_rejects_authored_draft(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "We would like to discuss a partnership.")))
        )
        data["category"] = "partnership_or_special_terms"
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("configured as no-reply" in error for error in result["validation"]["errors"]))

    def test_latest_filo_colleague_stops_before_reply(self) -> None:
        data = manifest(
            messages(
                ("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification."),
                ("staff-1", "Connie <teammate@support.example.invalid>", "Thanks, we are looking into it."),
            )
        )
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "latest-message-from-filo-colleague")

    def test_latest_filo_colleague_stops_before_existing_draft_review(self) -> None:
        data = add_existing_draft(
            manifest(
                messages(
                    ("customer-1", "Alex <alex@example.com>", "The inbox is empty."),
                    ("staff-1", "Connie <teammate@support.example.invalid>", "Thanks, we are looking into it."),
                )
            )
        )
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "latest-message-from-filo-colleague")

    def test_customer_after_colleague_continues(self) -> None:
        data = manifest(
            messages(
                ("customer-0", "Alex <alex@example.com>", "The inbox is empty."),
                ("staff-1", "Connie <teammate@support.example.invalid>", "Which version are you using?"),
                ("customer-1", "Alex <alex@example.com>", "I am using iOS 2.2.4 and it still happens."),
            )
        )
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 0)
        self.assertEqual(result["latest_customer_message_id"], "customer-1")

    def test_english_source_chinese_reply_is_rejected(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification.")))
        )
        set_reply_body(
            data,
            "Hi Alex，\n\n这个问题已经记录为 Issue 工单 #3448，目前正在处理。\n\n感谢你的反馈。\nFilo Support",
        )
        data["draft"]["language"] = "zh"
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("does not match source language" in error for error in result["validation"]["errors"]))

    def test_wrong_reply_message_id_is_rejected(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification.")))
        )
        data["draft"]["reply_message_id"] = "staff-1"
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("latest inbound customer message" in error for error in result["validation"]["errors"]))

    def test_thread_ids_without_visible_original_are_rejected(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification.")))
        )
        data["draft"]["body"] = data["draft"]["reply_body"]
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("visibly quote" in error for error in result["validation"]["errors"]))

    def test_google_groups_duplicate_is_rejected(self) -> None:
        data = manifest([google_groups_message()], canonical="direct-thread-9")
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "non-canonical-or-duplicate-thread")

    def test_google_groups_only_delivery_with_verified_customer_continues(self) -> None:
        data = manifest([google_groups_message()])
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 0, result)
        self.assertEqual(result["latest_customer_message_id"], "group-message-1")
        self.assertEqual(result["latest_customer_address"], "alex@example.com")
        self.assertEqual(result["latest_sender_domain"], "example.com")
        self.assertEqual(result["latest_transport_sender_domain"], "support.example.invalid")

    def test_google_groups_delivery_requires_matching_original_sender_and_reply_to(self) -> None:
        message = google_groups_message()
        message["reply_to"] = "different@example.com"
        message["from"] = "Teammate <teammate@support.example.invalid>"
        data = manifest([message])
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "latest-message-from-filo-colleague")

    def test_review_required_group_delivery_must_target_verified_customer(self) -> None:
        data = manifest([google_groups_message()])
        data.update(
            {
                "decision": "review-required",
                "category": "account_access_or_deletion",
                "draft": {
                    "thread_id": "thread-1",
                    "reply_message_id": "group-message-1",
                    "quoted_original_message_id": "group-message-1",
                    "subject": "Re: Account help",
                    "language": "en",
                    "from_address": "agent@example.invalid",
                    "to": "alex@example.com",
                    "cc": "support@example.invalid",
                },
            }
        )
        set_reply_body(
            data,
            "Hi Alex,\n\nThis needs an account review before we can confirm a safe migration path.\n\nThanks for explaining the outcome you need.\nFilo Support",
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 0, result)

        data["draft"]["to"] = "placeholder@example.invalid"
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("verified latest customer address" in error for error in result["validation"]["errors"]))

    def test_internal_terms_are_rejected(self) -> None:
        for term in ("release tag", "hard rebuild", "stale cursor"):
            with self.subTest(term=term):
                data = add_english_draft(
                    manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification.")))
                )
                set_reply_body(data, data["draft"]["reply_body"] + f" Internal detail: {term}.")
                result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
                self.assertEqual(code, 2)
                self.assertTrue(any("internal term" in error for error in result["validation"]["errors"]))

    def test_bare_chinese_issue_and_pr_references_are_rejected(self) -> None:
        data = manifest(messages(("customer-1", "小王 <wang@example.com>", "点击通知以后收件箱是空的，刷新也没有恢复。")))
        data.update(
            {
                "decision": "draft",
                "category": "bug_or_reliability",
                "repository_route": "frontend",
                "issue_ids": [3448],
                "pr_ids": [3460],
                "repository_action_ids": [],
                "follow_up": {
                    "items": [
                        {
                            "tracking_key": "frontend:issue-3448:thread-1",
                            "kind": "bug",
                            "status": "merged_waiting_release",
                            "next_check_at": "2026-08-18T00:00:00Z",
                            "issue_ids": [3448],
                            "feature_issue_ids": [],
                            "pr_ids": [3460],
                        }
                    ]
                },
                "draft": {
                    "thread_id": "thread-1",
                    "reply_message_id": "customer-1",
                    "subject": "Re: Sync problem",
                    "body": "Hi 小王，\n\n这个问题已经记录为 Issue #3448，修复正在 PR #3460 中处理。\n\n感谢你的反馈。\nFilo Support",
                    "language": "zh",
                    "from_address": "agent@example.invalid",
                    "to": "wang@example.com",
                    "cc": "support@example.invalid",
                },
            }
        )
        with_visible_original(data)
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("Issue 工单" in error for error in result["validation"]["errors"]))
        self.assertTrue(any("PR 工单" in error for error in result["validation"]["errors"]))

    def test_valid_chinese_ticket_wording_passes(self) -> None:
        data = manifest(messages(("customer-1", "小王 <wang@example.com>", "点击通知以后收件箱是空的，刷新也没有恢复。")))
        add_repository_search(data)
        data.update(
            {
                "decision": "draft",
                "category": "bug_or_reliability",
                "repository_route": "frontend",
                "issue_ids": [3448],
                "pr_ids": [3460],
                "repository_action_ids": [],
                "follow_up": {
                    "items": [
                        {
                            "tracking_key": "frontend:issue-3448:thread-1",
                            "kind": "bug",
                            "status": "merged_waiting_release",
                            "next_check_at": "2026-08-18T00:00:00Z",
                            "issue_ids": [3448],
                            "feature_issue_ids": [],
                            "pr_ids": [3460],
                        }
                    ]
                },
                "draft": {
                    "thread_id": "thread-1",
                    "reply_message_id": "customer-1",
                    "subject": "Re: Sync problem",
                    "body": "Hi 小王，\n\n这个问题已经记录为 Issue 工单 #3448，修复已合并到 PR 工单 #3460，目前正在等待发布。\n\n感谢你的详细反馈。\nFilo Support",
                    "language": "zh",
                    "from_address": "agent@example.invalid",
                    "to": "wang@example.com",
                    "cc": "support@example.invalid",
                },
            }
        )
        with_visible_original(data)
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 0, result)

    def test_valid_english_ticket_wording_passes(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification.")))
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 0, result)

    def test_simplified_reply_to_traditional_customer_is_rejected(self) -> None:
        data = manifest(
            messages(("customer-1", "小王 <wang@example.com>", "點擊通知以後收件匣是空的，重新整理也沒有恢復。"))
        )
        add_repository_search(data)
        data.update(
            {
                "decision": "draft",
                "category": "bug_or_reliability",
                "repository_route": "frontend",
                "issue_ids": [3448],
                "repository_action_ids": [],
                "follow_up": {
                    "items": [
                        {
                            "tracking_key": "frontend:issue-3448:thread-1",
                            "kind": "bug",
                            "status": "being_handled",
                            "next_check_at": "2026-08-18T00:00:00Z",
                            "issue_ids": [3448],
                            "feature_issue_ids": [],
                            "pr_ids": [],
                        }
                    ]
                },
                "draft": {
                    "thread_id": "thread-1",
                    "reply_message_id": "customer-1",
                    "subject": "Re: Sync problem",
                    "body": "Hi 小王，\n\n这个问题已经收到：点击通知后收件箱是空的。已记录为 Issue 工单 #3448，正在处理。\n\n感谢你的反馈。\nFilo Support",
                    "language": "zh",
                    "from_address": "agent@example.invalid",
                    "to": "wang@example.com",
                    "cc": "support@example.invalid",
                },
            }
        )
        with_visible_original(data)
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(
            any("customer's script" in error for error in result["validation"]["errors"])
        )

    def test_traditional_reply_to_traditional_customer_passes(self) -> None:
        data = manifest(
            messages(("customer-1", "小王 <wang@example.com>", "點擊通知以後收件匣是空的，重新整理也沒有恢復。"))
        )
        add_repository_search(data)
        data.update(
            {
                "decision": "draft",
                "category": "bug_or_reliability",
                "repository_route": "frontend",
                "issue_ids": [3448],
                "repository_action_ids": [],
                "follow_up": {
                    "items": [
                        {
                            "tracking_key": "frontend:issue-3448:thread-1",
                            "kind": "bug",
                            "status": "being_handled",
                            "next_check_at": "2026-08-18T00:00:00Z",
                            "issue_ids": [3448],
                            "feature_issue_ids": [],
                            "pr_ids": [],
                        }
                    ]
                },
                "draft": {
                    "thread_id": "thread-1",
                    "reply_message_id": "customer-1",
                    "subject": "Re: Sync problem",
                    "body": "Hi 小王，\n\n這個問題已經收到：點擊通知後收件匣是空的。已記錄為 Issue 工單 #3448，正在處理。\n\n感謝你的反饋。\nFilo Support",
                    "language": "zh",
                    "from_address": "agent@example.invalid",
                    "to": "wang@example.com",
                    "cc": "support@example.invalid",
                },
            }
        )
        set_reply_body(data, data["draft"]["body"], emphasis="Issue 工單 #3448")
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 0, result)
        self.assertEqual(result.get("source_script"), "hant")
        self.assertEqual(result.get("reply_script"), "hant")

    def test_feature_duplicate_reuse_with_review_action_passes(self) -> None:
        data = add_feature_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please keep unread mail at the top of the inbox.")))
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 0, result)

    def test_feature_requires_product_review_action(self) -> None:
        data = add_feature_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please keep unread mail at the top of the inbox.")))
        )
        data["product_review_action_ids"] = []
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("product-review action" in error for error in result["validation"]["errors"]))

    def test_feature_requires_capability_check(self) -> None:
        data = add_feature_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "Please keep unread mail at the top of the inbox.")))
        )
        data["capability_checks"] = []
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("capability_checks" in error for error in result["validation"]["errors"]))

    def test_existing_capability_cannot_be_filed_as_feature(self) -> None:
        data = add_feature_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "How do I change my primary email?")))
        )
        data["capability_checks"] = [
            {
                "key": "primary-mail-switch",
                "status": "existing",
                "repository_route": "mixed",
                "checked_at": "2026-08-18T05:00:00Z",
                "evidence_ids": ["repo:frontend@abc:settings/account"],
                "customer_guidance": "Settings → Account",
            }
        ]
        set_reply_body(
            data,
            "Hi Alex,\n\nOpen Settings → Account to change the primary email. Feature ticket #1011 was recorded.\n\nFilo Support",
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("existing capability is a how-to" in error for error in result["validation"]["errors"]))

    def test_existing_capability_how_to_passes_without_feature_ticket(self) -> None:
        data = manifest(
            messages(("customer-1", "Alex <alex@example.com>", "How do I change my primary email?"))
        )
        data.update(
            {
                "decision": "draft",
                "category": "product_capability_question",
                "capability_checks": [
                    {
                        "key": "primary-mail-switch",
                        "status": "existing",
                        "repository_route": "mixed",
                        "checked_at": "2026-08-18T05:00:00Z",
                        "evidence_ids": [
                            "repo:OWNER/FRONTEND_REPO@abc:desktop/src/components/settings/account",
                            "repo:OWNER/SERVER_REPO@def:user/primary-mail",
                        ],
                        "issue_search_evidence_ids": ["github-search:issues:primary-mail-switch"],
                        "pr_search_evidence_ids": ["github-search:prs:primary-mail-switch"],
                        "customer_guidance": "Settings → Account",
                    }
                ],
                "draft": {
                    "thread_id": "thread-1",
                    "reply_message_id": "customer-1",
                    "subject": "Re: Primary email",
                    "body": "Hi Alex,\n\nOpen Settings → Account to change the primary email.\n\nFilo Support",
                    "language": "en",
                    "from_address": "agent@example.invalid",
                    "to": "alex@example.com",
                    "cc": "support@example.invalid",
                },
            }
        )
        add_repository_search(data)
        with_visible_original(data)
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 0, result)

    def test_existing_capability_requires_customer_guidance_in_reply(self) -> None:
        data = manifest(
            messages(("customer-1", "Alex <alex@example.com>", "How do I change my primary email?"))
        )
        data.update(
            {
                "decision": "draft",
                "category": "product_capability_question",
                "capability_checks": [
                    {
                        "key": "primary-mail-switch",
                        "status": "existing",
                        "repository_route": "mixed",
                        "checked_at": "2026-08-18T05:00:00Z",
                        "evidence_ids": ["repo:frontend@abc:settings/account"],
                        "issue_search_evidence_ids": ["github-search:issues:primary-mail-switch"],
                        "pr_search_evidence_ids": ["github-search:prs:primary-mail-switch"],
                        "customer_guidance": "Settings → Account",
                    }
                ],
                "draft": {
                    "thread_id": "thread-1",
                    "reply_message_id": "customer-1",
                    "subject": "Re: Primary email",
                    "body": "Hi Alex,\n\nThe option already exists.\n\nFilo Support",
                    "language": "en",
                    "from_address": "agent@example.invalid",
                    "to": "alex@example.com",
                    "cc": "support@example.invalid",
                },
            }
        )
        add_repository_search(data)
        with_visible_original(data)
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("customer guidance" in error for error in result["validation"]["errors"]))

    def test_merged_but_unreleased_cannot_cross_staff_gate(self) -> None:
        data = manifest(
            messages(
                ("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification."),
                ("staff-1", "Connie <teammate@support.example.invalid>", "We recorded this."),
            )
        )
        data["workflow_kind"] = "resolution_follow_up"
        data["follow_up"] = {
            "previous_status": "being_handled",
            "status": "merged_waiting_release",
            "prior_audit_record_fingerprint": "sha256:" + "a" * 64,
            "repository_checked_at": "2026-08-18T01:00:00Z",
            "release_evidence_ids": ["pr:1059:merged"],
            "notification_key": "thread-1:issue-1043:pending",
            "prior_notification_keys": [],
        }
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 2)
        self.assertEqual(result["reason"], "invalid-resolution-follow-up-evidence")

    def test_verified_release_may_cross_staff_gate(self) -> None:
        data = add_release_follow_up(
            manifest(
                messages(
                    ("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification."),
                ("staff-1", "Connie <teammate@support.example.invalid>", "We recorded this."),
                )
            )
        )
        result, code = gate.preflight(data, policy())
        self.assertEqual(code, 0, result)
        self.assertEqual(result["reason"], "verified-resolution-follow-up")
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 0, result)

    def test_customer_on_newer_version_cannot_be_told_old_fix_is_released(self) -> None:
        data = add_release_follow_up(
            manifest(
                messages(
                    (
                        "customer-1",
                        "Alex <alex@example.com>",
                        "The sync problem still happens in Filo Desktop 2.2.6.",
                    )
                )
            ),
            reported_version="2.2.6",
            fix_released_version="2.2.4",
            conclusion="regression_or_fix_not_effective",
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(
            any(
                "same or newer version" in error
                or "same-platform fix version newer" in error
                for error in result["validation"]["errors"]
            ),
            result,
        )

    def test_customer_on_older_version_may_be_sent_to_newer_same_platform_fix(self) -> None:
        data = add_release_follow_up(
            manifest(
                messages(
                    (
                        "customer-1",
                        "Alex <alex@example.com>",
                        "The sync problem still happens in Filo Desktop 2.2.4.",
                    )
                )
            ),
            reported_version="2.2.4",
            fix_released_version="2.3.0",
            conclusion="update_to_newer_fix",
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 0, result)

    def test_other_platform_release_cannot_prove_customer_bug_is_fixed(self) -> None:
        data = add_release_follow_up(
            manifest(
                messages(
                    (
                        "customer-1",
                        "Alex <alex@example.com>",
                        "The sync problem still happens in Filo Desktop 2.2.6.",
                    )
                )
            ),
            reported_version="2.2.6",
            fix_released_version="2.2.4",
            reported_platform="desktop",
            fix_platform="ios",
            conclusion="different_platform",
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(
            any("same-platform fix version newer" in error for error in result["validation"]["errors"]),
            result,
        )

    def test_newer_version_reproduction_passes_after_verified_issue_update(self) -> None:
        data = add_english_draft(
            manifest(
                messages(
                    (
                        "customer-1",
                        "Alex <alex@example.com>",
                        "The sync problem still happens in Filo Desktop 2.2.6.",
                    )
                )
            )
        )
        data["repository_action_ids"] = ["github-comment:issue-3448:2.2.6-reproduction"]
        data["bug_version_checks"] = [
            {
                "key": "sync-problem",
                "reported_version": "2.2.6",
                "reported_platform": "desktop",
                "problem_reproduced_on_reported_version": True,
                "fix_released_version": "2.2.4",
                "fix_platform": "desktop",
                "conclusion": "regression_or_fix_not_effective",
                "evidence_ids": [
                    "gmail-message:customer-1:reported-version",
                    "release:desktop-2.2.4:pr-3400",
                    "github-comment:issue-3448:2.2.6-reproduction",
                ],
            }
        ]
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 0, result)
        record = gate.audit_record(data, policy(), result)
        self.assertEqual(
            record["bug_version_checks"][0]["conclusion"],
            "regression_or_fix_not_effective",
        )
        self.assertTrue(record["bug_version_evidence_fingerprint"].startswith("sha256:"))
        self.assertNotIn("The sync problem still happens", json.dumps(record))

    def test_customer_reported_version_requires_bug_version_check(self) -> None:
        data = add_english_draft(
            manifest(
                messages(
                    (
                        "customer-1",
                        "Alex <alex@example.com>",
                        "The sync problem still happens in Filo Desktop 2.2.6.",
                    )
                )
            )
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(
            any("bug_version_checks must compare" in error for error in result["validation"]["errors"]),
            result,
        )

    def test_duplicate_release_notification_is_rejected(self) -> None:
        data = add_release_follow_up(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification.")))
        )
        data["follow_up"]["prior_notification_keys"] = [data["follow_up"]["notification_key"]]
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("already been drafted" in error for error in result["validation"]["errors"]))

    def test_finalize_appends_ids_and_fingerprints_without_customer_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            policy_path = Path(tmp) / "policy.json"
            manifest_path = Path(tmp) / "manifest.json"
            database_path = Path(tmp) / "intake.sqlite"
            policy_path.write_text(
                json.dumps(
                    {
                        **policy(str(audit)),
                        "automation": {
                            "audit_log_path": str(audit),
                            "intake_database_path": str(database_path),
                        },
                    }
                ),
                encoding="utf-8",
            )

            data = add_english_draft(
                manifest(messages(("customer-1", "Alex <alex@example.com>", "SECRET-CUSTOMER-BODY: the inbox is empty.")))
            )
            data["draft"].update(
                {
                    "draft_id": "draft-9",
                    "message_id": "draft-message-9",
                    "persisted_mime_type": "multipart/alternative",
                    "persisted_body": data["draft"]["body_html"],
                    "persisted_body_html": data["draft"]["body_html"],
                }
            )
            manifest_path.write_text(json.dumps(data), encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "finalize", str(manifest_path), "--policy", str(policy_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            output = json.loads(completed.stdout)
            self.assertEqual(output["intake_database"]["source_type"], "email")
            record = json.loads(audit.read_text(encoding="utf-8"))
            db_spec = importlib.util.spec_from_file_location("intake_db", ROOT / "scripts" / "intake_db.py")
            assert db_spec and db_spec.loader
            intake_db = importlib.util.module_from_spec(db_spec)
            sys.modules[db_spec.name] = intake_db
            db_spec.loader.exec_module(intake_db)
            db = intake_db.connect(database_path)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM source_messages").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM engagement_events").fetchone()[0], 1)
            db.close()

            rerun = subprocess.run(
                [sys.executable, str(SCRIPT), "finalize", str(manifest_path), "--policy", str(policy_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
            db = intake_db.connect(database_path)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM source_messages").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM engagement_events").fetchone()[0], 1)
            db.close()
            self.assertEqual(record["thread_id"], "thread-1")
            self.assertEqual(record["draft_id"], "draft-9")
            self.assertEqual(record["draft_message_id"], "draft-message-9")
            self.assertEqual(record["reply_message_id"], "customer-1")
            self.assertEqual(record["quoted_original_message_id"], "customer-1")
            self.assertTrue(record["quoted_original_verified"])
            self.assertTrue(record["thread_fingerprint"].startswith("sha256:"))
            self.assertTrue(record["source_message_fingerprint"].startswith("sha256:"))
            self.assertTrue(record["draft_fingerprint"].startswith("sha256:"))
            self.assertNotIn("SECRET-CUSTOMER-BODY", audit.read_text(encoding="utf-8"))

    def test_finalize_rejects_saved_draft_that_lost_original(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification.")))
        )
        data["draft"].update(
            {
                "draft_id": "draft-9",
                "message_id": "draft-message-9",
                "persisted_mime_type": "multipart/alternative",
                "persisted_body": data["draft"]["reply_body"],
                "persisted_body_html": "<p>Saved reply without quote</p>",
            }
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=True)
        self.assertEqual(code, 2)
        self.assertFalse(result["quoted_original_verified"])
        self.assertTrue(any("saved Gmail draft" in error for error in result["validation"]["errors"]))

    def test_plaintext_only_draft_is_rejected(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification.")))
        )
        data["draft"].update(
            {
                "mime_type": "text/plain",
                "body": data["draft"]["body_plain"],
                "body_html": "",
            }
        )
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        self.assertTrue(any("multipart/alternative" in error for error in result["validation"]["errors"]))

    def test_html_requires_strong_and_blockquote(self) -> None:
        data = add_english_draft(
            manifest(messages(("customer-1", "Alex <alex@example.com>", "The inbox is empty after tapping a notification.")))
        )
        data["draft"]["body_html"] = "<p>Hi Alex, this is an unformatted reply.</p>"
        data["draft"]["body"] = data["draft"]["body_html"]
        result, code = gate.validate_manifest(data, policy(), require_persisted_draft=False)
        self.assertEqual(code, 2)
        errors = result["validation"]["errors"]
        self.assertTrue(any("blockquote" in error for error in errors))
        self.assertTrue(any("<strong>" in error for error in errors))


class ValidateScanTests(unittest.TestCase):
    def load_intake_db(self):
        spec = importlib.util.spec_from_file_location("intake_db_scan", ROOT / "scripts" / "intake_db.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def scan_policy(self, database: Path) -> dict:
        return {
            **policy(),
            "automation": {
                "audit_log_path": "/tmp/filo-support-audit.jsonl",
                "intake_database_path": str(database),
            },
        }

    def valid_scan(self, database: Path) -> dict:
        intake_db = self.load_intake_db()
        cursor = intake_db.cursor(intake_db.init_db(database))
        return {
            "run_id": "run-scan-1",
            "window": {
                "start_epoch": cursor["window_start_epoch"],
                "end_epoch": cursor["window_end_epoch"],
            },
            "cursor_evidence": cursor,
            "searches": [
                {"location": "inbox", "query": cursor["gmail_queries"]["inbox"], "result_count": 0},
                {"location": "spam", "query": cursor["gmail_queries"]["spam"], "result_count": 1},
            ],
            "candidates": [
                {"message_id": "spam-message-1", "disposition": "new"},
                {
                    "message_id": "spam-message-2",
                    "disposition": "skipped-already-indexed",
                    "exact_match": {"external_message_id": "spam-message-2", "source_type": "email"},
                },
            ],
        }

    def test_valid_scan_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            result, code = gate.validate_scan(self.valid_scan(database), self.scan_policy(database))
            self.assertEqual(code, 0, result["validation"]["errors"])
            self.assertTrue(result["validation"]["passed"])
            self.assertEqual(result["candidate_count"], 2)

    def test_date_based_window_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            scan = self.valid_scan(database)
            scan["searches"][0]["query"] = "to:support@example.invalid after:2026/08/19 before:2026/08/21 in:inbox"
            result, code = gate.validate_scan(scan, self.scan_policy(database))
            self.assertEqual(code, 2)
            self.assertTrue(any("date-based" in error for error in result["validation"]["errors"]))

    def test_missing_spam_search_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            scan = self.valid_scan(database)
            scan["searches"] = [scan["searches"][0]]
            result, code = gate.validate_scan(scan, self.scan_policy(database))
            self.assertEqual(code, 2)
            self.assertTrue(any("missing the required spam" in error for error in result["validation"]["errors"]))

    def test_window_starting_after_cursor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            scan = self.valid_scan(database)
            late_start = scan["window"]["end_epoch"] - 60
            scan["window"]["start_epoch"] = late_start
            result, code = gate.validate_scan(scan, self.scan_policy(database))
            self.assertEqual(code, 2)
            self.assertTrue(
                any("later than the deterministic cursor" in error for error in result["validation"]["errors"])
            )

    def test_skip_without_exact_match_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            scan = self.valid_scan(database)
            scan["candidates"][1].pop("exact_match")
            result, code = gate.validate_scan(scan, self.scan_policy(database))
            self.assertEqual(code, 2)
            self.assertTrue(
                any("without exact_match evidence" in error for error in result["validation"]["errors"])
            )

    def test_query_dropping_a_channel_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            scan = self.valid_scan(database)
            scan["searches"][0]["query"] = scan["searches"][0]["query"].replace(
                " OR from:feedback@example.invalid", ""
            )
            result, code = gate.validate_scan(scan, self.scan_policy(database))
            self.assertEqual(code, 2)
            self.assertTrue(any("verbatim" in error for error in result["validation"]["errors"]))

    def test_triage_indexed_match_cannot_skip_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            scan = self.valid_scan(database)
            scan["candidates"][1]["exact_match"]["source_type"] = "gmail"
            result, code = gate.validate_scan(scan, self.scan_policy(database))
            self.assertEqual(code, 2)
            self.assertTrue(
                any("support-audit match" in error for error in result["validation"]["errors"])
            )

    def test_recorded_scan_must_match_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "intake.sqlite"
            scan = self.valid_scan(database)
            scan["recorded_scan"] = {
                "run_id": "run-scan-1",
                "window_start_epoch": scan["window"]["start_epoch"] + 5,
                "window_end_epoch": scan["window"]["end_epoch"],
            }
            result, code = gate.validate_scan(scan, self.scan_policy(database))
            self.assertEqual(code, 2)
            self.assertTrue(
                any("recorded_scan.window_start_epoch" in error for error in result["validation"]["errors"])
            )


if __name__ == "__main__":
    unittest.main()
