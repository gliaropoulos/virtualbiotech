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

    # Standard research tools every scientist agent may use alongside its MCP data tools.
    STANDARD_TOOLS = ("WebSearch", "WebFetch")

    def allowed_tool_names(self) -> list[str]:
        """Fully-qualified tool names the agent may call: its MCP tools + standard research tools."""
        from .mcp_bridge import tool_names_for
        names: list[str] = []
        for server in self.spec.mcp_servers:
            names.extend(tool_names_for(server))
        names.extend(self.STANDARD_TOOLS)
        return names

    def build_options(self) -> dict:
        """SDK-agnostic description of this agent's runtime config (testable without the SDK)."""
        return {
            "model": self.spec.model,
            "system_prompt": self.system_prompt,
            "mcp_servers": list(self.spec.mcp_servers),
            "allowed_tools": self.allowed_tool_names(),
            "metadata": {"agent": self.spec.key, "division": self.spec.division.value},
        }

    def _sdk_options(self, *, workspace: str | None, max_turns: int | None):
        from claude_agent_sdk import ClaudeAgentOptions  # type: ignore
        from .mcp_bridge import build_servers

        cli_path = config.claude_cli_path()
        return ClaudeAgentOptions(
            model=self.spec.model,
            system_prompt=self.system_prompt,
            mcp_servers=build_servers(self.spec.mcp_servers),
            allowed_tools=self.allowed_tool_names(),
            cwd=workspace,
            **({"max_turns": max_turns} if max_turns else {}),
            **({"cli_path": cli_path} if cli_path else {}),
        )

    async def run(self, task: str, *, workspace: str | None = None,
                  max_turns: int | None = None) -> str:
        """Execute one task with this agent.

        Requires the Claude Agent SDK *and* the Claude Code CLI on PATH (the SDK runs the agent loop
        by spawning that CLI). The agent's domain MCP tools are bridged in-process via
        `create_sdk_mcp_server`, so it calls exactly the tested FastMCP tool code.

        Auth is delegated to the Claude CLI: it uses ANTHROPIC_API_KEY (paid API credits) if set,
        otherwise your `claude login` subscription/OAuth session. So no API key is strictly required.
        """
        try:
            from claude_agent_sdk import (  # type: ignore
                AssistantMessage, TextBlock, query,
            )
            from claude_agent_sdk._internal.transport.subprocess_cli import (  # type: ignore
                SubprocessCLITransport,
            )
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("claude-agent-sdk is not installed. `pip install -e .`.") from e

        options = self._sdk_options(workspace=workspace, max_turns=max_turns)
        transport = _CapturingTransport(SubprocessCLITransport(prompt=task, options=options))
        chunks: list[str] = []
        try:
            async for message in query(prompt=task, options=options, transport=transport):  # pragma: no cover
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            chunks.append(block.text)
        except Exception as e:
            raise _agent_run_error(e, transport.last_error) from e
        if transport.last_error:
            raise RuntimeError(f"Agent run failed: {transport.last_error}")
        return "".join(chunks)


class _CapturingTransport:
    """Remember the CLI's structured error payload when the SDK collapses it to 'success'."""

    def __init__(self, inner):
        self._inner = inner
        self.last_error: str | None = None

    def __getattr__(self, name):
        return getattr(self._inner, name)

    async def read_messages(self):
        async for message in self._inner.read_messages():
            if message.get("type") == "result" and message.get("is_error"):
                detail = message.get("result")
                if not detail:
                    errors = message.get("errors") or []
                    detail = "; ".join(errors) if errors else message.get("subtype")
                self.last_error = str(detail)
            yield message


def _agent_run_error(exc: Exception, captured: str | None) -> RuntimeError:
    if captured:
        return RuntimeError(f"Agent run failed: {captured}")
    msg = str(exc)
    if "error result: success" in msg:
        return RuntimeError(
            "Claude Code API call failed before the agent could respond. "
            "Check Anthropic billing/credits and that ANTHROPIC_API_KEY in .env is valid: "
            "https://console.anthropic.com/settings/billing"
        )
    return RuntimeError(f"Agent run failed: {msg}")
