"""`vb` — command-line entry point for interacting with the Virtual Biotech.

Subcommands:
    vb list                          list the 11 agents and their MCP tools
    vb agent <key> "<task>"          run one scientist agent on a task (live)
    vb ask "<query>"                 run the full CSO orchestration on a query (live)

Live runs require: ANTHROPIC_API_KEY in .env (or the environment) AND the Claude Code CLI on PATH
(`npm install -g @anthropic-ai/claude-code`), since the Agent SDK runs the agent loop via that CLI.
`vb list` and `--dry-run` work without either.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from . import config
from .agents.base import BaseAgent
from .agents.registry import REGISTRY, Division, scientists
from .common.workspace import Session


def cmd_list() -> None:
    from .agents import mcp_bridge
    by_div: dict[Division, list] = {}
    for spec in REGISTRY.values():
        by_div.setdefault(spec.division, []).append(spec)
    for div, specs in by_div.items():
        print(f"\n{div.value}")
        for spec in specs:
            tools = sum(len(mcp_bridge.tool_names_for(s)) for s in spec.mcp_servers)
            servers = ", ".join(spec.mcp_servers) or "—"
            print(f"  {spec.key:24s} [{spec.model}]  servers: {servers}  ({tools} tools)")


def _require_runtime() -> None:
    """Ensure a runnable agent runtime. Auth can be an API key (paid credits) OR a Claude
    subscription via the CLI's OAuth login — so the API key is not strictly required."""
    if config.claude_cli_path() is None:
        raise SystemExit(
            "The 'claude' CLI is required for live agent runs but was not found on PATH.\n"
            "  Install: npm install -g @anthropic-ai/claude-code")
    if config.anthropic_api_key() is None:
        print("No ANTHROPIC_API_KEY set — the run will use your Claude CLI login "
              "(subscription/OAuth) if you've run `claude login`.\n", file=sys.stderr)


def cmd_agent(key: str, task: str, max_turns: int | None) -> None:
    if key not in REGISTRY:
        raise SystemExit(f"unknown agent '{key}'. Try `vb list`.")
    _require_runtime()
    agent = BaseAgent.from_key(key)
    print(f"[{agent.spec.name}] working on: {task}\n")
    out = asyncio.run(agent.run(task, max_turns=max_turns))
    print(out)


def cmd_ask(query: str, dry_run: bool) -> None:
    from .orchestration.cso import CSO
    if not dry_run:
        _require_runtime()
    session = Session()
    print(f"Session {session.session_id} — workspace: {session.dir}\n")
    cso = CSO(session=session, dry_run=dry_run)
    report = asyncio.run(cso.handle(query))
    print(report)
    print(f"\nReasoning trace: {session.trace}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="vb", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("list", help="list agents and their tools")

    a = sub.add_parser("agent", help="run one scientist agent")
    a.add_argument("key", help="agent key, e.g. statistical_genetics (see `vb list`)")
    a.add_argument("task", help="the task/question for the agent")
    a.add_argument("--max-turns", type=int, default=None)

    k = sub.add_parser("ask", help="run the full CSO orchestration")
    k.add_argument("query", help="the scientific question")
    k.add_argument("--dry-run", action="store_true", help="record routing without calling models")

    args = p.parse_args(argv)
    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "agent":
        cmd_agent(args.key, args.task, args.max_turns)
    elif args.cmd == "ask":
        cmd_ask(args.query, args.dry_run)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
