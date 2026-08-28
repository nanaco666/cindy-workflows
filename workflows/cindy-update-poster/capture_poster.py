#!/usr/bin/env python3
"""Capture the fixed-size Cindy HTML poster with local Chrome."""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHROME = Path(os.environ.get(
    "CINDY_POSTER_CHROME",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
))
WIDTH, HEIGHT = 1240, 1754


def capture_html(html_path: str | Path, output_path: str | Path) -> Path:
    html_path = Path(html_path).resolve()
    output_path = Path(output_path).resolve()
    if not CHROME.exists():
        raise RuntimeError(f"Chrome not found: {CHROME}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cindy-poster-chrome-") as profile:
        command = [
            str(CHROME), "--headless=new", "--disable-gpu", "--no-sandbox",
            "--disable-extensions", "--disable-background-networking",
            "--disable-component-update", "--disable-sync", "--hide-scrollbars",
            "--run-all-compositor-stages-before-draw", f"--user-data-dir={profile}",
            f"--window-size={WIDTH},{HEIGHT}", f"--screenshot={output_path}",
            f"file://{html_path}",
        ]
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and not output_path.exists():
            time.sleep(0.25)
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        if not output_path.exists():
            detail = proc.stderr.read().decode("utf-8", "replace")[-1000:]
            raise RuntimeError(f"Chrome did not produce screenshot: {detail}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(capture_html(args.html, args.output))


if __name__ == "__main__":
    main()
