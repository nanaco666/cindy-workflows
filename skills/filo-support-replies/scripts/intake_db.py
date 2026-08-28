#!/usr/bin/env python3
"""Create and update the local SQLite index for Filo intake workflows.

The database is a queryable index beside the authoritative audit JSONL and CAS
state files. Inputs are identifier/status/summary records only; customer bodies
and credentials must never be written here.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 2
TICKET_RE = re.compile(r"^([^#/\s]+/[^#\s]+)#(\d+)$")
SCAN_SOURCE_TYPE_ALIASES = {
    # Gmail messages are indexed as "email" (support audit import) and "gmail"
    # (feedback decision import); lookups must treat both spellings as one pool.
    "email": ("email", "gmail"),
    "gmail": ("email", "gmail"),
}
DEFAULT_SCAN_OVERLAP_SECONDS = 2 * 60 * 60
DEFAULT_SCAN_BOOTSTRAP_LOOKBACK_SECONDS = 72 * 60 * 60
DEFAULT_SCAN_CHANNELS = tuple(
    item.strip()
    for item in os.environ.get(
        "CINDY_SUPPORT_SCAN_CHANNELS", "to:support@example.invalid|from:feedback@example.invalid"
    ).split("|")
    if item.strip()
)


@dataclass(frozen=True)
class TicketRef:
    repository: str
    number: int
    kind: str
    relationship: str


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    return db


def init_db(path: Path) -> sqlite3.Connection:
    db = connect(path)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_metadata (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS people (
          person_id INTEGER PRIMARY KEY,
          canonical_name TEXT NOT NULL,
          primary_email TEXT UNIQUE,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_identities (
          source_identity_id INTEGER PRIMARY KEY,
          person_id INTEGER NOT NULL REFERENCES people(person_id),
          source_type TEXT NOT NULL,
          source_user_id TEXT NOT NULL,
          display_name TEXT,
          email TEXT,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          UNIQUE(source_type, source_user_id)
        );
        CREATE INDEX IF NOT EXISTS source_identities_email_idx ON source_identities(email);
        CREATE TABLE IF NOT EXISTS feedback_items (
          feedback_id INTEGER PRIMARY KEY,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          problem_summary TEXT NOT NULL,
          category TEXT NOT NULL,
          current_status TEXT NOT NULL,
          severity TEXT,
          content_fingerprint TEXT UNIQUE
        );
        CREATE INDEX IF NOT EXISTS feedback_items_status_idx
          ON feedback_items(current_status, last_seen_at DESC);
        CREATE INDEX IF NOT EXISTS feedback_items_category_idx
          ON feedback_items(category, last_seen_at DESC);
        CREATE VIRTUAL TABLE IF NOT EXISTS feedback_items_fts USING fts5(
          problem_summary,
          content='feedback_items',
          content_rowid='feedback_id',
          tokenize='unicode61'
        );
        CREATE TABLE IF NOT EXISTS source_messages (
          source_message_id INTEGER PRIMARY KEY,
          feedback_id INTEGER NOT NULL REFERENCES feedback_items(feedback_id),
          source_type TEXT NOT NULL,
          external_message_id TEXT NOT NULL,
          thread_id TEXT,
          occurred_at TEXT,
          sender_person_id INTEGER REFERENCES people(person_id),
          summary TEXT,
          content_fingerprint TEXT,
          first_recorded_at TEXT NOT NULL,
          last_updated_at TEXT NOT NULL,
          UNIQUE(source_type, external_message_id)
        );
        CREATE INDEX IF NOT EXISTS source_messages_time_idx ON source_messages(occurred_at DESC);
        CREATE INDEX IF NOT EXISTS source_messages_person_idx
          ON source_messages(sender_person_id, occurred_at DESC);
        CREATE INDEX IF NOT EXISTS source_messages_feedback_idx
          ON source_messages(feedback_id, occurred_at DESC);
        CREATE TABLE IF NOT EXISTS tickets (
          ticket_id INTEGER PRIMARY KEY,
          repository TEXT NOT NULL,
          number INTEGER NOT NULL,
          kind TEXT NOT NULL,
          state TEXT,
          title TEXT,
          last_checked_at TEXT,
          released_version TEXT,
          first_recorded_at TEXT NOT NULL,
          last_updated_at TEXT NOT NULL,
          UNIQUE(repository, number, kind)
        );
        CREATE INDEX IF NOT EXISTS tickets_state_idx ON tickets(state, last_updated_at DESC);
        CREATE TABLE IF NOT EXISTS feedback_tickets (
          feedback_id INTEGER NOT NULL REFERENCES feedback_items(feedback_id),
          ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id),
          relationship TEXT NOT NULL,
          first_linked_at TEXT NOT NULL,
          last_confirmed_at TEXT NOT NULL,
          PRIMARY KEY(feedback_id, ticket_id, relationship)
        );
        CREATE TABLE IF NOT EXISTS engagement_events (
          engagement_event_id INTEGER PRIMARY KEY,
          person_id INTEGER NOT NULL REFERENCES people(person_id),
          occurred_at TEXT NOT NULL,
          event_type TEXT NOT NULL,
          points INTEGER NOT NULL,
          source_type TEXT NOT NULL,
          external_message_id TEXT NOT NULL,
          UNIQUE(person_id, event_type, source_type, external_message_id)
        );
        CREATE INDEX IF NOT EXISTS engagement_events_time_idx ON engagement_events(occurred_at DESC);
        CREATE TABLE IF NOT EXISTS scan_runs (
          scan_run_id INTEGER PRIMARY KEY,
          run_id TEXT NOT NULL,
          workflow TEXT NOT NULL DEFAULT 'support-replies',
          window_start_epoch INTEGER NOT NULL,
          window_end_epoch INTEGER NOT NULL,
          window_start TEXT NOT NULL,
          window_end TEXT NOT NULL,
          inbox_hits INTEGER NOT NULL DEFAULT 0,
          spam_hits INTEGER NOT NULL DEFAULT 0,
          recorded_at TEXT NOT NULL,
          UNIQUE(run_id, window_start_epoch)
        );
        CREATE INDEX IF NOT EXISTS scan_runs_end_idx ON scan_runs(window_end_epoch DESC);
        CREATE VIEW IF NOT EXISTS person_engagement AS
        SELECT people.person_id, people.canonical_name, people.primary_email,
          COALESCE(SUM(engagement_events.points), 0) AS points,
          COUNT(engagement_events.engagement_event_id) AS scored_events
        FROM people
        LEFT JOIN engagement_events ON engagement_events.person_id = people.person_id
        GROUP BY people.person_id;
        CREATE VIEW IF NOT EXISTS person_levels AS
        SELECT person_id, canonical_name, primary_email, points,
          CASE
            WHEN points >= 50 THEN 'advocate'
            WHEN points >= 20 THEN 'active'
            WHEN points >= 5 THEN 'reporter'
            ELSE 'observer'
          END AS level
        FROM person_engagement;
        CREATE TRIGGER IF NOT EXISTS feedback_items_ai AFTER INSERT ON feedback_items BEGIN
          INSERT INTO feedback_items_fts(rowid, problem_summary) VALUES (new.feedback_id, new.problem_summary);
        END;
        CREATE TRIGGER IF NOT EXISTS feedback_items_ad AFTER DELETE ON feedback_items BEGIN
          INSERT INTO feedback_items_fts(feedback_items_fts, rowid, problem_summary)
          VALUES ('delete', old.feedback_id, old.problem_summary);
        END;
        CREATE TRIGGER IF NOT EXISTS feedback_items_au AFTER UPDATE OF problem_summary ON feedback_items BEGIN
          INSERT INTO feedback_items_fts(feedback_items_fts, rowid, problem_summary)
          VALUES ('delete', old.feedback_id, old.problem_summary);
          INSERT INTO feedback_items_fts(rowid, problem_summary) VALUES (new.feedback_id, new.problem_summary);
        END;
        """
    )
    db.execute(
        "INSERT OR REPLACE INTO schema_metadata(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    db.commit()
    return db


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_person(db: sqlite3.Connection, record: dict[str, Any]) -> int | None:
    name = str(
        record.get("sender_name")
        or record.get("senderName")
        or record.get("display_name")
        or ""
    ).strip()
    email = str(
        record.get("sender_email")
        or record.get("senderEmail")
        or record.get("email")
        or ""
    ).strip().lower() or None
    source_type = str(record.get("source_type") or record.get("sourceType") or "other").strip()
    source_user_id = str(record.get("source_user_id") or email or name or "").strip()
    if not name and not email:
        return None
    if not name:
        name = email or source_user_id
    timestamp = str(record.get("occurred_at") or now())
    person = db.execute("SELECT person_id FROM people WHERE primary_email IS ?", (email,)).fetchone()
    if person:
        person_id = int(person["person_id"])
    else:
        cursor = db.execute(
            "INSERT INTO people(canonical_name, primary_email, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (name, email, timestamp, timestamp),
        )
        person_id = int(cursor.lastrowid)
    if source_user_id:
        db.execute(
            """
            INSERT INTO source_identities(
              person_id, source_type, source_user_id, display_name, email,
              first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_type, source_user_id) DO UPDATE SET
              person_id=excluded.person_id,
              display_name=COALESCE(excluded.display_name, source_identities.display_name),
              email=COALESCE(excluded.email, source_identities.email),
              last_seen_at=excluded.last_seen_at
            """,
            (person_id, source_type, source_user_id, name, email, timestamp, timestamp),
        )
    return person_id


def canonical_repository(record: dict[str, Any]) -> str:
    route = str(record.get("repository_route") or "").strip()
    configured = record.get("repository_routes")
    if isinstance(configured, dict):
        candidate = configured.get(route) or configured.get("frontend")
        if isinstance(candidate, dict):
            candidate = candidate.get("repository")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return {
        "frontend": os.environ.get("CINDY_FRONTEND_REPOSITORY", "OWNER/FRONTEND_REPO"),
        "server": os.environ.get("CINDY_SERVER_REPOSITORY", "OWNER/SERVER_REPO"),
        "mixed": os.environ.get("CINDY_FRONTEND_REPOSITORY", "OWNER/FRONTEND_REPO"),
    }.get(route, os.environ.get("CINDY_FRONTEND_REPOSITORY", "OWNER/FRONTEND_REPO"))


def ticket_refs(record: dict[str, Any]) -> list[TicketRef]:
    refs: list[TicketRef] = []
    repository = str(record.get("repository") or canonical_repository(record))
    for field, kind, relationship in (
        ("issue_ids", "issue", "reported"),
        ("feature_issue_ids", "issue", "reported"),
        ("pr_ids", "pr", "fix_pr"),
    ):
        for value in record.get(field) or []:
            if str(value).isdigit():
                refs.append(TicketRef(repository, int(value), kind, relationship))
    for field, default_kind, relationship in (
        ("issue", "issue", "reported"),
        ("pr", "pr", "fix_pr"),
        ("carrier", "issue", "reported"),
    ):
        match = TICKET_RE.fullmatch(str(record.get(field) or "").strip())
        if match:
            refs.append(TicketRef(match.group(1), int(match.group(2)), default_kind, relationship))
    for field, kind, relationship in (("carriers", "issue", "reported"), ("prs", "pr", "fix_pr")):
        for value in record.get(field) or []:
            match = TICKET_RE.fullmatch(str(value).strip())
            if match:
                refs.append(TicketRef(match.group(1), int(match.group(2)), kind, relationship))
    return refs


def normalized_ticket_state(record: dict[str, Any]) -> str | None:
    raw_state = (
        record.get("tracking_status")
        or record.get("release_status")
        or record.get("releaseStatus")
        or record.get("ticket_state")
        or record.get("issueState")
    )
    normalized = str(raw_state or "").strip().lower()
    return {
        "merged-unreleased": "merged_waiting_release",
        "merged_waiting_release": "merged_waiting_release",
        "being_handled": "being_handled",
        "recorded": "recorded",
        "open": "open",
        "closed": "closed",
    }.get(normalized)


def upsert_ticket(
    db: sqlite3.Connection, ref: TicketRef, timestamp: str, record: dict[str, Any]
) -> int:
    state = normalized_ticket_state(record)
    db.execute(
        """
        INSERT INTO tickets(
          repository, number, kind, state, title, last_checked_at,
          released_version, first_recorded_at, last_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repository, number, kind) DO UPDATE SET
          state=COALESCE(excluded.state, tickets.state),
          title=COALESCE(excluded.title, tickets.title),
          last_checked_at=COALESCE(excluded.last_checked_at, tickets.last_checked_at),
          released_version=COALESCE(excluded.released_version, tickets.released_version),
          last_updated_at=excluded.last_updated_at
        """,
        (ref.repository, ref.number, ref.kind, state, None, timestamp, None, timestamp, timestamp),
    )
    row = db.execute(
        "SELECT ticket_id FROM tickets WHERE repository=? AND number=? AND kind=?",
        (ref.repository, ref.number, ref.kind),
    ).fetchone()
    return int(row["ticket_id"])


def ingest(db: sqlite3.Connection, record: dict[str, Any]) -> dict[str, Any]:
    timestamp = str(record.get("timestamp") or record.get("observed_at") or now())
    source_type = str(record.get("source_type") or record.get("sourceType") or "email").strip()
    external_id = str(record.get("source_message_id") or record.get("external_message_id") or "").strip()
    if not external_id:
        raise ValueError("record requires source_message_id or external_message_id")
    fingerprint = record.get("content_fingerprint") or record.get("source_message_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        raise ValueError("record requires content_fingerprint")
    summary = str(record.get("problem_summary") or record.get("reason") or record.get("category") or "").strip()
    if not summary:
        raise ValueError("record requires problem_summary")
    category = str(record.get("category") or record.get("decision") or "uncategorized")
    status = str(record.get("current_status") or record.get("tracking_status") or record.get("decision") or "recorded")

    person_id = ensure_person(db, record)
    item = db.execute(
        "SELECT feedback_id FROM feedback_items WHERE content_fingerprint=?", (fingerprint,)
    ).fetchone()
    if item:
        feedback_id = int(item["feedback_id"])
        db.execute(
            """UPDATE feedback_items SET last_seen_at=?, problem_summary=?,
               category=?, current_status=COALESCE(?, current_status) WHERE feedback_id=?""",
            (timestamp, summary, category, status, feedback_id),
        )
    else:
        cursor = db.execute(
            """INSERT INTO feedback_items(
                 first_seen_at, last_seen_at, problem_summary, category,
                 current_status, severity, content_fingerprint
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, timestamp, summary, category, status, record.get("severity"), fingerprint),
        )
        feedback_id = int(cursor.lastrowid)

    db.execute(
        """
        INSERT INTO source_messages(
          feedback_id, source_type, external_message_id, thread_id, occurred_at,
          sender_person_id, summary, content_fingerprint,
          first_recorded_at, last_updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_type, external_message_id) DO UPDATE SET
          feedback_id=excluded.feedback_id,
          thread_id=COALESCE(excluded.thread_id, source_messages.thread_id),
          occurred_at=COALESCE(excluded.occurred_at, source_messages.occurred_at),
          sender_person_id=COALESCE(excluded.sender_person_id, source_messages.sender_person_id),
          summary=excluded.summary,
          content_fingerprint=excluded.content_fingerprint,
          last_updated_at=excluded.last_updated_at
        """,
        (
            feedback_id,
            source_type,
            external_id,
            record.get("thread_id"),
            record.get("occurred_at") or timestamp,
            person_id,
            summary,
            fingerprint,
            timestamp,
            timestamp,
        ),
    )
    tracking_items = record.get("tracking_items")
    ticket_records: list[tuple[TicketRef, dict[str, Any]]] = [
        (ref, record) for ref in ticket_refs(record)
    ]
    if isinstance(tracking_items, list):
        for item in tracking_items:
            if not isinstance(item, dict):
                continue
            ticket_records.extend((ref, item) for ref in ticket_refs(item))
    for ref, source_record in ticket_records:
        ticket_id = upsert_ticket(db, ref, timestamp, source_record)
        db.execute(
            """INSERT INTO feedback_tickets(
                 feedback_id, ticket_id, relationship, first_linked_at, last_confirmed_at
               ) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(feedback_id, ticket_id, relationship) DO UPDATE SET
                 last_confirmed_at=excluded.last_confirmed_at""",
            (feedback_id, ticket_id, ref.relationship, timestamp, timestamp),
        )
    points = int(record.get("engagement_points") or record.get("engagementPoints") or 0)
    if person_id and points:
        db.execute(
            """INSERT INTO engagement_events(
                 person_id, occurred_at, event_type, points, source_type, external_message_id
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(person_id, event_type, source_type, external_message_id) DO NOTHING""",
            (person_id, record.get("occurred_at") or timestamp, "inbound_message", points, source_type, external_id),
        )
    db.commit()
    return {
        "feedback_id": feedback_id,
        "source_type": source_type,
        "external_message_id": external_id,
        "ticket_refs": [f"{ref.repository}#{ref.number}:{ref.kind}" for ref in ticket_refs(record)],
    }


def import_support_record(db: sqlite3.Connection, record: dict[str, Any]) -> dict[str, Any]:
    if record.get("workflow_kind") not in {"intake", "resolution_follow_up", None}:
        return {"skipped": str(record.get("workflow_kind"))}
    if record.get("decision") == "no-reply" and not ticket_refs(record):
        return {"skipped": "no-reply-without-ticket"}
    enriched = dict(record)
    enriched.update(
        {
            "source_type": "email",
            "thread_id": record.get("thread_id"),
            "content_fingerprint": record.get("source_message_fingerprint"),
            "problem_summary": str(record.get("category") or "Filo intake"),
            "current_status": record.get("tracking_status") or record.get("decision"),
            "engagement_points": 1 if record.get("workflow_kind") == "intake" else 0,
        }
    )
    return ingest(db, enriched)


def import_support_audit(db: sqlite3.Connection, path: Path) -> dict[str, Any]:
    imported = 0
    skipped = 0
    errors: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("record must be an object")
                outcome = import_support_record(db, value)
                if "skipped" in outcome:
                    skipped += 1
                else:
                    imported += 1
            except (ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
                errors.append(f"line {line_number}: {exc}")
    return {"imported": imported, "skipped": skipped, "errors": errors}


def import_feedback_state(db: sqlite3.Connection, path: Path) -> dict[str, Any]:
    state = json.loads(path.read_text(encoding="utf-8"))
    decisions = state.get("reportedDecisionFingerprints")
    if not isinstance(decisions, dict):
        raise ValueError("state.reportedDecisionFingerprints must be an object")
    imported = 0
    errors: list[str] = []
    for decision_fingerprint, decision in decisions.items():
        if not isinstance(decision, dict):
            errors.append(f"{decision_fingerprint}: decision must be an object")
            continue
        try:
            value = dict(decision)
            source_message_ids = value.get("sourceMessageIds")
            source_ids = (
                [str(value.get("sourceMessageId") or "").strip()]
                if str(value.get("sourceMessageId") or "").strip()
                else [str(item).strip() for item in source_message_ids or [] if str(item).strip()]
            )
            if not source_ids:
                errors.append(f"{decision_fingerprint}: sourceMessageId is missing")
                continue
            if not str(value.get("reason") or "").strip():
                errors.append(f"{decision_fingerprint}: reason is missing")
                continue
            value["content_fingerprint"] = f"feedback-decision:{decision_fingerprint}"
            value["source_type"] = value.get("source_type") or value.get("sourceType") or "gmail"
            value["external_message_id"] = source_ids[0]
            value["occurred_at"] = value.get("observedAt")
            ingest(db, value)
            imported += 1
        except (ValueError, sqlite3.Error) as exc:
            errors.append(f"{decision_fingerprint}: {exc}")
    return {"imported": imported, "skipped": len(errors), "errors": errors}


def report(db: sqlite3.Connection) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "people": db.execute("SELECT COUNT(*) FROM people").fetchone()[0],
        "feedback_items": db.execute("SELECT COUNT(*) FROM feedback_items").fetchone()[0],
        "source_messages": db.execute("SELECT COUNT(*) FROM source_messages").fetchone()[0],
        "tickets": db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0],
        "feedback_tickets": db.execute("SELECT COUNT(*) FROM feedback_tickets").fetchone()[0],
        "engagement_events": db.execute("SELECT COUNT(*) FROM engagement_events").fetchone()[0],
        "scan_runs": db.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0],
    }


def iso_to_epoch(value: Any) -> int | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def epoch_to_iso(value: int) -> str:
    return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def scan_anchor(db: sqlite3.Connection) -> dict[str, Any]:
    """Return the latest completed scan boundary with its provenance.

    scan_runs is the only anchor: a zero-candidate scan still advances it.
    Indexer activity (audit imports, triage sync) must not advance the window,
    because those rows can be recorded long after the mail actually arrived;
    without a recorded scan the cursor bootstraps from a fixed lookback so the
    first scan re-covers recent history instead of skipping past it.
    """
    row = db.execute(
        """
        SELECT run_id, window_end_epoch, window_end FROM scan_runs
        ORDER BY window_end_epoch DESC, scan_run_id DESC LIMIT 1
        """
    ).fetchone()
    if row:
        return {"source": "scan_runs", "run_id": row["run_id"], "epoch": int(row["window_end_epoch"]), "value": row["window_end"]}
    return {"source": "bootstrap", "run_id": None, "epoch": None, "value": None}


def cursor(
    db: sqlite3.Connection,
    channels: tuple[str, ...] | list[str] = DEFAULT_SCAN_CHANNELS,
    overlap_seconds: int = DEFAULT_SCAN_OVERLAP_SECONDS,
    bootstrap_lookback_seconds: int = DEFAULT_SCAN_BOOTSTRAP_LOOKBACK_SECONDS,
) -> dict[str, Any]:
    """Return the deterministic Gmail search window for the next intake scan.

    The window is expressed as epoch seconds because Gmail interprets bare
    dates in the account timezone, which silently shifts the boundary. The
    queries embed the window and every monitored channel (joined with OR) so
    runs copy them verbatim instead of inventing their own anchor or silently
    dropping a channel.
    """
    terms = [str(term).strip() for term in channels if str(term).strip()]
    if not terms:
        raise ValueError("at least one scan channel is required")
    channel_filter = " OR ".join(terms)
    overlap_seconds = max(0, int(overlap_seconds))
    bootstrap_lookback_seconds = max(1, int(bootstrap_lookback_seconds))
    anchor = scan_anchor(db)
    end_epoch = int(datetime.now(timezone.utc).timestamp())
    if anchor["epoch"] is None:
        start_epoch = end_epoch - bootstrap_lookback_seconds
    else:
        start_epoch = min(int(anchor["epoch"]) - overlap_seconds, end_epoch - 1)
    start_epoch = max(start_epoch, 0)
    return {
        "query_kind": "intake-cursor",
        "window_start_epoch": start_epoch,
        "window_end_epoch": end_epoch,
        "window_start": epoch_to_iso(start_epoch),
        "window_end": epoch_to_iso(end_epoch),
        "overlap_seconds": overlap_seconds,
        "anchor": {
            "source": anchor["source"],
            "run_id": anchor["run_id"],
            "value": anchor["value"],
        },
        "channels": terms,
        "gmail_queries": {
            "inbox": f"{channel_filter} after:{start_epoch} before:{end_epoch} in:inbox",
            "spam": f"{channel_filter} after:{start_epoch} before:{end_epoch} in:spam",
        },
        "guidance": "epoch_window_required_use_queries_verbatim",
    }


def record_scan(
    db: sqlite3.Connection,
    run_id: str,
    window_start_epoch: int,
    window_end_epoch: int,
    inbox_hits: int = 0,
    spam_hits: int = 0,
    workflow: str = "support-replies",
) -> dict[str, Any]:
    """Record one completed scan so the cursor advances even with zero candidates.

    Only call this after both the Inbox and Spam searches for the window have
    actually executed; a failed or interrupted scan must leave the cursor where
    it was so the next run re-covers the same period.
    """
    run_id = str(run_id or "").strip()
    if not run_id:
        raise ValueError("run_id is required")
    start = int(window_start_epoch)
    end = int(window_end_epoch)
    if start < 0 or end <= start:
        raise ValueError("window must satisfy 0 <= start < end")
    recorded_at = now()
    db.execute(
        """
        INSERT OR IGNORE INTO scan_runs(
          run_id, workflow, window_start_epoch, window_end_epoch,
          window_start, window_end, inbox_hits, spam_hits, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            str(workflow or "support-replies"),
            start,
            end,
            epoch_to_iso(start),
            epoch_to_iso(end),
            max(0, int(inbox_hits)),
            max(0, int(spam_hits)),
            recorded_at,
        ),
    )
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]
    return {
        "recorded": True,
        "run_id": run_id,
        "window_start_epoch": start,
        "window_end_epoch": end,
        "scan_runs_total": int(total),
    }


def lookup(db: sqlite3.Connection, query: str, source_type: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Return identifier-level historical matches for one candidate.

    Exact source/thread IDs are checked first. A quoted FTS5 query is only a
    recall aid for repository/deduplication searches; callers must verify any
    match against authoritative state before acting on it.
    """
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query is required")
    limit = max(1, min(int(limit), 100))
    source_filter = ""
    source_args: list[str] = []
    if source_type:
        normalized_source = str(source_type).strip()
        variants = list(SCAN_SOURCE_TYPE_ALIASES.get(normalized_source, (normalized_source,)))
        source_filter = f"AND sm.source_type IN ({','.join('?' for _ in variants)})"
        source_args = variants

    exact_message = db.execute(
        f"""
        SELECT fi.feedback_id, fi.problem_summary, fi.current_status, fi.last_seen_at,
               sm.source_type, sm.external_message_id, sm.thread_id
        FROM source_messages AS sm
        JOIN feedback_items AS fi ON fi.feedback_id = sm.feedback_id
        WHERE sm.external_message_id = ? {source_filter}
        LIMIT ?
        """,
        (normalized_query, *source_args, limit),
    ).fetchall()
    exact_thread = [] if exact_message else db.execute(
        f"""
        SELECT fi.feedback_id, fi.problem_summary, fi.current_status, fi.last_seen_at,
               sm.source_type, sm.external_message_id, sm.thread_id
        FROM source_messages AS sm
        JOIN feedback_items AS fi ON fi.feedback_id = sm.feedback_id
        WHERE sm.thread_id = ? {source_filter}
        ORDER BY sm.occurred_at DESC
        LIMIT ?
        """,
        (normalized_query, *source_args, limit),
    ).fetchall()

    # Do not interpolate caller input into MATCH syntax. Quoting makes user
    # terms literal and prevents FTS5 operators from changing the query shape.
    fts_query = '"' + normalized_query.replace('"', '""') + '"'
    similar = db.execute(
        f"""
        SELECT fi.feedback_id, fi.problem_summary, fi.current_status, fi.last_seen_at,
               NULL AS source_type, NULL AS external_message_id, NULL AS thread_id
        FROM feedback_items_fts AS fts
        JOIN feedback_items AS fi ON fi.feedback_id = fts.rowid
        WHERE feedback_items_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (fts_query, limit),
    ).fetchall()

    feedback_ids = {
        int(row["feedback_id"])
        for rows in (exact_message, exact_thread, similar)
        for row in rows
    }
    tickets: list[dict[str, Any]] = []
    if feedback_ids:
        placeholders = ",".join("?" for _ in feedback_ids)
        tickets = [
            dict(row)
            for row in db.execute(
                f"""
                SELECT t.repository, t.number, t.kind, t.state, ft.relationship,
                       t.last_checked_at, t.released_version
                FROM feedback_tickets AS ft
                JOIN tickets AS t ON t.ticket_id = ft.ticket_id
                WHERE ft.feedback_id IN ({placeholders})
                ORDER BY t.last_updated_at DESC
                LIMIT ?
                """,
                (*feedback_ids, 100),
            )
        ]

    def rows(values: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in values]

    return {
        "query_kind": "intake-lookup",
        "query": normalized_query,
        "source_type": source_type,
        "exact_source_matches": rows(exact_message),
        "exact_thread_matches": rows(exact_thread),
        "similar_matches": rows(similar),
        "tickets": tickets,
        "decision_guidance": "advisory_only_verify_against_authoritative_state",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    support_cmd = sub.add_parser("import-support-audit")
    support_cmd.add_argument("input", type=Path)
    feedback_cmd = sub.add_parser("import-feedback-state")
    feedback_cmd.add_argument("input", type=Path)
    ingest_cmd = sub.add_parser("ingest")
    ingest_cmd.add_argument("input", type=Path)
    lookup_cmd = sub.add_parser("lookup")
    lookup_cmd.add_argument("query")
    lookup_cmd.add_argument("--source-type")
    lookup_cmd.add_argument("--limit", type=int, default=20)
    cursor_cmd = sub.add_parser("cursor")
    cursor_cmd.add_argument(
        "--channel",
        action="append",
        dest="channels",
        metavar="GMAIL_TERM",
        help="monitored channel term, repeatable, e.g. to:support@example.invalid",
    )
    cursor_cmd.add_argument("--overlap-seconds", type=int, default=DEFAULT_SCAN_OVERLAP_SECONDS)
    cursor_cmd.add_argument(
        "--bootstrap-lookback-seconds", type=int, default=DEFAULT_SCAN_BOOTSTRAP_LOOKBACK_SECONDS
    )
    record_cmd = sub.add_parser("record-scan")
    record_cmd.add_argument("--run-id", required=True)
    record_cmd.add_argument("--start-epoch", type=int, required=True)
    record_cmd.add_argument("--end-epoch", type=int, required=True)
    record_cmd.add_argument("--inbox-hits", type=int, default=0)
    record_cmd.add_argument("--spam-hits", type=int, default=0)
    record_cmd.add_argument("--workflow", default="support-replies")
    sub.add_parser("report")
    args = parser.parse_args()
    try:
        db = init_db(args.database)
        if args.command == "init":
            result = {"initialized": str(args.database)}
        elif args.command == "import-support-audit":
            result = import_support_audit(db, args.input)
        elif args.command == "import-feedback-state":
            result = import_feedback_state(db, args.input)
        elif args.command == "ingest":
            result = ingest(db, json.loads(args.input.read_text(encoding="utf-8")))
        elif args.command == "lookup":
            result = lookup(db, args.query, args.source_type, args.limit)
        elif args.command == "cursor":
            result = cursor(
                db,
                channels=args.channels or DEFAULT_SCAN_CHANNELS,
                overlap_seconds=args.overlap_seconds,
                bootstrap_lookback_seconds=args.bootstrap_lookback_seconds,
            )
        elif args.command == "record-scan":
            result = record_scan(
                db,
                run_id=args.run_id,
                window_start_epoch=args.start_epoch,
                window_end_epoch=args.end_epoch,
                inbox_hits=args.inbox_hits,
                spam_hits=args.spam_hits,
                workflow=args.workflow,
            )
        else:
            result = report(db)
        print(json.dumps({**result, "database": report(db)}, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
