# Architecture

This complements `DEVELOPMENT_PLAN.md` with the runtime design.

## Layers

1. **Orchestration** (`src/virtual_biotech/orchestration/`) — the CSO and its office. The CSO is a
   pure coordinator: it owns no MCP tools and runs no analysis. It spawns scientist agents as Claude
   Agent SDK sub-agents, optionally in parallel, and synthesizes their summaries.
2. **Agents** (`src/virtual_biotech/agents/`) — `BaseAgent` wraps an Agent SDK client with a system
   prompt, a model, an allowed set of MCP servers, and a session workspace. The registry maps the 11
   agents to their models and tool permissions.
3. **Tools** (`mcp_servers/`) — each data source is a FastMCP server. Tools are typed Python
   functions with rich docstrings; FastMCP introspects them into schemas. Tools return a structured
   payload plus a short natural-language summary so the model can triage quickly.
4. **Analysis** (`analysis/`) — deterministic scientific code (stats, single-cell, survival) the
   agents invoke via code execution / skills. Kept separate from agents so it is unit-testable.
5. **UI** (`ui/`) — streams reasoning + tool activity and exposes the per-session workspace.

## Orchestration flow (paper Figure 1C)

```
user query
  → CSO clarification interview  (+ Chief of Staff briefing, in parallel)
  → CSO task decomposition + routing
  → scientist agents analyze (parallel or sequenced)
  → Scientific Reviewer QA  ──(gaps?)──▶ CSO re-delegates
  → CSO synthesizes report + reproducible workspace
```

## Model routing

| Role | Model | Env override |
|---|---|---|
| CSO / scientists | Sonnet 4.5 | `VB_MODEL_SCIENTIST`, `VB_MODEL_ORCHESTRATOR` |
| Chief of Staff, Reviewer | Haiku 4.5 | `VB_MODEL_SUPPORT` |

## Agent → MCP permission matrix

Defined in `agents/registry.py`. Each agent sees only the servers relevant to its domain
(separation of responsibilities). Example: the statistical genetics agent gets `open_targets` +
`gnomad`; the clinical trialist gets `clinicaltrials` + `pubmed` + `cbioportal`.

## Session workspace & auditability

Every run gets an isolated directory under `sessions/<id>/` containing the reasoning trace
(JSONL), every tool call + result, generated code, figures, and data. This is the audit trail the
paper emphasizes — a human expert can re-run any result.

## MCP tool conventions

- One server per source; one Python function per tool.
- Typed params (gene symbols, disease IDs, NCT IDs, filters) + a thorough docstring.
- Return `{ "summary": str, "data": <typed payload>, "preview": <small slice> }`.
- Network calls go through a shared `httpx` client with retry/backoff (`common/http.py`).
- Each server ships a `smoke.py` for a credential-free (or live) one-shot check.
