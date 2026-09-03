#!/usr/bin/env python3
"""Capture a self-sizing Cindy HTML poster with the local Chrome browser."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
WIDTH = 1240


def chrome_path() -> Path:
    configured = os.environ.get("CINDY_POSTER_CHROME", "").strip()
    if configured:
        return Path(configured).expanduser()
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    return next((Path(value) for value in candidates if Path(value).exists()), Path(candidates[0]))


def capture_html(html_path: str | Path, output_path: str | Path) -> Path:
    html_path = Path(html_path).resolve()
    output_path = Path(output_path).resolve()
    chrome = chrome_path()
    if not chrome.exists():
        raise RuntimeError(
            f"Chrome not found: {chrome}. Set CINDY_POSTER_CHROME to a local Chrome/Chromium executable."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Remove only the exact requested output, so every capture is fresh.
    if output_path.exists():
        output_path.unlink()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(chrome),
            headless=True,
            args=["--disable-gpu", "--no-sandbox", "--disable-extensions"],
        )
        page = browser.new_page(
            # Start below the reference canvas. The poster itself determines
            # the final height; the viewport must not become an implicit min-height.
            viewport={"width": WIDTH, "height": 800},
            device_scale_factor=1,
        )
        page.goto(html_path.as_uri(), wait_until="networkidle", timeout=45_000)
        page.evaluate("document.fonts && document.fonts.ready")
        measured_height = page.evaluate(
            "Math.ceil(Math.max(document.body.scrollHeight, document.querySelector('.poster').getBoundingClientRect().height))"
        )
        rendered_height = max(1, int(measured_height))
        page.set_viewport_size({"width": WIDTH, "height": int(rendered_height)})
        page.screenshot(
            path=str(output_path),
            full_page=True,
            animations="disabled",
        )
        browser.close()
    print(f"{output_path} ({WIDTH}x{int(rendered_height)})")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    capture_html(args.html, args.output)


if __name__ == "__main__":
    main()
