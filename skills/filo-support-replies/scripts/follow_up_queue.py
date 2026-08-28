#!/usr/bin/env python3
"""Build and update the deterministic queue for pending Bug/Feature follow-ups.

This script reads only identifier/status fields from the JSONL audit log. It never
stores or prints customer message bodies. Repository lookups and Gmail drafting stay
with the scheduled Agent; this script enforces interval, CAS, and deduplication rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 3


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def parse_time(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def record_fingerprint(record: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical(record)).hexdigest()


def read_records(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                continue
            if isinstance(value, dict):
                records.append(value)
            else:
                invalid += 1
    return records, invalid


def policy_config(policy: dict[str, Any]) -> dict[str, Any]:
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"policy schema_version must be {SCHEMA_VERSION}")
    config = policy.get("follow_up")
    if not isinstance(config, dict) or config.get("enabled") is not True:
        raise ValueError("follow_up.enabled must be true")
    return config


def ticket_ids(record: dict[str, Any]) -> list[str]:
    values = []
    for field in ("issue_ids", "feature_issue_ids", "pr_ids"):
        raw = record.get(field)
        if isinstance(raw, list):
            values.extend(str(item) for item in raw if str(item).isdigit())
    return sorted(set(values))


def tracking_key(record: dict[str, Any]) -> str:
    explicit = str(record.get("tracking_key") or "").strip()
    if explicit:
        return explicit
    thread = str(record.get("thread_id") or "").strip()
    route = str(record.get("repository_route") or "").strip()
    tickets = ",".join(ticket_ids(record))
    return f"{route}:{tickets}:{thread}" if route and tickets and thread else ""


def expanded_tracking_records(record: dict[str, Any]) -> list[dict[str, Any]]:
    items = record.get("tracking_items")
    if not isinstance(items, list) or not items:
        return [record]
    expanded: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = dict(record)
        value["tracking_key"] = item.get("tracking_key")
        value["tracking_status"] = item.get("status")
        value["next_check_at"] = item.get("next_check_at")
        value["category"] = item.get("category") or record.get("category")
        for field in ("issue_ids", "feature_issue_ids", "pr_ids"):
            value[field] = item.get(field, [])
        value["tracking_kind"] = item.get("kind")
        expanded.append(value)
    return expanded


def queue_items(records: list[dict[str, Any]], config: dict[str, Any], now: datetime) -> tuple[list[dict[str, Any]], set[str]]:
    eligible = set(str(item) for item in config.get("eligible_categories", []) if str(item).strip())
    pending = set(str(item) for item in config.get("pending_statuses", []) if str(item).strip())
    latest: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    notified: set[str] = set()

    for record in records:
        notification_key = str(record.get("notification_key") or "").strip()
        if notification_key and record.get("workflow_kind") == "resolution_follow_up":
            if record.get("draft_disposition") in {"kept", "none"} and record.get("decision") in {"draft", "review-required"}:
                notified.add(notification_key)
        for expanded in expanded_tracking_records(record):
            key = tracking_key(expanded)
            if not key:
                continue
            category = str(expanded.get("category") or "")
            status = str(expanded.get("tracking_status") or "")
            if category not in eligible or status not in pending:
                if expanded.get("workflow_kind") in {"intake", "follow_up_check", "resolution_follow_up"}:
                    latest[key] = (record, expanded)
                continue
            latest[key] = (record, expanded)

    result: list[dict[str, Any]] = []
    for key, pair in latest.items():
        source_record, record = pair
        category = str(record.get("category") or "")
        status = str(record.get("tracking_status") or "")
        if category not in eligible or status not in pending:
            continue
        if not str(record.get("thread_id") or "").strip() or not ticket_ids(record):
            continue
        due = parse_time(record.get("next_check_at"))
        if due is None:
            timestamp = parse_time(record.get("timestamp"))
            if timestamp is None:
                continue
            due = timestamp + timedelta(hours=int(config.get("check_interval_hours", 24)))
        if due > now:
            continue
        result.append(
            {
                "tracking_key": key,
                "prior_audit_record_fingerprint": record_fingerprint(source_record),
                "thread_id": record.get("thread_id"),
                "source_message_id": record.get("source_message_id"),
                "source_language": record.get("source_language"),
                "category": category,
                "repository_route": record.get("repository_route"),
                "issue_ids": record.get("issue_ids", []),
                "feature_issue_ids": record.get("feature_issue_ids", []),
                "pr_ids": record.get("pr_ids", []),
                "previous_status": status,
                "kind": record.get("tracking_kind"),
                "due_at": iso(due),
                "prior_notification_keys": sorted(notified),
            }
        )
    result.sort(key=lambda item: (item["due_at"], item["tracking_key"]))
    return result, notified


def append_record(path: Path, record: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record_fingerprint(record)


def record_check(args: argparse.Namespace, policy: dict[str, Any]) -> dict[str, Any]:
    config = policy_config(policy)
    records, invalid = read_records(args.audit)
    candidates = [
        (record, expanded)
        for record in records
        for expanded in expanded_tracking_records(record)
        if tracking_key(expanded) == args.tracking_key
    ]
    if not candidates:
        raise ValueError("tracking_key was not found")
    previous_record, previous = candidates[-1]
    if record_fingerprint(previous_record) != args.prior_audit_record_fingerprint:
        raise ValueError("audit record changed; refusing to append without a fresh queue fingerprint")
    pending = {str(item) for item in config.get("pending_statuses", [])}
    if args.status not in pending:
        raise ValueError("record-check status must be a policy-approved pending status")
    checked = parse_time(args.repository_checked_at) or datetime.now(timezone.utc)
    next_check = parse_time(args.next_check_at) or checked + timedelta(hours=int(config["check_interval_hours"]))
    evidence = [item.strip() for item in args.repository_evidence_id if item.strip()]
    if not evidence:
        raise ValueError("at least one repository evidence ID is required")
    record = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": iso(datetime.now(timezone.utc)),
        "run_id": args.run_id,
        "thread_id": previous.get("thread_id"),
        "source_message_id": previous.get("source_message_id"),
        "latest_message_id": previous.get("latest_message_id"),
        "latest_sender_domain": previous.get("latest_sender_domain"),
        "decision": "no-reply",
        "draft_disposition": "none",
        "workflow_kind": "follow_up_check",
        "category": previous.get("category"),
        "source_language": previous.get("source_language"),
        "repository_route": previous.get("repository_route"),
        "issue_ids": previous.get("issue_ids", []),
        "feature_issue_ids": previous.get("feature_issue_ids", []),
        "pr_ids": previous.get("pr_ids", []),
        "repository_action_ids": [],
        "product_review_action_ids": previous.get("product_review_action_ids", []),
        "tracking_key": args.tracking_key,
        "tracking_status": args.status,
        "next_check_at": iso(next_check),
        "tracking_items": [
            {
                "tracking_key": args.tracking_key,
                "kind": previous.get("tracking_kind"),
                "category": previous.get("category"),
                "status": args.status,
                "next_check_at": iso(next_check),
                "issue_ids": previous.get("issue_ids", []),
                "feature_issue_ids": previous.get("feature_issue_ids", []),
                "pr_ids": previous.get("pr_ids", []),
            }
        ],
        "repository_checked_at": iso(checked),
        "repository_evidence_ids": evidence,
        "prior_audit_record_fingerprint": args.prior_audit_record_fingerprint,
        "repository_evidence_fingerprint": "sha256:" + hashlib.sha256(canonical(evidence)).hexdigest(),
        "invalid_lines_ignored": invalid,
    }
    record["record_fingerprint"] = append_record(args.audit, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    queue = sub.add_parser("queue")
    queue.add_argument("audit", type=Path)
    queue.add_argument("--policy", type=Path, required=True)
    queue.add_argument("--now")

    check = sub.add_parser("record-check")
    check.add_argument("audit", type=Path)
    check.add_argument("--policy", type=Path, required=True)
    check.add_argument("--tracking-key", required=True)
    check.add_argument("--prior-audit-record-fingerprint", required=True)
    check.add_argument("--status", required=True)
    check.add_argument("--repository-checked-at")
    check.add_argument("--next-check-at")
    check.add_argument("--repository-evidence-id", action="append", default=[])
    check.add_argument("--run-id", default="follow-up-check")
    args = parser.parse_args()

    try:
        policy = load_json(args.policy)
        config = policy_config(policy)
        if args.command == "queue":
            now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
            if now is None:
                raise ValueError("--now must be an ISO-8601 timestamp")
            records, invalid = read_records(args.audit)
            items, notified = queue_items(records, config, now)
            print(json.dumps({"schema_version": SCHEMA_VERSION, "now": iso(now), "invalid_lines_ignored": invalid, "notified_keys": sorted(notified), "items": items}, ensure_ascii=False, sort_keys=True))
        else:
            print(json.dumps(record_check(args, policy), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
