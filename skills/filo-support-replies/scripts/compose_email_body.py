#!/usr/bin/env python3
"""Build a standard Gmail rich-text reply draft body.

Input is a JSON object containing the authored plaintext reply, one to three
short emphasis phrases, a localized quote header, and the complete original
customer message. The output can be copied directly into the Gmail
``create_draft`` MIME payload and into the workflow manifest.

Customer text is escaped before it enters HTML. This script never writes mail
or audit data and never stores the input.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any


QUOTE_STYLE = "margin:0 0 0 .8ex;border-left:1px #ccc solid;padding-left:1ex"


def read_input(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read input JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def require_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def emphasis_phrases(data: dict[str, Any], reply_body: str) -> list[str]:
    raw = data.get("emphasis")
    if not isinstance(raw, list):
        raise ValueError("emphasis must be a list with one to three phrases")
    phrases = [str(item).strip() for item in raw if str(item).strip()]
    if not 1 <= len(phrases) <= 3:
        raise ValueError("emphasis must contain one to three non-empty phrases")
    if len({phrase.casefold() for phrase in phrases}) != len(phrases):
        raise ValueError("emphasis phrases must be unique")
    for phrase in phrases:
        if len(phrase) > 120:
            raise ValueError("each emphasis phrase must be 120 characters or fewer")
        if phrase not in reply_body:
            raise ValueError(f"emphasis phrase is not present in reply_body: {phrase!r}")
        if (
            re.fullmatch(r"Hi\b.*[,，]", phrase, flags=re.IGNORECASE)
            or phrase in {"Filo Support", "Best,", "Best，", "祝好，", "祝好,"}
        ):
            raise ValueError("do not bold the greeting, sign-off, or signature")
    return phrases


def render_inline(text: str, phrases: list[str]) -> str:
    positions: list[tuple[int, int, str]] = []
    for phrase in phrases:
        start = text.find(phrase)
        if start < 0:
            continue
        positions.append((start, start + len(phrase), phrase))
    positions.sort()
    for index in range(1, len(positions)):
        if positions[index][0] < positions[index - 1][1]:
            raise ValueError("emphasis phrases must not overlap")

    result: list[str] = []
    cursor = 0
    for start, end, phrase in positions:
        result.append(html.escape(text[cursor:start]))
        result.append(f"<strong>{html.escape(phrase)}</strong>")
        cursor = end
    result.append(html.escape(text[cursor:]))
    return "".join(result).replace("\n", "<br>")


def render_reply_html(reply_body: str, phrases: list[str]) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", reply_body) if part.strip()]
    if len(paragraphs) < 3:
        raise ValueError("reply_body must use at least three natural paragraphs")
    rendered: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        if index:
            rendered.append('<div dir="ltr"><br></div>')
        rendered.append(f'<div dir="ltr">{render_inline(paragraph, phrases)}</div>')
    return "".join(rendered)


def render_original_html(original_text: str) -> str:
    return html.escape(original_text).replace("\n", "<br>")


def build(data: dict[str, Any]) -> dict[str, Any]:
    reply_body = require_text(data, "reply_body")
    quote_header = require_text(data, "quote_header")
    original_text = require_text(data, "original_text")
    phrases = emphasis_phrases(data, reply_body)

    reply_body_html = render_reply_html(reply_body, phrases)
    quoted_plain = "\n".join(f"> {line}" if line else ">" for line in original_text.splitlines())
    body_plain = f"{reply_body}\n\n{quote_header}\n{quoted_plain}"
    body_html = (
        f"{reply_body_html}"
        '<div dir="ltr"><br></div>'
        '<div class="gmail_quote">'
        f'<div dir="ltr" class="gmail_attr">{html.escape(quote_header)}<br></div>'
        f'<blockquote class="gmail_quote" style="{QUOTE_STYLE}">'
        f"{render_original_html(original_text)}"
        "</blockquote></div>"
    )

    return {
        "mime_type": "multipart/alternative",
        "reply_body": reply_body,
        "reply_body_html": reply_body_html,
        "body_plain": body_plain,
        "body_html": body_html,
        "emphasis": phrases,
        "payload": {
            "mime_type": "multipart/alternative",
            "parts": [
                {
                    "mime_type": "text/plain",
                    "charset": "UTF-8",
                    "content_disposition": "inline",
                    "body": {"content": body_plain},
                },
                {
                    "mime_type": "text/html",
                    "charset": "UTF-8",
                    "content_disposition": "inline",
                    "body": {"content": body_html},
                },
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(read_input(args.input)), ensure_ascii=False, sort_keys=True))
        return 0
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
