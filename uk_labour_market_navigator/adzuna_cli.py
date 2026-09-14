"""User-controlled optional connection commands; never put credential values in arguments."""

from __future__ import annotations

import getpass
import json
import os
import sys
import warnings
from pathlib import Path

from .adzuna import (
    TERMS,
    AdzunaError,
    Credentials,
    _keyring,
    connection_status,
    disconnect,
    save_connection,
    search,
)

CREDENTIAL_PROMPTS = ("Adzuna App ID (hidden): ", "Adzuna App Key (hidden): ")


def interactive_console() -> bool:
    if not sys.stdin.isatty():
        return False
    if os.name != "nt":
        return True
    # Windows NUL can report isatty=True, but cannot supply protected console input.
    import ctypes
    import msvcrt
    from ctypes import wintypes

    try:
        query = ctypes.WinDLL("kernel32", use_last_error=True).GetConsoleMode
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        query.restype = wintypes.BOOL
        mode = wintypes.DWORD()
        return bool(query(msvcrt.get_osfhandle(sys.stdin.fileno()), ctypes.byref(mode)))
    except (OSError, ValueError):
        return False


def cmd_adzuna(args) -> int:
    try:
        if args.adzuna_command == "status":
            result = connection_status()
        elif args.adzuna_command == "disconnect":
            result = disconnect()
        elif args.adzuna_command == "connect":
            if not args.permission:
                print(
                    "Adzuna is optional. Register for your own App ID and App Key at "
                    "https://developer.adzuna.com/overview.\n"
                    "Check permission for your intended use: " + TERMS + "\n"
                    "Then use connect --permission personal_research or provider_permission, "
                    "as appropriate. Enter credentials only into the masked local prompt, never chat.\n"
                    "Results displayed through a host may remain in its conversation history. "
                    "The connector does not save provider data or enable publication/export."
                )
                return 0
            if not interactive_console():
                raise AdzunaError(
                    "Open the connection prompt yourself in an interactive local terminal. "
                    "Credential input through chat, pipes or command arguments is disabled."
                )
            backend = _keyring()
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                # Refuse getpass's echoing fallback when a protected terminal is unavailable.
                entered = [getpass.getpass(prompt) for prompt in CREDENTIAL_PROMPTS]
            result = save_connection(Credentials(*entered), args.permission, backend=backend)
            result["message"] = "Connection saved locally; no API request was made. "
            result["message"] += "Choose a permitted role/place search to check live access."
        elif args.adzuna_command == "search":
            if not args.online:
                raise AdzunaError(
                    "This optional search sends a role/place query to Adzuna. "
                    "Review the scope and permissions, then explicitly enable --online."
                )
            try:
                raw = sys.stdin.read() if args.request == "-" else Path(args.request).read_text(encoding="utf-8")
                request = json.loads(raw)
            except (OSError, ValueError):
                raise AdzunaError("The search request could not be read; no connection was attempted.") from None
            result = search(request)
        else:
            raise AdzunaError("Choose connection guidance, status, disconnect or an explicit search.")
    except AdzunaError as exc:
        print(json.dumps({"status": "unavailable", "message": str(exc), "core_available": True}))
        return 2
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        print(
            json.dumps(
                {
                    "status": "cancelled",
                    "message": "Protected credential entry was unavailable or cancelled. No new connection was saved.",
                    "core_available": True,
                }
            )
        )
        return 2
    except Exception:
        # Credential/transport exceptions must never reach a traceback or host logs.
        print(
            json.dumps(
                {
                    "status": "unavailable",
                    "message": "The optional connection could not complete. "
                    "No error details containing account information were displayed.",
                    "core_available": True,
                }
            )
        )
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def add_commands(subparsers) -> None:
    parser = subparsers.add_parser("adzuna", help="optional user-owned Adzuna connection and transient searches")
    commands = parser.add_subparsers(dest="adzuna_command")
    parser.set_defaults(func=cmd_adzuna, adzuna_command="connect", permission=None)
    connect = commands.add_parser("connect", help="guide masked local credential entry; no API request")
    connect.add_argument("--permission", choices=["personal_research", "provider_permission"])
    for name in ("status", "disconnect"):
        commands.add_parser(name)
    query = commands.add_parser("search", help="one permitted, explicitly online search; no saved provider data")
    query.add_argument("request", nargs="?", default="-")
    query.add_argument("--online", action="store_true")
