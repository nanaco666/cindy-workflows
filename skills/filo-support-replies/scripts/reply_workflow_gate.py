#!/usr/bin/env python3
"""Deterministic gates and fingerprinted audit records for Filo support replies.

The script reads a JSON manifest. It never calls Gmail or GitHub itself and never writes
customer bodies to the audit log. Use it before repository work, before creating a draft,
and after Gmail returns the real draft/message identifiers.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import html
import json
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from chinese_script import chinese_script, normalize_simplified, script_mismatch_error


AUDIT_SCHEMA_VERSION = 3
INTAKE_DB_SCHEMA_VERSION = 2
CAPABILITY_STATUSES = {"existing", "partial", "missing", "unverified"}
BUG_VERSION_CONCLUSIONS = {
    "no_applicable_release",
    "update_to_newer_fix",
    "regression_or_fix_not_effective",
    "different_platform",
    "unverified",
}
EMAIL_ADDRESS = re.compile(r"^[^\s@]+@([^\s@]+)$")
ZH_CHARS = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_LETTERS = re.compile(r"[A-Za-z]")
HTML_TAG = re.compile(r"<[^>]+>")
ALLOWED_MIME_TYPES = {"text/plain", "text/html", "multipart/alternative"}
SCAN_WINDOW_TOLERANCE_SECONDS = 300
SCAN_WINDOW_MAX_SPAN_SECONDS = 31 * 24 * 60 * 60
SCAN_LOCATIONS = ("inbox", "spam")
SCAN_DATE_WINDOW_RE = re.compile(r"\b(?:after|before):\d{4}/\d{1,2}/\d{1,2}")
SCAN_CANDIDATE_DISPOSITIONS = {"new", "skipped-already-indexed"}
# Only the support audit pool ("email") proves this workflow already handled a
# message. Rows imported from triage state ("gmail"/"feishu") mean the feedback
# was triaged into Issues, not that a reply draft exists.
SCAN_SKIP_SOURCE_TYPES = {"email"}
DEFAULT_NO_REPLY_CATEGORIES = {"partnership_or_special_terms"}

INTERNAL_TERMS = {
    r"\brelease[ -]?tag\b": "release tag",
    r"(?<![#\w])tag(?![#\w])": "tag",
    r"\bmerge commit\b": "merge commit",
    r"\bhard rebuild\b": "hard rebuild",
    r"\bstale cursor\b": "stale cursor",
    r"\bhistoryId\b": "historyId",
    r"\bcherry-pick(?:ed|ing)?\b": "cherry-pick",
    r"\bdeploy(?:ment)? pipeline\b": "deployment pipeline",
    r"发布标签": "发布标签",
    r"合并提交": "合并提交",
    r"硬重建": "硬重建",
    r"过期游标": "过期游标",
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def normalize_email(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    match = re.search(r"<([^<>]+@[^<>]+)>", raw)
    return (match.group(1) if match else raw).strip().lower()


def sender_domain(raw: Any) -> str:
    address = normalize_email(raw)
    match = EMAIL_ADDRESS.fullmatch(address)
    return match.group(1).lower() if match else ""


def no_reply_categories(policy: dict[str, Any]) -> set[str]:
    automation = policy.get("automation") if isinstance(policy.get("automation"), dict) else {}
    configured = automation.get("no_reply_categories")
    if isinstance(configured, list):
        return {item.strip() for item in configured if isinstance(item, str) and item.strip()}
    return set(DEFAULT_NO_REPLY_CATEGORIES)


def is_google_groups_delivery(message: dict[str, Any]) -> bool:
    list_id = str(message.get("list_id") or "").strip().lower()
    return bool(list_id and "groups.google" in list_id)


def verified_group_customer_address(
    message: dict[str, Any], policy: dict[str, Any]
) -> str:
    """Resolve the customer behind a sole Google Groups delivery.

    A Groups wrapper is not a colleague reply. It may be used as the canonical
    Gmail message only when Reply-To and X-Original-Sender agree on the same
    non-staff address. A separate direct representation is still preferred and
    is expressed by a different thread.canonical_thread_id.
    """

    threading = policy.get("threading", {})
    if threading.get("allow_verified_google_groups_delivery_as_canonical") is not True:
        return ""
    if not is_google_groups_delivery(message):
        return ""

    reply_to = normalize_email(message.get("reply_to"))
    original_sender = normalize_email(message.get("original_sender"))
    if not reply_to or not original_sender:
        return ""
    if threading.get("require_google_groups_reply_to_original_match") is True:
        if reply_to != original_sender:
            return ""
    if sender_domain(reply_to) in staff_domains(policy):
        return ""
    return reply_to


def effective_sender(message: dict[str, Any], policy: dict[str, Any]) -> str:
    return verified_group_customer_address(message, policy) or normalize_email(message.get("from"))


def normalize_rfc_message_id(raw: Any) -> str:
    return str(raw or "").strip()


def rfc_reference_values(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [normalize_rfc_message_id(value) for value in raw if normalize_rfc_message_id(value)]
    if not isinstance(raw, str):
        return []
    bracketed = re.findall(r"<[^<>]+>", raw)
    if bracketed:
        return [value.strip() for value in bracketed]
    return [value.strip() for value in raw.split() if value.strip()]


def parse_message_datetime(raw: Any) -> datetime | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def detect_language(text: Any) -> str:
    if not isinstance(text, str) or not text.strip():
        return "unknown"
    cjk = len(ZH_CHARS.findall(text))
    latin = len(LATIN_LETTERS.findall(text))
    if cjk >= 4 and cjk >= max(4, int(latin * 0.18)):
        return "zh"
    if latin >= 8:
        return "en"
    return "zh" if cjk else "unknown"


def normalize_visible_text(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    without_tags = HTML_TAG.sub(" ", html.unescape(text))
    return " ".join(without_tags.replace("\r", "").split()).strip()


def compact_visible_text(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    without_tags = HTML_TAG.sub("", html.unescape(text))
    return re.sub(r"\s+", "", without_tags).strip()


def visible_quoted_original(rendered_body: Any, source_text: Any) -> bool:
    """Return true only when the full source is visibly rendered as a quote.

    A matching thread ID or RFC reply header is not enough. The saved body must
    contain the source inside a plaintext `>` quote or an HTML blockquote.
    """

    if not isinstance(rendered_body, str) or not rendered_body.strip():
        return False
    normalized_source = normalize_visible_text(source_text)
    if not normalized_source:
        return False

    plaintext_quote = "\n".join(
        match.group(1)
        for line in rendered_body.replace("\r", "").splitlines()
        if (match := re.match(r"^\s*>\s?(.*)$", line))
    )
    if normalized_source in normalize_visible_text(plaintext_quote):
        return True

    for block in re.findall(
        r"<blockquote\b[^>]*>(.*?)</blockquote\s*>",
        rendered_body,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        if normalized_source in normalize_visible_text(block):
            return True
    return False


def email_format_errors(
    draft: dict[str, Any], reply_body: str, require_persisted_draft: bool
) -> list[str]:
    """Validate the standard Gmail rich-text/MIME contract for support drafts."""

    errors: list[str] = []
    mime_type = str(draft.get("mime_type") or "").strip().lower()
    body_plain = str(draft.get("body_plain") or "")
    body_html = str(draft.get("body_html") or "")
    persisted_mime_type = str(draft.get("persisted_mime_type") or "").strip().lower()
    persisted_body_html = str(draft.get("persisted_body_html") or "")
    emphasis = as_string_list(draft.get("emphasis"))

    if mime_type != "multipart/alternative":
        errors.append("draft.mime_type must be multipart/alternative")
    if not body_plain.strip():
        errors.append("draft.body_plain is required as the plaintext fallback")
    if not body_html.strip():
        errors.append("draft.body_html is required")
    if body_html and len(re.findall(r'<div\b[^>]*dir=["\']ltr["\'][^>]*>', body_html, re.I)) < 3:
        errors.append("draft.body_html must preserve normal Gmail paragraph breaks")
    if body_html and "<blockquote" not in body_html.casefold():
        errors.append("draft.body_html must use an HTML blockquote for the original message")
    if not 1 <= len(emphasis) <= 3:
        errors.append("draft.emphasis must contain one to three short phrases")
    for phrase in emphasis:
        if phrase not in reply_body:
            errors.append(f"draft.emphasis phrase is absent from reply_body: {phrase!r}")
            continue
        expected = f"<strong>{html.escape(phrase)}</strong>"
        if expected not in body_html:
            errors.append(f"draft.body_html must render emphasis phrase in <strong>: {phrase!r}")

    paragraph_count = len(
        [part for part in re.split(r"\n\s*\n", reply_body.strip()) if part.strip()]
    )
    if paragraph_count < 3:
        errors.append("draft.reply_body must use at least three natural paragraphs")

    if require_persisted_draft:
        if persisted_mime_type not in ALLOWED_MIME_TYPES:
            errors.append("draft.persisted_mime_type must be read from the saved Gmail MIME tree")
        if persisted_mime_type != "multipart/alternative":
            errors.append("saved Gmail draft must preserve multipart/alternative MIME")
        if not persisted_body_html.strip():
            errors.append("draft.persisted_body_html must contain the saved HTML part")
        elif "<blockquote" not in persisted_body_html.casefold():
            errors.append("saved Gmail HTML part must preserve the quoted original block")
        for phrase in emphasis:
            expected = f"<strong>{html.escape(phrase)}</strong>"
            if expected not in persisted_body_html:
                errors.append(
                    f"saved Gmail HTML part must preserve emphasized phrase: {phrase!r}"
                )
    return errors


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in as_list(value) if str(item).strip()]


def workflow_kind(manifest: dict[str, Any]) -> str:
    return str(manifest.get("workflow_kind") or "intake")


def follow_up_data(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("follow_up")
    return value if isinstance(value, dict) else {}


def tracking_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    follow_up = follow_up_data(manifest)
    items = [item for item in as_list(follow_up.get("items")) if isinstance(item, dict)]
    if items:
        return items
    return [follow_up] if str(follow_up.get("tracking_key") or "").strip() else []


def capability_checks(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in as_list(manifest.get("capability_checks")) if isinstance(item, dict)]


def bug_version_checks(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in as_list(manifest.get("bug_version_checks")) if isinstance(item, dict)]


def parse_product_version(raw: Any) -> tuple[int, ...] | None:
    match = re.search(r"(?<!\d)(\d{1,3}(?:\.\d{1,3}){1,3})(?!\d)", str(raw or ""))
    if not match:
        return None
    parts = tuple(int(part) for part in match.group(1).split("."))
    return parts + (0,) * (4 - len(parts))


def source_product_versions(message: dict[str, Any]) -> set[str]:
    text = f"{message.get('subject') or ''}\n{message.get('text') or ''}"
    versions: set[str] = set()
    for match in re.finditer(r"(?<!\d)(\d{1,3}(?:\.\d{1,3}){1,3})(?!\d)", text):
        value = match.group(1)
        parsed = parse_product_version(value)
        if parsed and parsed[0] <= 100:
            versions.add(value)
    return versions


def normalize_product_platform(raw: Any) -> str:
    value = str(raw or "").strip().casefold()
    if value in {"desktop", "mac", "macos", "mac os", "windows", "electron"}:
        return "desktop"
    if value in {"ios", "iphone", "ipad"}:
        return "ios"
    if value in {"android"}:
        return "android"
    if value in {"server", "api", "backend"}:
        return "server"
    return value


def claims_released_fix(reply_body: str) -> bool:
    simplified = normalize_simplified(reply_body)
    pending_markers = (
        "等待发布",
        "尚未发布",
        "还未发布",
        "仍未发布",
        "没有发布",
        "not released",
        "waiting for release",
    )
    without_pending = simplified.casefold()
    for marker in pending_markers:
        without_pending = without_pending.replace(marker.casefold(), "")
    return bool(
        re.search(
            r"\b(?:has now been released|has been released|is now available|has been fixed|is fixed|resolved in)\b"
            r"|(?:已经|已)(?:修复|解决)"
            r"|(?:已经|已)(?:在|于)?.{0,20}(?:发布|上线)",
            without_pending,
            flags=re.IGNORECASE,
        )
    )


def bug_version_check_errors(
    manifest: dict[str, Any],
    category: str,
    decision: str,
    latest_customer: dict[str, Any] | None,
    reply_body: str,
) -> list[str]:
    if category not in {"bug", "bug_or_reliability", "mixed_bug_and_feature"}:
        return []

    source_versions = source_product_versions(latest_customer or {})
    release_claim = workflow_kind(manifest) == "resolution_follow_up" or claims_released_fix(reply_body)
    checks = bug_version_checks(manifest)
    if not source_versions and not release_claim and not checks:
        return []
    if source_versions and not checks:
        return [
            "Bug source contains an app version; bug_version_checks must compare the reported version with any claimed fix release"
        ]
    if release_claim and not checks:
        return ["released Bug claim requires bug_version_checks release applicability evidence"]

    errors: list[str] = []
    saw_applicable_release = False
    for index, item in enumerate(checks):
        prefix = f"bug_version_checks[{index}]"
        key = str(item.get("key") or "").strip()
        reported_version_raw = str(item.get("reported_version") or "").strip()
        reported_platform_raw = str(item.get("reported_platform") or "").strip()
        fix_version_raw = str(item.get("fix_released_version") or "").strip()
        fix_platform_raw = str(item.get("fix_platform") or "").strip()
        reproduced = item.get("problem_reproduced_on_reported_version")
        conclusion = str(item.get("conclusion") or "").strip()
        evidence_ids = as_string_list(item.get("evidence_ids"))

        if not key:
            errors.append(f"{prefix}.key is required")
        if not reported_version_raw:
            errors.append(f"{prefix}.reported_version is required")
        elif source_versions and reported_version_raw not in source_versions:
            errors.append(f"{prefix}.reported_version must match a version found in the latest customer message")
        if not reported_platform_raw:
            errors.append(f"{prefix}.reported_platform is required")
        if reproduced is not True:
            errors.append(f"{prefix}.problem_reproduced_on_reported_version must be true for a current Bug report")
        if conclusion not in BUG_VERSION_CONCLUSIONS:
            errors.append(
                f"{prefix}.conclusion must be one of {sorted(BUG_VERSION_CONCLUSIONS)}"
            )
        if not evidence_ids:
            errors.append(f"{prefix}.evidence_ids must identify the customer version and release/repository check")

        reported_version = parse_product_version(reported_version_raw)
        fix_version = parse_product_version(fix_version_raw)
        reported_platform = normalize_product_platform(reported_platform_raw)
        fix_platform = normalize_product_platform(fix_platform_raw)

        if fix_version_raw and not fix_version:
            errors.append(f"{prefix}.fix_released_version must contain a comparable numeric version")
        if fix_version and not fix_platform_raw:
            errors.append(f"{prefix}.fix_platform is required when a released fix version is present")

        if not fix_version:
            if conclusion not in {"no_applicable_release", "unverified"}:
                errors.append(f"{prefix} without a released fix must conclude no_applicable_release or unverified")
            continue

        if reported_platform != fix_platform:
            if conclusion != "different_platform":
                errors.append(f"{prefix} compares different platforms and must conclude different_platform")
            continue

        if not reported_version:
            errors.append(f"{prefix}.reported_version must contain a comparable numeric version")
            continue

        if reported_version >= fix_version:
            if conclusion != "regression_or_fix_not_effective":
                errors.append(
                    f"{prefix}: customer still reproduces on version {reported_version_raw}, which is at or after fix release {fix_version_raw}; treat it as regression_or_fix_not_effective"
                )
            if release_claim:
                errors.append(
                    f"{prefix}: cannot claim released/resolved when the customer still reproduces on the same or newer version"
                )
            if decision != "review-required" and not as_string_list(manifest.get("repository_action_ids")):
                errors.append(
                    f"{prefix}: post-release reproduction requires a verified Issue/PR evidence update or review-required"
                )
        else:
            if conclusion != "update_to_newer_fix":
                errors.append(
                    f"{prefix}: a newer same-platform fix release must conclude update_to_newer_fix"
                )
            saw_applicable_release = True

    if release_claim and not saw_applicable_release:
        errors.append(
            "released Bug claim requires a same-platform fix version newer than the customer-reported reproducing version"
        )
    return errors


def repository_search(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("repository_search")
    return value if isinstance(value, dict) else {}


def existing_drafts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    thread = manifest.get("thread")
    if not isinstance(thread, dict):
        return []
    return [item for item in as_list(thread.get("existing_drafts")) if isinstance(item, dict)]


def existing_draft_fingerprint(draft: dict[str, Any]) -> str:
    """Fingerprint the saved draft metadata/content used by the review gate.

    The audit record never stores the body, but the preflight manifest must bind a
    review to the exact draft that was read. This prevents an arbitrary evidence
    string from being used to skip a newer or different Gmail draft.
    """
    return fingerprint(
        {
            "draft_id": draft.get("draft_id") or draft.get("id"),
            "message_id": draft.get("message_id"),
            "thread_id": draft.get("thread_id"),
            "subject": draft.get("subject"),
            "body": draft.get("body") or draft.get("body_html"),
            "body_plain": draft.get("body_plain"),
        }
    )


def repository_search_errors(
    manifest: dict[str, Any], policy: dict[str, Any], category: str
) -> list[str]:
    """Require explicit Issue and PR search evidence before any tracked reply.

    The agent must record evidence even when a search returns no match.  This is
    deliberately a presence check: the workflow owns the actual GitHub/local
    repository query, while this gate prevents a model from silently skipping it.
    """
    threading = policy.get("threading", {})
    if threading.get("require_repository_search_evidence") is not True:
        return []
    tracked_categories = {
        "bug",
        "bug_or_reliability",
        "feature_request",
        "mixed_bug_and_feature",
        "product_capability_question",
    }
    if category not in tracked_categories:
        return []
    search = repository_search(manifest)
    errors: list[str] = []
    if not str(search.get("checked_at") or "").strip():
        errors.append("repository_search.checked_at is required")
    if not str(search.get("issue_query") or "").strip():
        errors.append("repository_search.issue_query is required")
    if not str(search.get("pr_query") or "").strip():
        errors.append("repository_search.pr_query is required")
    if not as_string_list(search.get("issue_evidence_ids")):
        errors.append("repository_search.issue_evidence_ids must record the Issue search result")
    if not as_string_list(search.get("pr_evidence_ids")):
        errors.append("repository_search.pr_evidence_ids must record the PR search result")
    return errors


def existing_draft_review_errors(
    manifest: dict[str, Any], policy: dict[str, Any], context: dict[str, Any]
) -> list[str]:
    if not context["existing_draft_count"]:
        return []
    if policy.get("threading", {}).get("require_existing_draft_review") is not True:
        return []
    drafts = existing_drafts(manifest)
    review = manifest.get("existing_draft_review")
    if not isinstance(review, dict):
        return ["existing draft requires an explicit review before it may be skipped or updated"]
    errors: list[str] = []
    if review.get("status") != "reviewed":
        errors.append("existing_draft_review.status must be reviewed")
    action = str(review.get("action") or "")
    if action not in {"skip_verified", "update"}:
        errors.append("existing_draft_review.action must be skip_verified or update")
    if not str(review.get("reviewed_at") or "").strip():
        errors.append("existing_draft_review.reviewed_at is required")
    if not as_string_list(review.get("evidence_ids")):
        errors.append("existing_draft_review.evidence_ids must identify the read draft and decision")
    reviewed_ids = as_string_list(review.get("draft_ids"))
    reviewed_fingerprints = as_string_list(review.get("draft_fingerprints"))
    actual_ids = [str(item.get("draft_id") or item.get("id") or "").strip() for item in drafts]
    if not reviewed_ids:
        errors.append("existing_draft_review.draft_ids must identify every existing Gmail draft")
    if set(reviewed_ids) != set(actual_ids) or any(not value for value in actual_ids):
        errors.append("existing_draft_review.draft_ids must match the existing Gmail draft IDs")
    expected_fingerprints = [existing_draft_fingerprint(item) for item in drafts]
    if not reviewed_fingerprints:
        errors.append("existing_draft_review.draft_fingerprints must bind the reviewed draft contents")
    if set(reviewed_fingerprints) != set(expected_fingerprints):
        errors.append("existing_draft_review.draft_fingerprints do not match the saved Gmail drafts")
    if action == "update" and policy.get("threading", {}).get("allow_existing_draft_update") is not True:
        errors.append("policy does not allow updating an existing draft")
    if action == "update":
        draft = manifest.get("draft") if isinstance(manifest.get("draft"), dict) else {}
        if draft.get("operation") != "update":
            errors.append("existing draft updates must set draft.operation=update")
        if not str(draft.get("draft_id") or "").strip():
            errors.append("existing draft updates require draft.draft_id")
        elif str(draft.get("draft_id")) not in reviewed_ids:
            errors.append("existing draft update must target a reviewed draft_id")
    return errors


def capability_check_errors(
    manifest: dict[str, Any],
    policy: dict[str, Any],
    category: str,
    decision: str,
    reply_body: str,
) -> list[str]:
    config = policy.get("feature_tracking", {})
    if config.get("require_capability_check_before_issue") is not True:
        return []
    if category not in {"feature_request", "mixed_bug_and_feature", "product_capability_question"}:
        return []

    errors: list[str] = []
    checks = capability_checks(manifest)
    if not checks:
        return ["functional request requires at least one capability_checks item"]

    routes = policy.get("bug_tracking", {}).get("repository_routes", {})
    statuses: list[str] = []
    for index, item in enumerate(checks):
        prefix = f"capability_checks[{index}]"
        key = str(item.get("key") or "").strip()
        status = str(item.get("status") or "").strip()
        route = str(item.get("repository_route") or "").strip()
        checked_at = str(item.get("checked_at") or "").strip()
        evidence_ids = as_string_list(item.get("evidence_ids"))
        issue_search_evidence_ids = as_string_list(item.get("issue_search_evidence_ids"))
        pr_search_evidence_ids = as_string_list(item.get("pr_search_evidence_ids"))
        guidance = str(item.get("customer_guidance") or "").strip()

        statuses.append(status)
        if not key:
            errors.append(f"{prefix}.key is required")
        if status not in CAPABILITY_STATUSES:
            errors.append(
                f"{prefix}.status must be one of {sorted(CAPABILITY_STATUSES)}"
            )
        if route not in routes and route != "mixed":
            errors.append(f"{prefix}.repository_route must be frontend, server, or mixed")
        if not checked_at:
            errors.append(f"{prefix}.checked_at is required")
        if not evidence_ids:
            errors.append(f"{prefix}.evidence_ids requires current product evidence")
        if not issue_search_evidence_ids:
            errors.append(f"{prefix}.issue_search_evidence_ids requires an Issue search result")
        if not pr_search_evidence_ids:
            errors.append(f"{prefix}.pr_search_evidence_ids requires a PR search result")
        if status in {"existing", "partial"}:
            if not guidance:
                errors.append(f"{prefix}.customer_guidance is required for {status} capability")
            elif guidance.casefold() not in reply_body.casefold():
                errors.append(
                    f"reply must include customer guidance from {prefix}.customer_guidance"
                )

    if category in {"feature_request", "mixed_bug_and_feature"} and not any(
        status in {"partial", "missing"} for status in statuses
    ):
        errors.append(
            "Feature intake requires a verified partial or missing capability; existing capability is a how-to"
        )
    if category == "product_capability_question":
        if any(status != "existing" for status in statuses):
            errors.append(
                "product_capability_question may contain only verified existing capabilities"
            )
        if as_list(manifest.get("feature_issue_ids")) or as_string_list(
            manifest.get("product_review_action_ids")
        ):
            errors.append("existing capability must not create or route a Feature ticket")
    if "unverified" in statuses and decision != "review-required":
        errors.append("unverified capability requires review-required decision")
    return errors


def pending_tracking_errors(manifest: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pending = set(as_string_list(policy.get("follow_up", {}).get("pending_statuses")))
    for index, item in enumerate(tracking_items(manifest)):
        status = str(item.get("status") or "")
        if status not in pending:
            continue
        prefix = f"follow_up.items[{index}]"
        if not str(item.get("tracking_key") or "").strip():
            errors.append(f"{prefix}.tracking_key is required")
        if item.get("kind") not in {"bug", "feature"}:
            errors.append(f"{prefix}.kind must be bug or feature")
        if not str(item.get("next_check_at") or "").strip():
            errors.append(f"{prefix}.next_check_at is required")
        ids = (
            as_list(item.get("issue_ids"))
            + as_list(item.get("feature_issue_ids"))
            + as_list(item.get("pr_ids"))
        )
        if not any(str(value).isdigit() for value in ids):
            errors.append(f"{prefix} requires at least one Issue, Feature, or PR ID")
    return errors


def resolution_follow_up_errors(
    manifest: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    if workflow_kind(manifest) != "resolution_follow_up":
        return []

    errors: list[str] = []
    config = policy.get("follow_up")
    if not isinstance(config, dict) or config.get("enabled") is not True:
        errors.append("resolution follow-up is not enabled by policy")
        return errors

    follow_up = follow_up_data(manifest)
    prior_fingerprint = str(follow_up.get("prior_audit_record_fingerprint") or "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", prior_fingerprint):
        errors.append("follow_up.prior_audit_record_fingerprint must be a SHA-256 fingerprint")

    pending_statuses = set(as_string_list(config.get("pending_statuses")))
    previous_status = str(follow_up.get("previous_status") or "")
    if previous_status not in pending_statuses:
        errors.append("follow_up.previous_status must be a policy-approved pending status")
    if follow_up.get("status") != "released":
        errors.append("follow_up.status must be released")

    released_version = str(follow_up.get("released_version") or "").strip()
    if config.get("require_verified_release_version") is True and not released_version:
        errors.append("follow_up.released_version is required")
    if not str(follow_up.get("repository_checked_at") or "").strip():
        errors.append("follow_up.repository_checked_at is required")
    if not as_string_list(follow_up.get("release_evidence_ids")):
        errors.append("follow_up.release_evidence_ids must contain verified release evidence")

    notification_key = str(follow_up.get("notification_key") or "").strip()
    if not notification_key:
        errors.append("follow_up.notification_key is required")
    prior_keys = set(as_string_list(follow_up.get("prior_notification_keys")))
    if follow_up.get("duplicate_notification") is True or notification_key in prior_keys:
        errors.append("release notification has already been drafted or recorded")
    return errors


def load_policy(path: Path) -> dict[str, Any]:
    policy = read_json(path)
    if policy.get("schema_version") != AUDIT_SCHEMA_VERSION:
        raise ValueError(f"policy schema_version must be {AUDIT_SCHEMA_VERSION}")
    return policy


def thread_data(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("thread")
    if not isinstance(value, dict):
        raise ValueError("manifest.thread must be an object")
    return value


def non_draft_messages(thread: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in as_list(thread.get("messages")):
        if isinstance(item, dict) and not item.get("is_draft", False):
            result.append(item)
    return result


def customer_messages(thread: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    domains = staff_domains(policy)
    return [
        message
        for message in non_draft_messages(thread)
        if sender_domain(effective_sender(message, policy)) not in domains
    ]


def staff_domains(policy: dict[str, Any]) -> set[str]:
    values = policy.get("threading", {}).get("staff_domains", [])
    return {str(value).strip().lower() for value in values if str(value).strip()}


def related_staff_reply_context(
    manifest: dict[str, Any], policy: dict[str, Any], latest_customer: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Verify staff replies that Gmail placed in a sibling thread.

    Gmail thread IDs remain the draft target. This evidence only closes ordinary
    intake when a non-draft staff message points to the latest customer message's
    exact RFC Message-ID and was sent after that customer message.
    """

    candidates = as_list(manifest.get("related_staff_replies"))
    if not candidates or latest_customer is None:
        return [], []

    latest_customer_id = str(latest_customer.get("id") or "").strip()
    latest_rfc_id = normalize_rfc_message_id(latest_customer.get("rfc_message_id"))
    latest_date = parse_message_datetime(latest_customer.get("date"))
    verified: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            errors.append(f"related_staff_replies[{index}] must be an object")
            continue
        if item.get("is_draft") is True:
            continue
        if sender_domain(effective_sender(item, policy)) not in staff_domains(policy):
            continue
        if str(item.get("customer_message_id") or "").strip() != latest_customer_id:
            continue

        in_reply_to = normalize_rfc_message_id(item.get("in_reply_to"))
        references = rfc_reference_values(item.get("references"))
        if not latest_rfc_id:
            errors.append(
                "latest customer message requires rfc_message_id before a sibling staff reply can be verified"
            )
            continue
        if in_reply_to != latest_rfc_id and latest_rfc_id not in references:
            continue

        message_id = str(item.get("message_id") or item.get("id") or "").strip()
        thread_id = str(item.get("thread_id") or "").strip()
        if not message_id or not thread_id:
            errors.append(
                f"related_staff_replies[{index}] requires concrete Gmail message_id and thread_id"
            )
            continue
        staff_date = parse_message_datetime(item.get("date"))
        if latest_date is None or staff_date is None:
            errors.append(
                f"related_staff_replies[{index}] and its customer message require parseable dates"
            )
            continue
        if staff_date <= latest_date:
            continue

        verified.append(
            {
                "message_id": message_id,
                "thread_id": thread_id,
                "from": effective_sender(item, policy),
                "customer_message_id": latest_customer_id,
                "customer_rfc_message_id": latest_rfc_id,
                "date": staff_date.isoformat().replace("+00:00", "Z"),
            }
        )
    return verified, errors


def compute_context(manifest: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    thread = thread_data(manifest)
    messages = non_draft_messages(thread)
    if not messages:
        raise ValueError("thread.messages must contain at least one non-draft message")

    latest = messages[-1]
    domains = staff_domains(policy)
    customers = customer_messages(thread, policy)
    latest_customer = customers[-1] if customers else None
    source_text = latest_customer.get("text", "") if latest_customer else ""
    source_language = detect_language(source_text)
    declared_language = manifest.get("source_language")
    if declared_language in {"zh", "en"} and source_language not in {"unknown", declared_language}:
        raise ValueError(
            f"declared source_language {declared_language!r} conflicts with detected {source_language!r}"
        )
    if source_language == "unknown" and declared_language in {"zh", "en"}:
        source_language = declared_language

    thread_id = str(thread.get("id") or "")
    canonical_thread_id = str(thread.get("canonical_thread_id") or thread_id)
    compact_messages = [
        {
            "id": message.get("id"),
            "from": effective_sender(message, policy),
            "transport_from": normalize_email(message.get("from")),
            "google_groups_delivery": is_google_groups_delivery(message),
            "date": message.get("date"),
            "subject_fingerprint": fingerprint(message.get("subject", "")),
            "body_fingerprint": fingerprint(message.get("text", "")),
        }
        for message in messages
    ]
    source_fingerprint = fingerprint(
        {
            "id": latest_customer.get("id") if latest_customer else None,
            "from": normalize_email(latest_customer.get("from")) if latest_customer else "",
            "subject": latest_customer.get("subject", "") if latest_customer else "",
            "text": source_text,
        }
    )
    related_staff_replies, related_staff_reply_errors = related_staff_reply_context(
        manifest, policy, latest_customer
    )
    return {
        "thread_id": thread_id,
        "canonical_thread_id": canonical_thread_id,
        "thread_fingerprint": fingerprint({"thread_id": thread_id, "messages": compact_messages}),
        "latest_message_id": str(latest.get("id") or ""),
        "latest_sender_domain": sender_domain(effective_sender(latest, policy)),
        "latest_transport_sender_domain": sender_domain(latest.get("from")),
        "latest_customer_message_id": str(latest_customer.get("id") or "") if latest_customer else "",
        "latest_customer_address": effective_sender(latest_customer, policy) if latest_customer else "",
        "source_message_fingerprint": source_fingerprint,
        "source_language": source_language,
        "existing_draft_count": len(as_list(thread.get("existing_drafts"))),
        "is_canonical_thread": bool(thread_id and thread_id == canonical_thread_id),
        "related_staff_reply_message_ids": [
            item["message_id"] for item in related_staff_replies
        ],
        "related_staff_reply_thread_ids": sorted(
            {item["thread_id"] for item in related_staff_replies}
        ),
        "related_staff_reply_evidence_fingerprint": fingerprint(related_staff_replies),
        "related_staff_reply_errors": related_staff_reply_errors,
    }


def preflight(manifest: dict[str, Any], policy: dict[str, Any]) -> tuple[dict[str, Any], int]:
    context = compute_context(manifest, policy)
    domains = staff_domains(policy)
    kind = workflow_kind(manifest)
    category = str(manifest.get("category") or "")
    follow_up_errors = resolution_follow_up_errors(manifest, policy)
    existing_review_errors: list[str] = []
    decision = "continue"
    reason = "verified-resolution-follow-up" if kind == "resolution_follow_up" else "unanswered-customer-message"

    if category in no_reply_categories(policy):
        decision = "stop"
        reason = "category-policy-no-reply"
    elif not context["is_canonical_thread"]:
        decision = "stop"
        reason = "non-canonical-or-duplicate-thread"
    elif kind == "resolution_follow_up" and follow_up_errors:
        decision = "stop"
        reason = "invalid-resolution-follow-up-evidence"
    elif context["latest_sender_domain"] in domains and kind != "resolution_follow_up":
        decision = "stop"
        reason = "latest-message-from-filo-colleague"
    elif context["related_staff_reply_errors"] and kind != "resolution_follow_up":
        decision = "stop"
        reason = "invalid-related-staff-reply-evidence"
    elif context["related_staff_reply_message_ids"] and kind != "resolution_follow_up":
        decision = "stop"
        reason = "related-thread-replied-by-filo-colleague"
    elif not context["latest_customer_message_id"]:
        decision = "stop"
        reason = "no-customer-message"
    elif context["source_language"] not in {"zh", "en"}:
        decision = "stop"
        reason = "source-language-unresolved"
    elif context["existing_draft_count"]:
        existing_review_errors = existing_draft_review_errors(manifest, policy, context)
        if existing_review_errors:
            decision = "stop"
            reason = "existing-draft-review-required"
        elif (manifest.get("existing_draft_review") or {}).get("action") == "update":
            decision = "continue"
            reason = "existing-draft-reviewed-update"
        else:
            decision = "stop"
            reason = "existing-draft-verified"

    result = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "run_id": manifest.get("run_id"),
        "decision": decision,
        "reason": reason,
        "workflow_kind": kind,
        "follow_up_errors": follow_up_errors,
        "existing_draft_review_errors": existing_review_errors,
        **context,
    }
    return result, 0 if decision == "continue" else 2


def issue_pr_reference_errors(body: str, language: str) -> list[str]:
    errors: list[str] = []
    if language == "zh":
        if re.search(r"\bIssue\s*#\d+", body, flags=re.IGNORECASE):
            errors.append("Chinese replies must use 'Issue 工单 #N', not bare 'Issue #N'")
        if re.search(r"\bPR\s*#\d+", body, flags=re.IGNORECASE):
            errors.append("Chinese replies must use 'PR 工单 #N', not bare 'PR #N'")
    elif language == "en":
        if re.search(r"\bIssue\s*#\d+", body, flags=re.IGNORECASE):
            errors.append("English replies must use 'Issue ticket #N', not bare 'Issue #N'")
        if re.search(r"\bPR\s*#\d+", body, flags=re.IGNORECASE):
            errors.append("English replies must use 'PR ticket #N', not bare 'PR #N'")
    return errors


def feature_reference_errors(body: str, language: str) -> list[str]:
    errors: list[str] = []
    if language == "zh" and re.search(r"\bFeature\s*#\d+", body, flags=re.IGNORECASE):
        errors.append("Chinese replies must use 'Feature 工单 #N', not bare 'Feature #N'")
    if language == "en" and re.search(r"\bFeature\s*#\d+", body, flags=re.IGNORECASE):
        errors.append("English replies must use 'Feature ticket #N', not bare 'Feature #N'")
    return errors


def validate_manifest(
    manifest: dict[str, Any], policy: dict[str, Any], require_persisted_draft: bool
) -> tuple[dict[str, Any], int]:
    context = compute_context(manifest, policy)
    errors: list[str] = []
    decision = str(manifest.get("decision") or "")
    category = str(manifest.get("category") or "")
    kind = workflow_kind(manifest)
    follow_up = follow_up_data(manifest)
    follow_up_errors = resolution_follow_up_errors(manifest, policy)
    draft = manifest.get("draft")
    draft = draft if isinstance(draft, dict) else {}
    body = str(draft.get("body") or draft.get("body_html") or "")
    reply_body = str(draft.get("reply_body") or "")
    persisted_body = str(
        draft.get("persisted_body_html") or draft.get("persisted_body") or ""
    )
    customers = customer_messages(thread_data(manifest), policy)
    latest_customer = customers[-1] if customers else None
    source_text = str(latest_customer.get("text") or "") if latest_customer else ""
    quote_body = persisted_body if require_persisted_draft else body
    quote_verified = visible_quoted_original(quote_body, source_text)

    if category in no_reply_categories(policy) and decision != "no-reply":
        errors.append(f"category {category!r} is configured as no-reply and cannot receive a draft")

    if (
        context["latest_sender_domain"] in staff_domains(policy)
        and decision != "no-reply"
        and kind != "resolution_follow_up"
    ):
        errors.append("latest non-draft message is from a Filo colleague; decision must be no-reply")
    if context["related_staff_reply_errors"] and kind != "resolution_follow_up":
        errors.extend(context["related_staff_reply_errors"])
    if (
        context["related_staff_reply_message_ids"]
        and decision != "no-reply"
        and kind != "resolution_follow_up"
    ):
        errors.append(
            "an RFC-linked sibling thread contains a later Filo colleague reply; decision must be no-reply"
        )
    if kind == "resolution_follow_up":
        errors.extend(follow_up_errors)
    if not context["is_canonical_thread"] and decision != "no-reply":
        errors.append("non-canonical or duplicate thread cannot receive a draft")
    existing_review_errors = existing_draft_review_errors(manifest, policy, context)
    errors.extend(existing_review_errors)
    if context["existing_draft_count"] and decision != "no-reply":
        review_action = (manifest.get("existing_draft_review") or {}).get("action")
        if review_action != "update":
            errors.append("thread already has a draft; only a reviewed update may validate a replacement")

    if decision in {"draft", "review-required"}:
        required = [
            "thread_id",
            "reply_message_id",
            "subject",
            "body",
            "reply_body",
            "quoted_original_message_id",
            "from_address",
            "to",
            "mime_type",
            "body_plain",
            "body_html",
        ]
        if require_persisted_draft:
            required += [
                "draft_id",
                "message_id",
                "persisted_mime_type",
                "persisted_body_html",
            ]
        for field in required:
            if not str(draft.get(field) or "").strip():
                errors.append(f"draft.{field} is required")

        if str(draft.get("thread_id") or "") != context["canonical_thread_id"]:
            errors.append("draft.thread_id must equal the canonical Gmail thread ID")
        if str(draft.get("reply_message_id") or "") != context["latest_customer_message_id"]:
            errors.append("draft.reply_message_id must equal the latest inbound customer message ID")
        if str(draft.get("quoted_original_message_id") or "") != context["latest_customer_message_id"]:
            errors.append("draft.quoted_original_message_id must equal the latest inbound customer message ID")
        if normalize_email(draft.get("to")) != context["latest_customer_address"]:
            errors.append("draft.to must equal the verified latest customer address")
        if reply_body and reply_body not in str(draft.get("body_plain") or ""):
            errors.append("draft.body_plain must contain the authored draft.reply_body")
        if reply_body and compact_visible_text(reply_body) not in compact_visible_text(body):
            errors.append("draft.body_html must visibly contain the authored draft.reply_body")
        if (
            require_persisted_draft
            and reply_body
            and compact_visible_text(reply_body) not in compact_visible_text(persisted_body)
        ):
            errors.append("saved Gmail HTML part must visibly contain the authored reply")
        errors.extend(email_format_errors(draft, reply_body, require_persisted_draft))
        if not visible_quoted_original(body, source_text):
            errors.append("draft.body must visibly quote the complete original customer message")
        if require_persisted_draft and not quote_verified:
            errors.append("saved Gmail draft must visibly quote the complete original customer message")

        subject = str(draft.get("subject") or "").strip()
        if re.fullmatch(r"(?i)re\s*:\s*", subject):
            errors.append("draft subject cannot be only 'Re:'")

        reply_language = detect_language(reply_body)
        if reply_language != context["source_language"]:
            errors.append(
                f"reply language {reply_language!r} does not match source language {context['source_language']!r}"
            )
        declared_reply_language = draft.get("language")
        if declared_reply_language in {"zh", "en"} and declared_reply_language != reply_language:
            errors.append("draft.language does not match the reply body")

        if reply_language == "zh" and context["source_language"] == "zh":
            script_error = script_mismatch_error(source_text, reply_body)
            if script_error:
                errors.append(script_error)

        # Chinese regex checks run on the Simplified-normalized reply so every
        # Simplified-written pattern also fires on Traditional drafts.
        reply_check = normalize_simplified(reply_body)

        for pattern, label in INTERNAL_TERMS.items():
            if re.search(pattern, reply_check, flags=re.IGNORECASE):
                errors.append(f"customer reply exposes internal term: {label}")
        errors.extend(issue_pr_reference_errors(reply_check, context["source_language"]))
        errors.extend(feature_reference_errors(reply_check, context["source_language"]))
        errors.extend(
            capability_check_errors(manifest, policy, category, decision, reply_body)
        )
        errors.extend(repository_search_errors(manifest, policy, category))
        errors.extend(
            bug_version_check_errors(
                manifest,
                category,
                decision,
                latest_customer,
                reply_body,
            )
        )

        if re.search(r"https?://(?:www\.)?github\.com/[^/\s]+/[^/\s]+", reply_check, flags=re.IGNORECASE):
            errors.append("customer reply must not include a private repository link")

        if category in {"bug", "bug_or_reliability", "mixed_bug_and_feature"}:
            routes = policy.get("bug_tracking", {}).get("repository_routes", {})
            route = manifest.get("repository_route")
            if route not in routes and route != "mixed":
                errors.append("Bug reply requires repository_route frontend, server, or mixed")
            issue_ids = [int(value) for value in as_list(manifest.get("issue_ids")) if str(value).isdigit()]
            pr_ids = [int(value) for value in as_list(manifest.get("pr_ids")) if str(value).isdigit()]
            if not issue_ids and not pr_ids:
                errors.append("Bug reply requires at least one verified Issue or PR ID")
            for issue_id in issue_ids:
                expected = (
                    f"Issue 工单 #{issue_id}" if context["source_language"] == "zh" else f"Issue ticket #{issue_id}"
                )
                if expected.casefold() not in reply_check.casefold():
                    errors.append(f"reply is missing customer-readable reference {expected!r}")
            for pr_id in pr_ids:
                expected = f"PR 工单 #{pr_id}" if context["source_language"] == "zh" else f"PR ticket #{pr_id}"
                if expected.casefold() not in reply_check.casefold():
                    errors.append(f"reply is missing customer-readable reference {expected!r}")

            claims_notification = bool(
                re.search(
                    r"(?:通知|同步|加急).{0,12}(?:开发|技术)|(?:notified|escalated).{0,18}(?:developer|engineering)",
                    reply_check,
                    flags=re.IGNORECASE,
                )
            )
            if claims_notification and not as_list(manifest.get("repository_action_ids")):
                errors.append("developer notification/expedite claim requires a repository action ID from this run")
            claims_pending = bool(
                re.search(
                    r"waiting for release|being handled|\brecorded\b|等待发布|正在处理|已记录",
                    reply_check,
                    flags=re.IGNORECASE,
                )
            )
            if claims_pending:
                bug_items = [item for item in tracking_items(manifest) if item.get("kind") == "bug"]
                if not bug_items:
                    errors.append("pending Bug reply requires a follow_up tracking item")
                errors.extend(pending_tracking_errors(manifest, policy))

        if category in {"feature_request", "mixed_bug_and_feature"}:
            routes = policy.get("bug_tracking", {}).get("repository_routes", {})
            route = manifest.get("repository_route")
            if route not in routes and route != "mixed":
                errors.append("Feature reply requires repository_route frontend, server, or mixed")
            feature_ids = [
                int(value) for value in as_list(manifest.get("feature_issue_ids")) if str(value).isdigit()
            ]
            if not feature_ids:
                errors.append("Feature reply requires at least one verified Feature ticket ID")
            for feature_id in feature_ids:
                expected = (
                    f"Feature 工单 #{feature_id}"
                    if context["source_language"] == "zh"
                    else f"Feature ticket #{feature_id}"
                )
                if expected.casefold() not in reply_check.casefold():
                    errors.append(f"reply is missing customer-readable reference {expected!r}")
            if not as_string_list(manifest.get("product_review_action_ids")):
                errors.append("Feature reply requires an auditable product-review action ID")
            feature_items = [item for item in tracking_items(manifest) if item.get("kind") == "feature"]
            if not feature_items:
                errors.append("Feature reply requires a follow_up tracking item")
            errors.extend(pending_tracking_errors(manifest, policy))

        if kind == "resolution_follow_up":
            released_version = str(follow_up.get("released_version") or "").strip()
            if released_version and released_version.casefold() not in reply_check.casefold():
                errors.append("resolution follow-up reply must name the verified released version")
            if not re.search(
                r"\b(?:released|available)\b|已(?:在|于)?.{0,16}(?:发布|上线)",
                reply_check,
                flags=re.IGNORECASE,
            ):
                errors.append("resolution follow-up reply must clearly state that the change is released")

    elif decision == "no-reply":
        if draft:
            errors.append("no-reply decision must not include a draft")
    else:
        errors.append("decision must be draft, review-required, or no-reply")

    result = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "run_id": manifest.get("run_id"),
        "decision": decision,
        "workflow_kind": kind,
        "validation": {"passed": not errors, "errors": errors},
        "quoted_original_message_id": draft.get("quoted_original_message_id"),
        "quoted_original_verified": quote_verified,
        **context,
    }
    if reply_body:
        result["reply_language"] = detect_language(reply_body)
        if result["reply_language"] == "zh":
            result["source_script"] = chinese_script(source_text)
            result["reply_script"] = chinese_script(reply_body)
        result["draft_fingerprint"] = fingerprint(
            {
                "thread_id": draft.get("thread_id"),
                "reply_message_id": draft.get("reply_message_id"),
                "quoted_original_message_id": draft.get("quoted_original_message_id"),
                "from": normalize_email(draft.get("from_address")),
                "to": normalize_email(draft.get("to")),
                "cc": draft.get("cc"),
                "subject": draft.get("subject"),
                "reply_body": reply_body,
                "mime_type": draft.get("persisted_mime_type") or draft.get("mime_type"),
                "rendered_body": persisted_body or body,
                "emphasis": as_string_list(draft.get("emphasis")),
            }
        )
    return result, 0 if not errors else 2


def audit_record(
    manifest: dict[str, Any], policy: dict[str, Any], validation: dict[str, Any]
) -> dict[str, Any]:
    draft = manifest.get("draft") if isinstance(manifest.get("draft"), dict) else {}
    issue_ids = [int(value) for value in as_list(manifest.get("issue_ids")) if str(value).isdigit()]
    pr_ids = [int(value) for value in as_list(manifest.get("pr_ids")) if str(value).isdigit()]
    feature_issue_ids = [
        int(value) for value in as_list(manifest.get("feature_issue_ids")) if str(value).isdigit()
    ]
    repository_action_ids = [str(value) for value in as_list(manifest.get("repository_action_ids"))]
    product_review_action_ids = as_string_list(manifest.get("product_review_action_ids"))
    capability_items = [
        {
            "key": item.get("key"),
            "status": item.get("status"),
            "repository_route": item.get("repository_route"),
            "checked_at": item.get("checked_at"),
            "evidence_ids": as_string_list(item.get("evidence_ids")),
            "issue_search_evidence_ids": as_string_list(item.get("issue_search_evidence_ids")),
            "pr_search_evidence_ids": as_string_list(item.get("pr_search_evidence_ids")),
            "guidance_fingerprint": fingerprint(str(item.get("customer_guidance") or "")),
        }
        for item in capability_checks(manifest)
    ]
    bug_version_items = [
        {
            "key": item.get("key"),
            "reported_version": item.get("reported_version"),
            "reported_platform": normalize_product_platform(item.get("reported_platform")),
            "problem_reproduced_on_reported_version": item.get(
                "problem_reproduced_on_reported_version"
            ),
            "fix_released_version": item.get("fix_released_version"),
            "fix_platform": normalize_product_platform(item.get("fix_platform")),
            "conclusion": item.get("conclusion"),
            "evidence_ids": as_string_list(item.get("evidence_ids")),
        }
        for item in bug_version_checks(manifest)
    ]
    follow_up = follow_up_data(manifest)
    search = repository_search(manifest)
    existing_review = (
        manifest.get("existing_draft_review")
        if isinstance(manifest.get("existing_draft_review"), dict)
        else {}
    )
    send = manifest.get("send") if isinstance(manifest.get("send"), dict) else {}
    follow_up_items = [
        {
            "tracking_key": item.get("tracking_key"),
            "kind": item.get("kind"),
            "category": item.get("category"),
            "status": item.get("status"),
            "next_check_at": item.get("next_check_at"),
            "issue_ids": [int(value) for value in as_list(item.get("issue_ids")) if str(value).isdigit()],
            "feature_issue_ids": [
                int(value) for value in as_list(item.get("feature_issue_ids")) if str(value).isdigit()
            ],
            "pr_ids": [int(value) for value in as_list(item.get("pr_ids")) if str(value).isdigit()],
        }
        for item in tracking_items(manifest)
    ]
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_id": manifest.get("run_id"),
        "thread_id": validation.get("thread_id"),
        "thread_fingerprint": validation.get("thread_fingerprint"),
        "source_message_id": validation.get("latest_customer_message_id"),
        "source_message_fingerprint": validation.get("source_message_fingerprint"),
        "latest_message_id": validation.get("latest_message_id"),
        "latest_sender_domain": validation.get("latest_sender_domain"),
        "related_staff_reply_message_ids": validation.get("related_staff_reply_message_ids", []),
        "related_staff_reply_thread_ids": validation.get("related_staff_reply_thread_ids", []),
        "related_staff_reply_evidence_fingerprint": validation.get(
            "related_staff_reply_evidence_fingerprint"
        ),
        "decision": manifest.get("decision"),
        "workflow_kind": workflow_kind(manifest),
        "draft_disposition": manifest.get("draft_disposition", "kept" if draft else "none"),
        "category": manifest.get("category"),
        "source_language": validation.get("source_language"),
        "reply_language": validation.get("reply_language"),
        "repository_route": manifest.get("repository_route"),
        "issue_ids": issue_ids,
        "pr_ids": pr_ids,
        "feature_issue_ids": feature_issue_ids,
        "repository_action_ids": repository_action_ids,
        "product_review_action_ids": product_review_action_ids,
        "capability_checks": capability_items,
        "capability_evidence_fingerprint": fingerprint(capability_items),
        "bug_version_checks": bug_version_items,
        "bug_version_evidence_fingerprint": fingerprint(bug_version_items),
        "repository_search": {
            "checked_at": search.get("checked_at"),
            "issue_evidence_ids": as_string_list(search.get("issue_evidence_ids")),
            "pr_evidence_ids": as_string_list(search.get("pr_evidence_ids")),
        },
        "existing_draft_review": {
            "status": existing_review.get("status"),
            "action": existing_review.get("action"),
            "reviewed_at": existing_review.get("reviewed_at"),
            "evidence_ids": as_string_list(existing_review.get("evidence_ids")),
            "draft_ids": as_string_list(existing_review.get("draft_ids")),
            "draft_fingerprints": as_string_list(existing_review.get("draft_fingerprints")),
        },
        "repository_evidence_fingerprint": fingerprint(
            {
                "route": manifest.get("repository_route"),
                "issues": issue_ids,
                "prs": pr_ids,
                "feature_issues": feature_issue_ids,
                "actions": repository_action_ids,
                "product_review_actions": product_review_action_ids,
                "release_evidence": as_string_list(follow_up.get("release_evidence_ids")),
            }
        ),
        "tracking_key": follow_up.get("tracking_key"),
        "tracking_status": follow_up.get("status"),
        "next_check_at": follow_up.get("next_check_at"),
        "tracking_items": follow_up_items,
        "repository_checked_at": follow_up.get("repository_checked_at"),
        "released_version": follow_up.get("released_version"),
        "release_evidence_ids": as_string_list(follow_up.get("release_evidence_ids")),
        "notification_key": follow_up.get("notification_key"),
        "prior_audit_record_fingerprint": follow_up.get("prior_audit_record_fingerprint"),
        "draft_id": draft.get("draft_id"),
        "draft_message_id": draft.get("message_id"),
        "reply_message_id": draft.get("reply_message_id"),
        "quoted_original_message_id": validation.get("quoted_original_message_id"),
        "quoted_original_verified": validation.get("quoted_original_verified"),
        "draft_fingerprint": validation.get("draft_fingerprint"),
        "send_status": send.get("status"),
        "sent_message_id": send.get("message_id"),
        "sent_at": send.get("sent_at"),
        "policy_fingerprint": fingerprint(policy),
        "checks": validation.get("validation"),
    }


def auto_send_errors(manifest: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    """Return deterministic reasons a validated reply may not be sent automatically."""
    errors: list[str] = []
    mode = str(policy.get("reply_mode") or "")
    category = str(manifest.get("category") or "")
    decision = str(manifest.get("decision") or "")
    draft = manifest.get("draft") if isinstance(manifest.get("draft"), dict) else {}
    automation = policy.get("automation") if isinstance(policy.get("automation"), dict) else {}
    allowed = automation.get("auto_send_categories")
    allowed = allowed if isinstance(allowed, list) else []
    always_review = automation.get("always_review_categories")
    always_review = always_review if isinstance(always_review, list) else []

    if mode != "guarded-auto":
        errors.append("automatic send requires policy reply_mode=guarded-auto")
    if category not in allowed:
        errors.append(f"category {category!r} is not on the auto-send allowlist")
    if category in always_review:
        errors.append(f"category {category!r} is always-review and cannot be auto-sent")
    if decision != "draft":
        errors.append("automatic send requires decision=draft")
    if not str(draft.get("draft_id") or "").strip():
        errors.append("automatic send requires the validated Gmail draft_id")
    thread = manifest.get("thread") if isinstance(manifest.get("thread"), dict) else {}
    if as_list(thread.get("existing_drafts")) or draft.get("operation") == "update":
        errors.append("pre-existing Gmail drafts require human review and cannot be auto-sent")
    return errors


def append_audit(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def resolve_intake_db_path(policy: dict[str, Any]) -> Path | None:
    raw = policy.get("automation", {}).get("intake_database_path")
    return Path(raw) if isinstance(raw, str) and raw.strip() else None


def load_intake_db_module():
    module_path = Path(__file__).with_name("intake_db.py")
    spec = importlib.util.spec_from_file_location("filo_intake_db", module_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load intake database helper: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if module.SCHEMA_VERSION != INTAKE_DB_SCHEMA_VERSION:
        raise ValueError("intake database helper schema version is incompatible")
    return module


def sync_intake_database(
    manifest: dict[str, Any], policy: dict[str, Any], audit_record: dict[str, Any]
) -> dict[str, Any] | None:
    """Index a successfully audited intake without replacing the audit JSONL."""
    database_path = resolve_intake_db_path(policy)
    if database_path is None:
        return None
    module = load_intake_db_module()
    db = module.init_db(database_path)
    thread = manifest.get("thread")
    thread = thread if isinstance(thread, dict) else {}
    sender = {}
    reply_message_id = audit_record.get("source_message_id")
    for message in thread.get("messages") or []:
        if isinstance(message, dict) and message.get("id") == reply_message_id:
            sender["sender_email"] = normalize_email(message.get("from"))
            sender["sender_name"] = str(message.get("from") or "").split("<", 1)[0].strip()
            break
    return module.import_support_record(
        db,
        {
            **audit_record,
            "thread_id": audit_record.get("thread_id"),
            "source_message_id": audit_record.get("source_message_id"),
            "sender_name": sender.get("sender_name"),
            "sender_email": sender.get("sender_email"),
            "repository_route": audit_record.get("repository_route"),
        },
    )


def resolve_audit_path(policy: dict[str, Any], override: Path | None) -> Path:
    if override:
        return override
    raw = policy.get("automation", {}).get("audit_log_path")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("automation.audit_log_path is required")
    return Path(raw)


def scan_window_errors(scan: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    """Validate the run-level intake scan manifest against the deterministic cursor.

    Fail-closed checks for the Gmail incremental scan: the window must be epoch
    seconds anchored on intake_db's cursor (never self-invented date strings),
    both Inbox and Spam searches must be reported with the exact query text,
    and any candidate skipped as already indexed must carry its exact-match
    evidence. This blocks the "run reported success but never searched" mode.
    """
    errors: list[str] = []

    run_id = str(scan.get("run_id") or "").strip()
    if not run_id:
        errors.append("run_id is required")

    window = scan.get("window")
    window = window if isinstance(window, dict) else {}
    try:
        start = int(window.get("start_epoch"))
        end = int(window.get("end_epoch"))
    except (TypeError, ValueError):
        start = end = None
        errors.append("window.start_epoch and window.end_epoch must be epoch-second integers")
    if start is not None and end is not None:
        if start < 0 or end <= start:
            errors.append("window must satisfy 0 <= start_epoch < end_epoch")
        if end - start > SCAN_WINDOW_MAX_SPAN_SECONDS:
            errors.append(
                f"window span must not exceed {SCAN_WINDOW_MAX_SPAN_SECONDS} seconds; "
                "re-check the cursor instead of widening the window manually"
            )

    cursor_evidence = scan.get("cursor_evidence")
    cursor_evidence = cursor_evidence if isinstance(cursor_evidence, dict) else {}
    if not cursor_evidence:
        errors.append("cursor_evidence must embed the intake_db cursor output used for this scan")
    cursor_start = cursor_evidence.get("window_start_epoch")
    if start is not None and isinstance(cursor_start, int):
        if start > cursor_start + SCAN_WINDOW_TOLERANCE_SECONDS:
            errors.append(
                "window.start_epoch starts later than the deterministic cursor window; "
                "use the cursor queries verbatim"
            )
    elif start is not None:
        errors.append("cursor_evidence.window_start_epoch must be an epoch-second integer")

    database_path = resolve_intake_db_path(policy)
    if database_path is None:
        errors.append("automation.intake_database_path is required to cross-check the scan anchor")
    else:
        module = load_intake_db_module()
        db = module.init_db(database_path)
        anchor = module.scan_anchor(db)
        if start is not None and anchor["epoch"] is not None:
            if start > int(anchor["epoch"]) + SCAN_WINDOW_TOLERANCE_SECONDS:
                errors.append(
                    "window.start_epoch leaves a gap after the latest indexed scan boundary "
                    f"({anchor['value']}); the scan window must start at or before it"
                )

    searches = scan.get("searches")
    searches = searches if isinstance(searches, list) else []
    if not searches:
        errors.append("searches must list one executed Gmail search per location (inbox and spam)")
    cursor_queries = cursor_evidence.get("gmail_queries")
    cursor_queries = cursor_queries if isinstance(cursor_queries, dict) else {}
    if not cursor_queries:
        errors.append(
            "cursor_evidence.gmail_queries must embed the cursor queries used for this scan"
        )
    seen_locations: set[str] = set()
    for entry in searches:
        entry = entry if isinstance(entry, dict) else {}
        location = str(entry.get("location") or "").strip()
        if location not in SCAN_LOCATIONS:
            errors.append(f"searches location must be one of {list(SCAN_LOCATIONS)}, got {location!r}")
            continue
        if location in seen_locations:
            errors.append(f"searches contains duplicate location {location!r}")
        seen_locations.add(location)
        query = str(entry.get("query") or "")
        if not query:
            errors.append(f"searches[{location}].query is required")
            continue
        if SCAN_DATE_WINDOW_RE.search(query):
            errors.append(
                f"searches[{location}].query uses date-based after:/before:, which Gmail "
                "interprets in the account timezone; epoch seconds are required"
            )
        if start is not None and end is not None:
            if f"after:{start}" not in query or f"before:{end}" not in query:
                errors.append(
                    f"searches[{location}].query must contain after:{start} before:{end} "
                    "matching the declared window"
                )
        if f"in:{location}" not in query:
            errors.append(f"searches[{location}].query must contain in:{location}")
        expected_query = str(cursor_queries.get(location) or "")
        if expected_query and query != expected_query:
            errors.append(
                f"searches[{location}].query must match cursor_evidence.gmail_queries.{location} "
                "verbatim; channel terms may not be dropped or rewritten"
            )
        result_count = entry.get("result_count")
        if not isinstance(result_count, int) or result_count < 0:
            errors.append(f"searches[{location}].result_count must be a non-negative integer")
    for location in SCAN_LOCATIONS:
        if location not in seen_locations:
            errors.append(f"searches is missing the required {location} search")

    candidates = scan.get("candidates")
    candidates = candidates if isinstance(candidates, list) else []
    for index, candidate in enumerate(candidates):
        candidate = candidate if isinstance(candidate, dict) else {}
        message_id = str(candidate.get("message_id") or "").strip()
        if not message_id:
            errors.append(f"candidates[{index}].message_id is required")
        disposition = str(candidate.get("disposition") or "").strip()
        if disposition not in SCAN_CANDIDATE_DISPOSITIONS:
            errors.append(
                f"candidates[{index}].disposition must be one of "
                f"{sorted(SCAN_CANDIDATE_DISPOSITIONS)}, got {disposition!r}"
            )
        if disposition == "skipped-already-indexed":
            exact = candidate.get("exact_match")
            exact = exact if isinstance(exact, dict) else {}
            if not exact:
                errors.append(
                    f"candidates[{index}] skipped as already indexed without exact_match evidence"
                )
            elif str(exact.get("external_message_id") or "") != message_id:
                errors.append(
                    f"candidates[{index}].exact_match.external_message_id must equal message_id"
                )
            elif str(exact.get("source_type") or "").strip() not in SCAN_SKIP_SOURCE_TYPES:
                errors.append(
                    f"candidates[{index}] may only be skipped on a support-audit match "
                    f"(source_type {sorted(SCAN_SKIP_SOURCE_TYPES)}); a triage-indexed match "
                    "(gmail/feishu) is a recall lead, not proof this workflow replied"
                )

    recorded = scan.get("recorded_scan")
    if recorded is not None:
        recorded = recorded if isinstance(recorded, dict) else {}
        if str(recorded.get("run_id") or "") != run_id:
            errors.append("recorded_scan.run_id must match the scan run_id")
        if start is not None and recorded.get("window_start_epoch") != start:
            errors.append("recorded_scan.window_start_epoch must match window.start_epoch")
        if end is not None and recorded.get("window_end_epoch") != end:
            errors.append("recorded_scan.window_end_epoch must match window.end_epoch")

    return errors


def validate_scan(scan: dict[str, Any], policy: dict[str, Any]) -> tuple[dict[str, Any], int]:
    errors = scan_window_errors(scan, policy)
    searches = scan.get("searches")
    searches = searches if isinstance(searches, list) else []
    candidates = scan.get("candidates")
    candidates = candidates if isinstance(candidates, list) else []
    result = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "run_id": scan.get("run_id"),
        "validation": {"passed": not errors, "errors": errors},
        "search_count": len(searches),
        "candidate_count": len(candidates),
    }
    return result, 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "fingerprint-existing-drafts",
            "preflight",
            "validate-scan",
            "validate",
            "finalize",
            "authorize-send",
            "record-send",
            "record-drop",
        ),
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--audit-log", type=Path)
    args = parser.parse_args()

    try:
        manifest = read_json(args.manifest)
        policy = load_policy(args.policy)
        if args.command == "fingerprint-existing-drafts":
            result = {
                "schema_version": AUDIT_SCHEMA_VERSION,
                "existing_drafts": [
                    {
                        "draft_id": str(item.get("draft_id") or item.get("id") or ""),
                        "draft_fingerprint": existing_draft_fingerprint(item),
                    }
                    for item in existing_drafts(manifest)
                ],
            }
            exit_code = 0 if result["existing_drafts"] else 2
        elif args.command == "preflight":
            result, exit_code = preflight(manifest, policy)
        elif args.command == "validate-scan":
            result, exit_code = validate_scan(manifest, policy)
        elif args.command == "authorize-send":
            result, exit_code = validate_manifest(
                manifest, policy, require_persisted_draft=True
            )
            if exit_code == 0:
                send_errors = auto_send_errors(manifest, policy)
                result["send_authorization"] = {
                    "allowed": not send_errors,
                    "errors": send_errors,
                }
                if send_errors:
                    result["validation"]["passed"] = False
                    result["validation"]["errors"].extend(send_errors)
                    exit_code = 2
        elif args.command == "record-send":
            result, exit_code = validate_manifest(
                manifest, policy, require_persisted_draft=True
            )
            send = manifest.get("send") if isinstance(manifest.get("send"), dict) else {}
            send_errors = auto_send_errors(manifest, policy)
            if send.get("confirmed") is not True:
                send_errors.append("send.confirmed must be true after Gmail confirms delivery")
            if not str(send.get("message_id") or "").strip():
                send_errors.append("send.message_id is required after Gmail confirms delivery")
            if not str(send.get("sent_at") or "").strip():
                send_errors.append("send.sent_at is required after Gmail confirms delivery")
            if send_errors:
                result["validation"]["passed"] = False
                result["validation"]["errors"].extend(send_errors)
                exit_code = 2
            else:
                manifest["draft_disposition"] = "sent"
                path = resolve_audit_path(policy, args.audit_log)
                record = audit_record(manifest, policy, result)
                append_audit(path, record)
                intake_result = sync_intake_database(manifest, policy, record)
                result["audit"] = {
                    "path": str(path),
                    "record_fingerprint": fingerprint(record),
                }
                if intake_result is not None:
                    result["intake_database"] = intake_result
        else:
            result, exit_code = validate_manifest(
                manifest, policy, require_persisted_draft=args.command in {"finalize", "record-drop"}
            )
            if args.command == "finalize" and exit_code == 0:
                path = resolve_audit_path(policy, args.audit_log)
                record = audit_record(manifest, policy, result)
                append_audit(path, record)
                intake_result = sync_intake_database(manifest, policy, record)
                result["audit"] = {
                    "path": str(path),
                    "record_fingerprint": fingerprint(record),
                }
                if intake_result is not None:
                    result["intake_database"] = intake_result
            elif args.command == "record-drop":
                drop = manifest.get("drop")
                drop = drop if isinstance(drop, dict) else {}
                draft = manifest.get("draft")
                draft = draft if isinstance(draft, dict) else {}
                drop_errors: list[str] = []
                if draft.get("operation") == "update":
                    drop_errors.append("an existing draft update must not be moved to Trash")
                if drop.get("confirmed") is not True:
                    drop_errors.append("drop.confirmed must be true after the draft message is moved to Trash")
                if str(drop.get("message_id") or "") != str(draft.get("message_id") or ""):
                    drop_errors.append("drop.message_id must match draft.message_id")
                if not str(drop.get("reason") or "").strip():
                    drop_errors.append("drop.reason is required")
                if drop_errors:
                    result["validation"]["passed"] = False
                    result["validation"]["errors"].extend(drop_errors)
                    exit_code = 2
                else:
                    manifest["draft_disposition"] = "dropped"
                    path = resolve_audit_path(policy, args.audit_log)
                    record = audit_record(manifest, policy, result)
                    record["decision"] = "dropped"
                    record["drop"] = {
                        "message_id": drop.get("message_id"),
                        "reason": drop.get("reason"),
                        "confirmed": True,
                    }
                    append_audit(path, record)
                    result["audit"] = {
                        "path": str(path),
                        "record_fingerprint": fingerprint(record),
                    }
                    exit_code = 0
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return exit_code
    except ValueError as exc:
        print(json.dumps({"schema_version": AUDIT_SCHEMA_VERSION, "error": str(exc)}, ensure_ascii=False))
        return 2
    except OSError as exc:
        print(json.dumps({"schema_version": AUDIT_SCHEMA_VERSION, "error": f"audit write failed: {exc}"}, ensure_ascii=False))
        return 3


if __name__ == "__main__":
    sys.exit(main())
