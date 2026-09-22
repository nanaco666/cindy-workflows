#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

def chrome_path() -> Path:
    configured = os.environ.get("CINDY_POSTER_CHROME", "").strip()
    if configured:
        return Path(configured).expanduser()
    candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    return next((Path(value) for value in candidates if Path(value).exists()), Path(candidates[0]))

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    chrome = chrome_path()
    if not chrome.exists():
        raise SystemExit(f"Chrome not found: {chrome}. Set CINDY_POSTER_CHROME.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(chrome), headless=True, args=["--disable-gpu", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1080, "height": 800}, device_scale_factor=1)
        page.goto(args.html.resolve().as_uri(), wait_until="networkidle", timeout=45_000)
        height = int(page.evaluate("Math.ceil(document.body.scrollHeight)"))
        page.set_viewport_size({"width": 1080, "height": max(1, height)})
        page.screenshot(path=str(args.output), full_page=True, animations="disabled")
        browser.close()
    print(f"CAPTURED: {args.output}")

if __name__ == "__main__":
    main()
