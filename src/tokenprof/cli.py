"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys

from tokenprof import __version__
from tokenprof.attribute import profile_stream, read_jsonl
from tokenprof.cache import analyze as analyze_cache
from tokenprof.diff import diff_turns
from tokenprof.record import record
from tokenprof.report.json_out import (
    cache_to_dict,
    diff_to_dict,
    profile_to_dict,
    turn_to_dict,
)
from tokenprof.report.table import render_cache, render_diff, render_profile, render_turn


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tokenprof",
        description="Profile what is actually consuming your context window.",
    )
    p.add_argument("--version", action="version", version=f"tokenprof {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("file", help="JSONL of request payloads, or - for stdin")
    common.add_argument(
        "--provider",
        choices=["openai_chat", "anthropic_messages"],
        help="skip shape detection and force an adapter",
    )
    common.add_argument("--format", choices=["table", "json"], default="table")
    common.add_argument(
        "--rate",
        type=float,
        metavar="USD_PER_MTOK",
        help="input price per million tokens, overriding the built-in table",
    )

    a = sub.add_parser("analyze", parents=[common], help="profile every turn in a file")
    a.add_argument("--turn", type=int, help="show one turn in full instead of the summary")
    a.add_argument("--top", type=int, default=10, help="rows in the per-turn breakdowns")

    d = sub.add_parser("diff", parents=[common], help="compare two turns")
    d.add_argument("--from", dest="from_", type=int, default=0, help="baseline turn index")
    d.add_argument("--to", type=int, default=-1, help="comparison turn index, -1 for last")

    sub.add_parser(
        "cache",
        parents=[common],
        help="find where the cacheable prompt prefix breaks",
    )

    r = sub.add_parser("record", help="run a program and capture its requests")
    r.add_argument("-o", "--out", default="tokenprof.jsonl", help="where to write the JSONL")
    r.add_argument("--verbose", action="store_true", help="report whether the shim attached")
    r.add_argument(
        "argv",
        nargs=argparse.REMAINDER,
        metavar="-- COMMAND",
        help="the command to run, after --",
    )

    return p


def _load(args: argparse.Namespace):
    profile = profile_stream(read_jsonl(args.file), provider=args.provider)
    if not profile.turns:
        raise SystemExit(f"{args.file}: no request payloads found")
    return profile


def cmd_analyze(args: argparse.Namespace) -> int:
    profile = _load(args)

    if args.turn is not None:
        try:
            turn = profile.turns[args.turn]
        except IndexError:
            raise SystemExit(
                f"turn {args.turn} out of range: file has {len(profile.turns)} turns"
            ) from None
        if args.format == "json":
            json.dump(turn_to_dict(turn), sys.stdout, indent=2)
            print()
        else:
            print(render_turn(turn, top=args.top, rate=args.rate))
        return 0

    if args.format == "json":
        json.dump(profile_to_dict(profile), sys.stdout, indent=2)
        print()
    else:
        print(render_profile(profile, top=args.top, rate=args.rate))
        if len(profile.turns) == 1:
            print()
            print(render_turn(profile.turns[0], top=args.top, rate=args.rate))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    profile = _load(args)
    try:
        before = profile.turns[args.from_]
        after = profile.turns[args.to]
    except IndexError:
        raise SystemExit(f"turn index out of range: file has {len(profile.turns)} turns") from None

    d = diff_turns(before, after)
    if args.format == "json":
        json.dump(diff_to_dict(d), sys.stdout, indent=2)
        print()
    else:
        print(render_diff(d, rate=args.rate, model=after.model))
    return 0


def cmd_cache(args: argparse.Namespace) -> int:
    profile = _load(args)
    report = analyze_cache(profile)
    if args.format == "json":
        json.dump(cache_to_dict(report), sys.stdout, indent=2)
        print()
    else:
        print(render_cache(report, profile, rate=args.rate))
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    argv = [a for a in args.argv if a != "--"]
    if not argv:
        raise SystemExit("nothing to run. Usage: tokenprof record -- python your_app.py")
    return record(argv, args.out, verbose=args.verbose)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "analyze":
            return cmd_analyze(args)
        if args.command == "diff":
            return cmd_diff(args)
        if args.command == "cache":
            return cmd_cache(args)
        if args.command == "record":
            return cmd_record(args)
    except (ValueError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc
    except BrokenPipeError:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
