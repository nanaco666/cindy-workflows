#!/usr/bin/env python3
"""Zero-token schedule gate for the portable Xiaohongshu workflow.

Exit 0 when local configuration is structurally usable, 2 when there is no
actionable local change, and non-zero on malformed or unsafe configuration.
The live Chrome/MCP login check remains in the agent run because it requires
interactive browser state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--accounts", type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        if config.get("version") != 1 or config.get("mode") != "READ_ONLY":
            raise ValueError("config must use version=1 and mode=READ_ONLY")
        if config.get("browser", {}).get("requiresRealChromeProfile") is not True:
            raise ValueError("real Chrome Profile requirement cannot be disabled")
        if args.accounts:
            accounts = json.loads(args.accounts.read_text(encoding="utf-8"))
            enabled = [a for a in accounts.get("accounts", []) if a.get("enabled", True)]
            mapped = [a for a in enabled if a.get("chrome_profile")]
            if not mapped:
                print("NO_MAPPED_ACCOUNTS", file=sys.stderr)
                return 2
        print("PREFLIGHT_OK")
        return 0
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError) as exc:
        print(f"PREFLIGHT_FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
