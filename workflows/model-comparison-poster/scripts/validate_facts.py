#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

PLACEHOLDER = re.compile(r"REPLACE_WITH_|" + re.escape("/" + "Users" + "/") + r"|[A-Za-z]:\\Users\\", re.I)
CJK = re.compile(r"[\u3400-\u9fff]")

def fail(errors: list[str]) -> None:
    for error in errors:
        print(f"ERROR: {error}")
    raise SystemExit(1)

def valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("facts", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    try:
        data = json.loads(args.facts.read_text(encoding="utf-8"))
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except Exception as exc:
        fail([f"cannot read JSON: {exc}"])
    if data.get("slug") != args.facts.stem:
        errors.append("slug must match the facts filename stem")
    for key in ("as_of", "topic", "highlight_model"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f"{key} must be a non-empty string")
    notes = data.get("source_notes")
    if not isinstance(notes, list) or not notes:
        errors.append("source_notes must contain at least one source")
    else:
        for index, note in enumerate(notes):
            if not isinstance(note, dict) or not valid_url(str(note.get("url", ""))):
                errors.append(f"source_notes[{index}].url must be an http(s) URL")
            if note.get("confidence") not in {"verified", "unverified"}:
                errors.append(f"source_notes[{index}].confidence must be verified or unverified")
    models = data.get("models")
    if not isinstance(models, list) or len(models) < 2:
        errors.append("models must contain at least two models")
        models = []
    ids = set()
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            errors.append(f"models[{index}] must be an object")
            continue
        model_id = model.get("id")
        if not isinstance(model_id, str) or not model_id:
            errors.append(f"models[{index}].id is required")
        elif model_id in ids:
            errors.append(f"duplicate model id: {model_id}")
        ids.add(model_id)
        if not isinstance(model.get("name"), str) or not model["name"].strip():
            errors.append(f"models[{index}].name is required")
        for price_key in ("input_price_per_million", "output_price_per_million"):
            value = model.get(price_key)
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                errors.append(f"models[{index}].{price_key} must be a non-negative number or null")
    if data.get("highlight_model") not in ids:
        errors.append("highlight_model must match a model id")
    for language in ("cn", "en"):
        block = data.get(language)
        if not isinstance(block, dict) or not block.get("title") or not block.get("lead"):
            errors.append(f"{language}.title and {language}.lead are required")
        if language == "en" and CJK.search(json.dumps(block, ensure_ascii=False)):
            errors.append("English copy must not contain CJK characters")
    if PLACEHOLDER.search(json.dumps(data, ensure_ascii=False)):
        errors.append("facts contain a local absolute path or placeholder")
    if not isinstance(config, dict) or config.get("version") != 1:
        errors.append("config.version must equal 1")
    if errors:
        fail(errors)
    print(f"VALID: {args.facts}")

if __name__ == "__main__":
    main()
