from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

from .agent import Agent
from .config import load_settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="csift", description="ContextSift Agent")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    parser.add_argument(
        "--recent-messages",
        type=int,
        help="Override recent main messages; 0 includes all main messages",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run one user request")
    run.add_argument("message", nargs="+", help="User request")
    subparsers.add_parser("chat", help="Start an interactive chat")
    subparsers.add_parser("doctor", help="Check local readiness without calling external APIs")
    preview = subparsers.add_parser("context", help="Print the next context manifest")
    preview.add_argument("--query", help="Optional retrieval query")
    return parser


def _agent(args: argparse.Namespace) -> Agent:
    settings = load_settings(args.config)
    if args.recent_messages is not None:
        if args.recent_messages < 0:
            raise ValueError("--recent-messages must be 0 or positive")
        settings.context.recent_main_messages = args.recent_messages
    return Agent(settings)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        agent = _agent(args)
        if args.command == "run":
            print(agent.ask(" ".join(args.message)))
            return 0
        if args.command == "context":
            print(json.dumps(agent.preview_context(args.query)["manifest"], indent=2))
            return 0
        if args.command == "doctor":
            report = agent.doctor()
            print(json.dumps(report, indent=2))
            return 0 if report["status"] == "ready" else 1
        print("ContextSift Agent. Type /exit to quit.")
        while True:
            try:
                text = input("> ").strip()
            except EOFError:
                print()
                return 0
            if text in {"/exit", "/quit"}:
                return 0
            if text:
                print(agent.ask(text))
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
