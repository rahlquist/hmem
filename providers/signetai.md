# SignetAI — Local-First Identity, Memory, and Secrets

## End Goal
Provide a local-first identity and memory layer for AI agents that is portable across models and harnesses — storing not just memories but also agent identity and secrets in a single portable package.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Local filesystem (portable state file) |
| **Database type** | None — portable state file |
| **Data at rest** | State file on disk; secrets encrypted at rest |
| **Data in transit** | None — fully local |
| **Authentication** | None required for local use |
| **Encryption** | Secrets encrypted at rest in the state file |
| **Compliance** | Full data sovereignty; no cloud dependency |
| **Multi-tenant** | No — single state file per installation |

## How It Works
SignetAI combines three concerns in one system: identity (who the agent is), memory (what it has learned), and secrets (API keys, credentials, configuration). It stores everything in a local-first, portable format that can move between different agent frameworks (Hermes, Claude Code, Codex, OpenClaw, etc.) without losing context. The system uses a portable state format that is framework-agnostic.

## Hermes Integration
- **MCP server**: Primary integration path for Hermes
- **Portable state**: Works across Hermes, Claude Code, Codex, OpenClaw, and MCP clients
- **Local-first**: All data stored locally; no cloud dependency
- **Identity + memory + secrets**: Combined in one portable package

## Install Type
- **MCP server** (primary)
- Standalone installation; does not install per-Hermes-instance
- Portable state file can be shared across instances and frameworks

## Overflow / Retention
- Bounded by local storage
- Portable state file can be backed up or version-controlled
- No built-in automatic pruning
- Identity and secrets are persistent by design (not auto-expiring)

## Unique Features
- **Identity + memory + secrets in one system**: Not just memory — full agent state
- **Portable across frameworks**: Same state works with Hermes, Claude Code, Codex, OpenClaw
- **Local-first**: No cloud dependency, no API keys needed
- **Portable state format**: Framework-agnostic, can be version-controlled
- **Secrets management**: Built-in credential storage alongside memory

## Compatible Agents
Hermes, Claude Code, Codex, OpenClaw, any MCP-compatible agent

## Pricing
- **Free**: Self-hosted, local-first
- **No cloud tier**: Local only

## Public Metrics
- GitHub: ★ 227 (Signet-AI/signetai)
- Weekly growth: +6 stars/wk
- Primary differentiator: Identity + memory + secrets combined
