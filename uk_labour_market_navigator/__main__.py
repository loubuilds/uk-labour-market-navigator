"""Internal host commands. People use the conversation, not these arguments."""

import argparse
import json
import sys
from pathlib import Path

from .branding import DESCRIPTION, PRODUCT_NAME


def main(argv=None):
    # Check before engine imports so older Python receives setup help, not a traceback.
    if sys.version_info < (3, 11):
        version = ".".join(str(part) for part in sys.version_info[:3])
        print(
            f"One setup step before we begin: this project needs Python 3.11 or later; this command is using {version}.\n"
            "Your coding agent can check for a suitable version already installed, or help you install one.\n"
            "Ask it: Help me get Python ready, then continue my question.\n"
            "Keep your existing Python in place. Setup guidance: https://github.com/loubuilds/uk-labour-market-navigator/blob/main/docs/python-setup.md",
            file=sys.stderr,
        )
        return 2
    from . import workflow
    from .evidence import ScopeChoice

    parser = argparse.ArgumentParser(prog="uk-labour-market-navigator", description=PRODUCT_NAME + ": " + DESCRIPTION)
    commands = parser.add_subparsers(dest="command", required=True)
    from .adzuna_cli import add_commands

    add_commands(commands)
    commands.add_parser("setup")
    commands.add_parser("help")
    start = commands.add_parser("start")
    start.add_argument("question")
    start.add_argument("--purpose", default="Prepare a useful workforce discussion")
    start.add_argument("--place", action="append", required=True)
    start.add_argument("--role", required=True)
    start.add_argument("--gap", action="append", default=[])
    start.add_argument("--view", choices=("market", "workforce", "demand", "pay"), default="market")
    start.add_argument("--requested-role")
    start.add_argument("--no-pay", action="store_true")
    start.add_argument("--no-hours", action="store_true", help="Leave out the separate UK paid-hours benchmarks")
    context_choice = start.add_mutually_exclusive_group()
    context_choice.add_argument("--with-context", dest="with_context", action="store_true")
    context_choice.add_argument("--no-context", dest="with_context", action="store_false")
    start.set_defaults(with_context=None)
    start.add_argument("--pay-pattern", choices=("all", "full_time", "part_time"), default="full_time")
    start.add_argument("--pay-measure", choices=("annual_gross", "hourly_excluding_overtime"), default="annual_gross")
    start.add_argument("--runs-dir", type=Path, default=Path("runs"))
    for name in ("collect", "publish", "verify", "show", "status"):
        p = commands.add_parser(name)
        p.add_argument("run", type=Path)
        if name == "collect":
            p.add_argument("--accept", action="store_true")
            pay_choice = p.add_mutually_exclusive_group()
            pay_choice.add_argument("--accept-pay", dest="pay_accepted", action="store_true")
            pay_choice.add_argument("--decline-pay", dest="pay_accepted", action="store_false")
            p.set_defaults(pay_accepted=None)
        if name == "publish":
            p.add_argument("--draft", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "adzuna":
        return args.func(args)
    try:
        if args.command == "setup":
            print(
                f"Welcome to {PRODUCT_NAME}.\n{DESCRIPTION}\n\n"
                "You don't need a research question ready. Choose a starting point:\n\n"
                "1. Show me what this can do - walk through the fictional Sheffield customer-service example.\n"
                "2. Help with a hire - tell me the role and town; we can work out what would be useful to explore.\n\n"
                "A short reply is enough. No profile or data-provider key is needed."
            )
            return 0
        if args.command == "help":
            print(
                "1. Show me an example\n2. We're finding a role hard to fill\n3. We're considering two locations\n4. We're reviewing the pay offer\n5. Help me understand a figure or reopen a brief\n\n"
                "Reply with a number, or just tell me the role and town. I will help frame a useful question and explain any broader scope before using it.\n"
                "The evidence can inform these decisions; it does not diagnose your recruitment results. No provider key is required."
            )
            return 0
        if args.command == "start":
            result = workflow.start(
                args.question,
                args.purpose,
                args.place,
                args.role,
                args.gap,
                args.runs_dir,
                include_demand=args.view in ("market", "demand"),
                include_workforce=args.view in ("market", "workforce"),
                release=True,
                requested_role=args.requested_role,
                include_hours=args.view in ("market", "pay") and not args.no_pay and not args.no_hours,
                include_pay=args.view in ("market", "pay") and not args.no_pay,
                include_context=args.with_context if args.with_context is not None else args.view == "market",
                pay_pattern=args.pay_pattern,
                pay_measure=args.pay_measure,
            )
        elif args.command == "collect":
            result = workflow.gather(args.run, args.accept, args.pay_accepted)
        elif args.command == "publish":
            result = workflow.publish(args.run, workflow.read_draft(args.draft))
        elif args.command == "status":
            result = workflow.verify(args.run)
        else:
            result = workflow.verify(args.run)
            if args.command == "show" and result["status"] == "ready":
                print(Path(result["markdown"]).read_text(encoding="utf-8"))
                return 0
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2 if result.get("status") == "withdrawn" else 0
    except ScopeChoice as exc:
        print(json.dumps({"status": "scope_choice", "message": str(exc)}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Internal commands contain only general context. Do not print file/JSON
        # exceptions that could echo arbitrary file contents or private paths.
        message = (
            str(exc)
            if isinstance(exc, ValueError) and not isinstance(exc, (json.JSONDecodeError, UnicodeError))
            else "I couldn't read this research step. Check the current run and try again."
        )
        print(json.dumps({"status": "needs_attention", "message": message}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
