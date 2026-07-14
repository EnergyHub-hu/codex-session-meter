from __future__ import annotations

import argparse
import json
import sys

from . import auth
from .config import LOG_FILE, ALLOWED_POLL_INTERVALS, ALLOWED_DISPLAY_FORMATS, ALLOWED_WEEKLY_WORKDAYS, ALLOWED_PANEL_ICONS, ConfigError, read_settings, write_settings
from .fetcher import cached_status, refresh_status


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _settings_payload(settings: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        **settings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="codex-session-meter")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "refresh"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--json", action="store_true", help="Print normalized JSON")

    settings_parser = subparsers.add_parser("settings")
    settings_parser.add_argument("--json", action="store_true", help="Print current settings as JSON")

    configure = subparsers.add_parser("configure")
    configure.add_argument("--poll-interval", type=int, choices=ALLOWED_POLL_INTERVALS)
    configure.add_argument("--display-format", choices=tuple(sorted(ALLOWED_DISPLAY_FORMATS)))
    configure.add_argument("--weekly-workdays", type=int, choices=ALLOWED_WEEKLY_WORKDAYS)
    configure.add_argument("--panel-icon", choices=tuple(sorted(ALLOWED_PANEL_ICONS)))
    configure.add_argument("--json", action="store_true", help="Print updated settings as JSON")

    subparsers.add_parser("login")
    subparsers.add_parser("logout")
    subparsers.add_parser("auth-status")
    subparsers.add_parser("open-logs")

    args = parser.parse_args(argv)

    if args.command == "status":
        payload = cached_status()
        print_json(payload) if args.json else print(payload.get("display", "Codex: unknown"))
        return 0 if payload.get("ok") else 1
    if args.command == "refresh":
        payload = refresh_status()
        print_json(payload) if args.json else print(payload.get("display", "Codex: unknown"))
        return 0 if payload.get("ok") else 1
    if args.command == "settings":
        try:
            payload = _settings_payload(read_settings())
        except ConfigError as exc:
            payload = {"ok": False, "status": "config_error", "message": str(exc)}
        print_json(payload) if args.json else print(payload)
        return 0
    if args.command == "configure":
        payload = _settings_payload(
            write_settings(
                poll_interval_minutes=args.poll_interval,
                display_format=args.display_format,
                weekly_workdays=args.weekly_workdays,
                panel_icon=args.panel_icon,
            )
        )
        print_json(payload) if args.json else print("Settings updated")
        return 0
    if args.command == "login":
        auth.open_login()
        print("Started Codex CLI login.")
        return 0
    if args.command == "logout":
        auth.logout()
        print("Codex CLI logout requested")
        return 0
    if args.command == "auth-status":
        print_json(auth.codex_auth_summary())
        return 0
    if args.command == "open-logs":
        import subprocess

        subprocess.Popen(["xdg-open", str(LOG_FILE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
