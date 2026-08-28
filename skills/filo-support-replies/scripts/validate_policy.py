#!/usr/bin/env python3
"""Validate a local Filo support policy file without external dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


PLACEHOLDER = re.compile(r"REPLACE_|CHANGEME|TODO", re.IGNORECASE)
EMAIL_ADDRESS = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ALLOWED_MODES = {"draft", "guarded-auto"}


def parse_json(raw: str, source: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON from {source} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise ValueError("top-level value must be an object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    if str(path) == "-":
        return parse_json(sys.stdin.read(), "stdin")
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    return parse_json(raw, str(path))


def nested(data: dict[str, Any], *keys: str) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path, help="JSON file, or - for stdin")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = load_json(args.policy)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    if data.get("schema_version") != 3:
        errors.append("schema_version must be 3")

    mode = data.get("reply_mode")
    if mode not in ALLOWED_MODES:
        errors.append(f"reply_mode must be one of {sorted(ALLOWED_MODES)}")

    required_strings = {
        "product": data.get("product"),
        "policy_review.reviewed_at": nested(data, "policy_review", "reviewed_at"),
        "policy_review.reviewed_by": nested(data, "policy_review", "reviewed_by"),
        "policy_review.source_of_truth": nested(data, "policy_review", "source_of_truth"),
        "sender.team_name": nested(data, "sender", "team_name"),
        "sender.mailbox_account": nested(data, "sender", "mailbox_account"),
        "sender.from_address": nested(data, "sender", "from_address"),
    }
    for label, value in required_strings.items():
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} must be a non-empty string")
        elif PLACEHOLDER.search(value):
            errors.append(f"{label} still contains a placeholder")

    for label in ("sender.mailbox_account", "sender.from_address"):
        value = nested(data, *label.split("."))
        if isinstance(value, str) and value.strip() and not PLACEHOLDER.search(value):
            if not EMAIL_ADDRESS.fullmatch(value.strip()):
                errors.append(f"{label} must be a valid email address")

    cc_addresses = nested(data, "sender", "cc_addresses")
    if not isinstance(cc_addresses, list) or not cc_addresses:
        errors.append("sender.cc_addresses must be a non-empty email address array")
    elif not all(isinstance(item, str) and EMAIL_ADDRESS.fullmatch(item.strip()) and not PLACEHOLDER.search(item) for item in cc_addresses):
        errors.append("sender.cc_addresses must contain only valid email addresses without placeholders")
    elif len({item.strip().lower() for item in cc_addresses}) != len(cc_addresses):
        errors.append("sender.cc_addresses must not contain duplicates")

    threading = data.get("threading")
    if not isinstance(threading, dict):
        errors.append("threading must be an object")
    else:
        staff_domains = threading.get("staff_domains")
        if not isinstance(staff_domains, list) or not staff_domains or not all(
            isinstance(item, str) and item.strip() and "@" not in item for item in staff_domains
        ):
            errors.append("threading.staff_domains must be a non-empty domain string array")
        if threading.get("draft_mode") != "threaded_reply":
            errors.append("threading.draft_mode must be threaded_reply")
        for field in (
            "require_reply_message_id",
            "include_spam_candidates",
            "require_visible_quoted_original",
            "require_post_save_body_check",
            "skip_if_existing_draft",
            "require_existing_draft_review",
            "allow_existing_draft_update",
            "require_repository_search_evidence",
            "drop_invalid_drafts",
            "allow_verified_google_groups_delivery_as_canonical",
            "require_google_groups_reply_to_original_match",
            "review_required_create_draft_when_reply_target_verified",
        ):
            if threading.get(field) is not True:
                errors.append(f"threading.{field} must be true")

    bug_tracking = data.get("bug_tracking")
    if not isinstance(bug_tracking, dict):
        errors.append("bug_tracking must be an object")
    else:
        if bug_tracking.get("enabled") is not True:
            errors.append("bug_tracking.enabled must be true")

        canonical_repo = bug_tracking.get("canonical_repo")
        if not isinstance(canonical_repo, str) or not GITHUB_REPOSITORY.fullmatch(canonical_repo.strip()) or PLACEHOLDER.search(canonical_repo):
            errors.append("bug_tracking.canonical_repo must be a non-placeholder owner/repository value")

        related_repos = bug_tracking.get("related_repos")
        if not isinstance(related_repos, list) or not all(
            isinstance(item, str) and GITHUB_REPOSITORY.fullmatch(item.strip()) and not PLACEHOLDER.search(item)
            for item in related_repos
        ):
            errors.append("bug_tracking.related_repos must be an owner/repository string array")

        repository_routes = bug_tracking.get("repository_routes")
        if not isinstance(repository_routes, dict):
            errors.append("bug_tracking.repository_routes must be an object")
        else:
            for route_name in ("frontend", "server"):
                route = repository_routes.get(route_name)
                if not isinstance(route, dict):
                    errors.append(f"bug_tracking.repository_routes.{route_name} must be an object")
                    continue
                if route.get("directory") != route_name:
                    errors.append(
                        f"bug_tracking.repository_routes.{route_name}.directory must be {route_name}"
                    )
                repository = route.get("repository")
                if (
                    not isinstance(repository, str)
                    or not GITHUB_REPOSITORY.fullmatch(repository.strip())
                    or PLACEHOLDER.search(repository)
                ):
                    errors.append(
                        f"bug_tracking.repository_routes.{route_name}.repository must be a non-placeholder owner/repository value"
                    )

        if bug_tracking.get("include_repository_links_in_customer_reply") is not False:
            errors.append("bug_tracking.include_repository_links_in_customer_reply must be false")

        github_writes = bug_tracking.get("github_writes")
        required_write_flags = {
            "create_issue": True,
            "comment_existing_issue": True,
            "update_issue_labels": True,
            "close_or_reopen_issue": False,
            "modify_pull_request": False,
        }
        if not isinstance(github_writes, dict):
            errors.append("bug_tracking.github_writes must be an object")
        else:
            for field, expected in required_write_flags.items():
                if github_writes.get(field) is not expected:
                    errors.append(f"bug_tracking.github_writes.{field} must be {str(expected).lower()}")

        allowed_labels = bug_tracking.get("allowed_issue_labels")
        if not isinstance(allowed_labels, dict):
            errors.append("bug_tracking.allowed_issue_labels must be an object")
        else:
            for field in ("types", "clients"):
                labels = allowed_labels.get(field)
                if not isinstance(labels, list) or not all(isinstance(item, str) and item.strip() for item in labels):
                    errors.append(f"bug_tracking.allowed_issue_labels.{field} must be a string array")

    feature_tracking = data.get("feature_tracking")
    if not isinstance(feature_tracking, dict):
        errors.append("feature_tracking must be an object")
    else:
        if feature_tracking.get("enabled") is not True:
            errors.append("feature_tracking.enabled must be true")
        if feature_tracking.get("repository_route") not in {"frontend", "server"}:
            errors.append("feature_tracking.repository_route must be frontend or server")
        if feature_tracking.get("require_capability_check_before_issue") is not True:
            errors.append("feature_tracking.require_capability_check_before_issue must be true")
        if feature_tracking.get("existing_capability_action") != "reply_with_instructions":
            errors.append(
                "feature_tracking.existing_capability_action must be reply_with_instructions"
            )
        if feature_tracking.get("unverified_capability_action") != "review_required":
            errors.append(
                "feature_tracking.unverified_capability_action must be review_required"
            )
        labels = feature_tracking.get("required_labels")
        if not isinstance(labels, list) or not labels or not all(
            isinstance(item, str) and item.strip() for item in labels
        ):
            errors.append("feature_tracking.required_labels must be a non-empty string array")
        else:
            required_labels = {
                "类型：新需求",
                "triage:feature",
                "status:needs-product-scope",
                "needs-human-review",
            }
            missing_labels = required_labels - set(labels)
            if missing_labels:
                errors.append(f"feature_tracking.required_labels is missing: {sorted(missing_labels)}")
        if feature_tracking.get("product_review_label") != "needs-human-review":
            errors.append("feature_tracking.product_review_label must be needs-human-review")
        for field in ("create_missing_issue", "reuse_matching_issue", "route_to_product_review"):
            if feature_tracking.get(field) is not True:
                errors.append(f"feature_tracking.{field} must be true")

    follow_up = data.get("follow_up")
    if not isinstance(follow_up, dict):
        errors.append("follow_up must be an object")
    else:
        if follow_up.get("enabled") is not True:
            errors.append("follow_up.enabled must be true")
        interval = follow_up.get("check_interval_hours")
        if not isinstance(interval, int) or interval <= 0:
            errors.append("follow_up.check_interval_hours must be a positive integer")
        eligible = follow_up.get("eligible_categories")
        required_eligible = {"bug_or_reliability", "feature_request"}
        if not isinstance(eligible, list) or not required_eligible.issubset(set(eligible)):
            errors.append("follow_up.eligible_categories must include bug_or_reliability and feature_request")
        pending_statuses = follow_up.get("pending_statuses")
        required_pending = {"recorded", "being_handled", "merged_waiting_release"}
        if not isinstance(pending_statuses, list) or not required_pending.issubset(set(pending_statuses)):
            errors.append(
                "follow_up.pending_statuses must include recorded, being_handled, and merged_waiting_release"
            )
        for field in (
            "require_verified_release_version",
            "allow_latest_staff_sender_exception_for_resolution_follow_up",
            "deduplicate_release_notifications",
        ):
            if follow_up.get(field) is not True:
                errors.append(f"follow_up.{field} must be true")
        if not isinstance(follow_up.get("draft_only"), bool):
            errors.append("follow_up.draft_only must be boolean")
        elif mode == "draft" and follow_up.get("draft_only") is not True:
            errors.append("follow_up.draft_only must be true in draft mode")

    facts = nested(
        data,
        "current_policy",
        "free_ai_transition",
        "facts_to_reverify_before_live_use",
    )
    if not isinstance(facts, list) or not facts or not all(isinstance(item, str) and item.strip() for item in facts):
        errors.append("current_policy.free_ai_transition.facts_to_reverify_before_live_use must be a non-empty string array")

    review_date_raw = nested(data, "policy_review", "reviewed_at")
    stale_after = nested(data, "policy_review", "stale_after_days")
    if isinstance(review_date_raw, str):
        try:
            review_date = datetime.strptime(review_date_raw, "%Y-%m-%d").date()
            if review_date > date.today():
                errors.append("policy_review.reviewed_at cannot be in the future")
            if isinstance(stale_after, int) and stale_after > 0:
                age = (date.today() - review_date).days
                if age > stale_after:
                    warnings.append(f"policy review is {age} days old; configured stale threshold is {stale_after} days")
        except ValueError:
            errors.append("policy_review.reviewed_at must use YYYY-MM-DD")
    if not isinstance(stale_after, int) or stale_after <= 0:
        errors.append("policy_review.stale_after_days must be a positive integer")

    auto_categories = nested(data, "automation", "auto_send_categories")
    always_review = nested(data, "automation", "always_review_categories")
    no_reply_categories = nested(data, "automation", "no_reply_categories")
    if not isinstance(auto_categories, list) or not all(isinstance(item, str) for item in auto_categories):
        errors.append("automation.auto_send_categories must be a string array")
    if not isinstance(always_review, list) or not always_review or not all(isinstance(item, str) for item in always_review):
        errors.append("automation.always_review_categories must be a non-empty string array")
    else:
        required_human_categories = {
            "product_plan_or_new_feature",
            "feature_request",
            "pricing_or_paid_operation",
        }
        missing_human_categories = required_human_categories - set(always_review)
        if missing_human_categories:
            errors.append(
                "automation.always_review_categories is missing required human-decision categories: "
                f"{sorted(missing_human_categories)}"
            )
    if no_reply_categories is not None and (
        not isinstance(no_reply_categories, list)
        or not all(isinstance(item, str) and item.strip() for item in no_reply_categories)
    ):
        errors.append("automation.no_reply_categories must be a string array when present")

    audit_log_path = nested(data, "automation", "audit_log_path")
    if not isinstance(audit_log_path, str) or not audit_log_path.strip():
        errors.append("automation.audit_log_path must be a non-empty path in every mode")
    elif PLACEHOLDER.search(audit_log_path):
        errors.append("automation.audit_log_path still contains a placeholder")
    elif not Path(audit_log_path).is_absolute():
        errors.append("automation.audit_log_path must be absolute")
    intake_database_path = nested(data, "automation", "intake_database_path")
    if intake_database_path is not None:
        if not isinstance(intake_database_path, str) or not intake_database_path.strip():
            errors.append("automation.intake_database_path must be a non-empty absolute path when present")
        elif PLACEHOLDER.search(intake_database_path):
            errors.append("automation.intake_database_path still contains a placeholder")
        elif not Path(intake_database_path).is_absolute():
            errors.append("automation.intake_database_path must be absolute")
    if nested(data, "automation", "audit_schema_version") != 3:
        errors.append("automation.audit_schema_version must be 3")
    if nested(data, "automation", "require_fingerprints") is not True:
        errors.append("automation.require_fingerprints must be true")

    if mode == "guarded-auto":
        for field in ("approved_by", "approved_at"):
            value = nested(data, "automation", field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"automation.{field} is required in guarded-auto mode")
        if not auto_categories:
            errors.append("guarded-auto mode requires at least one auto_send_category")
        overlap = set(auto_categories or []) & set(always_review or [])
        if overlap:
            errors.append(f"categories cannot be both auto-send and always-review: {sorted(overlap)}")
        no_reply = set(no_reply_categories or []) if isinstance(no_reply_categories, list) else set()
        overlap = (set(auto_categories or []) | set(always_review or [])) & no_reply
        if overlap:
            errors.append(f"categories cannot be both reply and no-reply: {sorted(overlap)}")

    for warning in warnings:
        print(f"[WARN] {warning}")
    for error in errors:
        print(f"[ERROR] {error}")

    if errors:
        return 1
    print(f"[OK] policy is structurally valid for {mode} mode: {args.policy}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
