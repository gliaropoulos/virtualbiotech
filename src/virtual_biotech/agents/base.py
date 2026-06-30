"""BaseAgent — a thin wrapper that turns an AgentSpec into a runnable Claude Agent SDK agent.

The Claude Agent SDK is imported lazily so the package can be built, imported, and unit-tested
without the SDK installed or an API key present. `BaseAgent.build_options()` returns the SDK
configuration; `BaseAgent.run()` actually executes a turn and requires the SDK + a key.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import config
from ..prompts import load_prompt
from .registry import AgentSpec, get


@dataclass
class BaseAgent:
    spec: AgentSpec

    @classmethod
    def from_key(cls, key: str) -> "BaseAgent":
        return cls(get(key))

    @property
    def system_prompt(self) -> str:
        return load_prompt(self.spec.prompt_name)

    def mcp_server_commands(self) -> dict[str, list[str]]:
        """Map each permitted MCP server to the command that launches it.

        Convention: every server is runnable as `python -m mcp_servers.<name>.server`.
        """
        return {
            name: ["python", "-m", f"mcp_servers.{name}.server"]
            for name in self.spec.mcp_servers
        }

    def build_options(self) -> dict:
        """Assemble the configuration dict for the Agent SDK (SDK-agnostic representation).

        Kept as a plain dict so it is testable without the SDK. `run()` adapts it to the SDK's
        options object at call time.
        """
        return {
            "model": self.spec.model,
            "system_prompt": self.system_prompt,
            "mcp_servers": self.mcp_server_commands(),
            "allowed_tools": ["Read", "Write", "Edit", "Bash"],  # standard compute tools
            "metadata": {"agent": self.spec.key, "division": self.spec.division.value},
        }

    async def run(self, task: str, *, workspace: str | None = None) -> str:
        """Execute one task with this agent. Requires the Claude Agent SDK and an API key."""
        config.require_anthropic_api_key()
        try:
            from claude_agent_sdk import ClaudeAgentOptions, query  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "claude-agent-sdk is not installed. `pip install claude-agent-sdk` to run agents."
            ) from e

        opts = self.build_options()
        options = ClaudeAgentOptions(
            model=opts["model"],
            system_prompt=opts["system_prompt"],
            allowed_tools=opts["allowed_tools"],
            cwd=workspace,
            # mcp_servers wiring is SDK-version specific; see docs/ARCHITECTURE.md.
        )
        chunks: list[str] = []
        async for message in query(prompt=task, options=options):  # pragma: no cover
            chunks.append(getattr(message, "text", str(message)))
        return "".join(chunks)
