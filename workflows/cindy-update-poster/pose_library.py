"""Approved Cindy character art library with deterministic daily selection."""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "assets", "pose-library.json")
POSE_DIR = os.path.join(HERE, "assets", "poses")


def load_library():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def eligible(layout):
    assets = []
    for asset in load_library().get("assets", []):
        if not asset.get("enabled", True) or layout not in asset.get("layouts", []):
            continue
        path = os.path.join(POSE_DIR, f"{asset['name']}.png")
        if not os.path.exists(path):
            raise FileNotFoundError(f"pose library asset is missing: {path}")
        assets.append(asset)
    return sorted(assets, key=lambda item: item["name"])


def enabled_assets():
    """All approved assets available as imagegen references.

    Unlike ``eligible()``, this does not depend on a legacy Pillow layout. The
    manifest's layout compatibility remains useful only for ``--legacy-render``.
    """
    assets = []
    for asset in load_library().get("assets", []):
        if not asset.get("enabled", True):
            continue
        path = os.path.join(POSE_DIR, f"{asset['name']}.png")
        if not os.path.exists(path):
            raise FileNotFoundError(f"pose library asset is missing: {path}")
        item = deepcopy(asset)
        item["path"] = path
        assets.append(item)
    return sorted(assets, key=lambda item: item["name"])


def choose(day_id, layout):
    pool = eligible(layout)
    if not pool:
        return None
    digest = hashlib.sha256(f"{day_id}:{layout}".encode()).digest()
    return deepcopy(pool[int.from_bytes(digest[:8], "big") % len(pool)])


def choose_reference(day_id):
    """Stable daily choice from the full approved imagegen reference pool."""
    pool = enabled_assets()
    if not pool:
        return None
    digest = hashlib.sha256(f"{day_id}:imagegen-reference".encode()).digest()
    return deepcopy(pool[int.from_bytes(digest[:8], "big") % len(pool)])


def find(name):
    for asset in load_library().get("assets", []):
        if asset.get("name") == name:
            return deepcopy(asset)
    return None


def apply(cfg, layout):
    """Fill only omitted visual fields. Explicit JSON values always win."""
    if cfg.get("pose"):
        selected = find(cfg["pose"])
        if selected and layout in selected.get("layouts", []):
            for key, value in selected.get("layout_options", {}).get(layout, {}).items():
                cfg.setdefault(key, value)
        return None
    selected = choose(str(cfg["day_id"]), layout)
    if not selected:
        return None
    cfg["pose"] = selected["name"]
    for key, value in selected.get("layout_options", {}).get(layout, {}).items():
        cfg.setdefault(key, value)
    return selected
