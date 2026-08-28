#!/usr/bin/env python3
"""Classify normalized records and atomically update incremental account state."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Missing file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


def atomic_write(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--records", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--classified-output", required=True)
    parser.add_argument("--successful-at", required=True, help="ISO-8601 timestamp")
    parser.add_argument("--retention-days", type=int, default=90)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    state_path = Path(args.state)
    state = load(state_path)
    payload = load(Path(args.records))
    records = payload.get("records", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise SystemExit("Records must be a JSON array or an object with a records array")

    accounts = state.setdefault("accounts", {})
    account_state = accounts.setdefault(
        args.account,
        {"last_success_at": None, "cursor_start": None, "fingerprints": []},
    )
    raw_seen = account_state.get("fingerprints", {})
    if isinstance(raw_seen, list):
        # Backward compatibility with the initial list-only state schema.
        seen = {value: None for value in raw_seen}
    elif isinstance(raw_seen, dict):
        seen = dict(raw_seen)
    else:
        seen = {}
    previous = set(seen)
    classified = []
    for record in records:
        item = dict(record)
        item["incremental_status"] = (
            "previously_seen" if item.get("fingerprint") in previous else "new"
        )
        classified.append(item)

    Path(args.classified_output).write_text(
        json.dumps({"records": classified}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.commit:
        successful_at = datetime.fromisoformat(args.successful_at)
        cutoff = successful_at - timedelta(days=args.retention_days)
        for record in records:
            value = record.get("fingerprint")
            if value:
                seen[value] = record.get("timestamp") or successful_at.isoformat()
        retained = {}
        for value, timestamp in seen.items():
            if timestamp is None:
                # Preserve migrated hashes for one successful run.
                retained[value] = successful_at.isoformat()
                continue
            try:
                if datetime.fromisoformat(timestamp) >= cutoff:
                    retained[value] = timestamp
            except ValueError:
                continue
        account_state["fingerprints"] = retained
        account_state["last_success_at"] = successful_at.isoformat()
        account_state["cursor_start"] = (successful_at - timedelta(days=1)).isoformat()
        atomic_write(state_path, state)

    print(
        json.dumps(
            {
                "records": len(classified),
                "new": sum(item["incremental_status"] == "new" for item in classified),
                "previously_seen": sum(
                    item["incremental_status"] == "previously_seen" for item in classified
                ),
                "committed": args.commit,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
