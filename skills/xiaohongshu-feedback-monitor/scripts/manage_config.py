#!/usr/bin/env python3
"""Manage local, credential-free configuration for Xiaohongshu monitoring."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


DEFAULT_RUNTIME = Path.home() / ".cindy" / "xiaohongshu-feedback-monitor"
CHROME_LOCAL_STATE = Path.home() / "Library/Application Support/Google/Chrome/Local State"


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Missing {path}. Run the init command first.")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


def chrome_profile_directories(path: Path = CHROME_LOCAL_STATE) -> set[str]:
    data = load_json(path)
    return set(data.get("profile", {}).get("info_cache", {}))


def cmd_init(args: argparse.Namespace) -> None:
    runtime = Path(args.runtime).expanduser()
    accounts_path = runtime / "accounts.json"
    state_path = runtime / "state.json"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "exports").mkdir(exist_ok=True)

    if accounts_path.exists() and not args.force:
        accounts = load_json(accounts_path)
    else:
        accounts = {
            "version": 1,
            "timezone": "Asia/Shanghai",
            "accounts": [
                {
                    "id": f"account-{index}",
                    "label": f"Xiaohongshu account {index}",
                    "chrome_profile": None,
                    "enabled": not args.disabled,
                }
                for index in range(1, args.slots + 1)
            ],
        }
        atomic_write(accounts_path, accounts)

    if not state_path.exists() or args.force:
        state = {
            "version": 1,
            "accounts": {
                item["id"]: {
                    "last_success_at": None,
                    "cursor_start": None,
                    "fingerprints": {},
                }
                for item in accounts.get("accounts", [])
            },
        }
        atomic_write(state_path, state)

    print(accounts_path)
    print(state_path)


def cmd_show(args: argparse.Namespace) -> None:
    runtime = Path(args.runtime).expanduser()
    accounts = load_json(runtime / "accounts.json")
    state = load_json(runtime / "state.json")
    print(json.dumps({"config": accounts, "state": state}, ensure_ascii=False, indent=2))


def cmd_chrome_profiles(args: argparse.Namespace) -> None:
    data = load_json(Path(args.chrome_local_state).expanduser())
    info_cache = data.get("profile", {}).get("info_cache", {})
    profiles = [
        {
            "directory": directory,
            "display_name": item.get("name", ""),
            "signed_in_email": item.get("user_name", ""),
        }
        for directory, item in sorted(info_cache.items())
    ]
    print(json.dumps(profiles, ensure_ascii=False, indent=2))


def cmd_set_account(args: argparse.Namespace) -> None:
    runtime = Path(args.runtime).expanduser()
    accounts_path = runtime / "accounts.json"
    state_path = runtime / "state.json"
    config = load_json(accounts_path)
    state = load_json(state_path)

    matches = [item for item in config.get("accounts", []) if item.get("id") == args.account]
    if not matches:
        raise SystemExit(f"Unknown account slot: {args.account}")
    if args.chrome_profile not in chrome_profile_directories(Path(args.chrome_local_state).expanduser()):
        raise SystemExit(f"Chrome profile directory does not exist: {args.chrome_profile}")

    account = matches[0]
    account["label"] = args.label
    account["chrome_profile"] = args.chrome_profile
    account["enabled"] = not args.disabled
    state.setdefault("accounts", {}).setdefault(
        args.account,
        {"last_success_at": None, "cursor_start": None, "fingerprints": {}},
    )
    atomic_write(accounts_path, config)
    atomic_write(state_path, state)
    print(json.dumps(account, ensure_ascii=False, indent=2))


def cmd_validate(args: argparse.Namespace) -> None:
    runtime = Path(args.runtime).expanduser()
    config = load_json(runtime / "accounts.json")
    state = load_json(runtime / "state.json")
    errors: list[str] = []
    accounts = config.get("accounts")
    if config.get("version") != 1 or not isinstance(accounts, list):
        errors.append("accounts.json must have version=1 and an accounts array")
        accounts = []
    seen: set[str] = set()
    assigned_profiles: dict[str, str] = {}
    available_profiles = chrome_profile_directories(Path(args.chrome_local_state).expanduser())
    for index, account in enumerate(accounts):
        account_id = account.get("id")
        if not account_id or account_id in seen:
            errors.append(f"account at index {index} has a missing or duplicate id")
        else:
            seen.add(account_id)
        profile = account.get("chrome_profile")
        if account.get("enabled", True) and not profile:
            errors.append(f"{account_id or index}: enabled account has no chrome_profile mapping")
        elif profile and profile not in available_profiles:
            errors.append(f"{account_id or index}: Chrome profile does not exist: {profile}")
        elif account.get("enabled", True) and profile in assigned_profiles:
            errors.append(
                f"{account_id or index}: Chrome profile {profile} is already assigned to "
                f"{assigned_profiles[profile]}"
            )
        elif account.get("enabled", True) and profile:
            assigned_profiles[profile] = account_id or str(index)
    if state.get("version") != 1 or not isinstance(state.get("accounts"), dict):
        errors.append("state.json must have version=1 and an accounts object")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"OK: {len(accounts)} account slots configured")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--runtime", default=str(DEFAULT_RUNTIME))
    init.add_argument("--slots", type=int, default=3)
    init.add_argument("--force", action="store_true")
    init.add_argument("--disabled", action="store_true", help="Create slots disabled until mapped")
    init.set_defaults(func=cmd_init)
    show = sub.add_parser("show")
    show.add_argument("--runtime", default=str(DEFAULT_RUNTIME))
    show.set_defaults(func=cmd_show)
    profiles = sub.add_parser("chrome-profiles")
    profiles.add_argument("--runtime", default=str(DEFAULT_RUNTIME), help=argparse.SUPPRESS)
    profiles.add_argument("--chrome-local-state", default=str(CHROME_LOCAL_STATE))
    profiles.set_defaults(func=cmd_chrome_profiles)
    set_account = sub.add_parser("set-account")
    set_account.add_argument("--runtime", default=str(DEFAULT_RUNTIME))
    set_account.add_argument("--account", required=True, help="Account slot id, for example account-1")
    set_account.add_argument("--label", required=True, help="Human-readable Xiaohongshu account name")
    set_account.add_argument("--chrome-profile", required=True, help="Chrome profile directory name")
    set_account.add_argument("--chrome-local-state", default=str(CHROME_LOCAL_STATE))
    set_account.add_argument("--disabled", action="store_true")
    set_account.set_defaults(func=cmd_set_account)
    validate = sub.add_parser("validate")
    validate.add_argument("--runtime", default=str(DEFAULT_RUNTIME))
    validate.add_argument("--chrome-local-state", default=str(CHROME_LOCAL_STATE))
    validate.set_defaults(func=cmd_validate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
