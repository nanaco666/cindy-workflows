#!/usr/bin/env python3
"""Normalize Xiaohongshu feedback timestamps and exact duplicates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_clock(raw: str) -> time:
    match = re.search(r"(\d{1,2}):(\d{2})", raw)
    if not match:
        return time(12, 0)
    return time(int(match.group(1)), int(match.group(2)))


def parse_time(raw: str, today: date, timezone: ZoneInfo, now: datetime | None = None) -> datetime:
    text = normalize_space(raw)
    clock = parse_clock(text)

    patterns = [
        (r"^刚刚$", timedelta()),
        (r"^(\d+)分钟前$", "minutes"),
        (r"^(\d+)小时前$", "hours"),
    ]
    current = now or datetime.combine(today, time(12, 0), timezone)
    for pattern, delta in patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        if isinstance(delta, timedelta):
            return current - delta
        return current - timedelta(**{delta: int(match.group(1))})

    if text.startswith("昨天"):
        return datetime.combine(today - timedelta(days=1), clock, timezone)

    match = re.match(r"^(\d+)天前(?:\s+\d{1,2}:\d{2})?$", text)
    if match:
        return datetime.combine(today - timedelta(days=int(match.group(1))), clock, timezone)

    match = re.match(r"^(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$", text)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        parsed_clock = time(int(match.group(3) or 12), int(match.group(4) or 0))
        year = today.year
        candidate = date(year, month, day)
        if candidate > today + timedelta(days=7):
            candidate = date(year - 1, month, day)
        return datetime.combine(candidate, parsed_clock, timezone)

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=timezone)
        except ValueError:
            pass
    raise ValueError(f"Unsupported Xiaohongshu time: {raw!r}")


def fingerprint(record: dict) -> str:
    stable = "\x1f".join(
        normalize_space(record.get(key)).casefold()
        for key in ("account", "source", "user", "timestamp", "content", "url", "conversation_id")
    )
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]


def normalize_record(raw: dict, account: str, today: date, timezone: ZoneInfo) -> dict:
    timestamp = parse_time(str(raw.get("time_raw", "")), today, timezone)
    record = {
        "account": normalize_space(raw.get("account") or account),
        "source": normalize_space(raw.get("source")),
        "user": normalize_space(raw.get("user")),
        "time_raw": normalize_space(raw.get("time_raw")),
        "timestamp": timestamp.isoformat(),
        "date": timestamp.date().isoformat(),
        "content": normalize_space(raw.get("content")),
        "quote": normalize_space(raw.get("quote")),
        "interaction_type": normalize_space(raw.get("interaction_type")),
        "url": normalize_space(raw.get("url")),
        "conversation_id": normalize_space(raw.get("conversation_id")),
        "side": normalize_space(raw.get("side")),
    }
    if record["source"] not in {"comment", "dm"}:
        raise ValueError(f"source must be comment or dm: {raw!r}")
    if not record["user"] or not record["content"]:
        raise ValueError(f"user and content are required: {raw!r}")
    record["fingerprint"] = fingerprint(record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--today", required=True)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--account", required=True)
    args = parser.parse_args()

    raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("Input must be a JSON array")
    today = date.fromisoformat(args.today)
    timezone = ZoneInfo(args.timezone)
    by_fingerprint: dict[str, dict] = {}
    errors: list[dict] = []
    for index, item in enumerate(raw):
        try:
            record = normalize_record(item, args.account, today, timezone)
            by_fingerprint.setdefault(record["fingerprint"], record)
        except (TypeError, ValueError) as exc:
            errors.append({"index": index, "error": str(exc)})

    records = sorted(by_fingerprint.values(), key=lambda item: item["timestamp"], reverse=True)
    output = {"records": records, "errors": errors}
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"input": len(raw), "records": len(records), "errors": len(errors)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
