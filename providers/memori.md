# Memori — Tool-Aware Structured Memory

## End Goal
Provide structured, tool-aware memory for AI agents with explicit project and session attribution, enabling agents to recall memories with full context about where and when they were created.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Memori Cloud (backend not publicly disclosed) |
| **Database type** | Cloud-managed (proprietary) |
| **Data at rest** | Encrypted by cloud provider; details not publicly documented |
| **Data in transit** | TLS for all API calls |
| **Authentication** | API key from [app.memorilabs.ai](https://app.memorilabs.ai/signup) |
| **Encryption** | No client-side encryption; relies on cloud TLS + server-side |
| **Compliance** | Not publicly documented |
| **Multi-tenant** | Cloud-managed; scoped by API key |

## How It Works
Memori stores memories with structured metadata including project attribution, session attribution, and tool usage context. Unlike systems that just store freeform text, Memori tracks which tool or action generated each memory, making it possible to query memories by the context in which they were created. This is particularly useful for agents that use multiple tools — the memory system knows not just what was learned, but how it was learned.

## Hermes Integration
- **Native plugin**: `memory.provider: memori` in `~/.hermes/config.yaml`
- **Setup**: `pip install hermes-memori` → `hermes-memori install` → `hermes memory setup`
- **Config**: `hermes config set memory.provider memori`
- **Auth**: Memori API key from [app.memorilabs.ai](https://app.memorilabs.ai/signup)
- **Storage**: Memori Cloud (no self-hosted option currently listed)

## Install Type
- **Hermes native plugin** (primary)
- Cloud-synced across instances (Memori Cloud)
- Single install per Hermes instance; data isolated by profile on the cloud side

## Overflow / Retention
- Managed by Memori Cloud — retention policies are cloud-configured
- Structured metadata enables precise querying, reducing noise from irrelevant memories
- No local storage option — all data lives in Memori Cloud

## Unique Features
- **Tool-aware memory**: Tracks which tool/action generated each memory
- **Structured project attribution**: Memories are scoped to projects
- **Session attribution**: Full context about when and where a memory was created
- **Structured recall**: Query memories by project, session, or tool context
- **Cloud-only**: No self-hosted option (as of research date)

## Compatible Agents
Hermes (primary); any MCP-compatible agent via Memori Cloud API

## Pricing
- **Free tier**: Available (details on Memori site)
- **Paid tier**: Memori pricing (see app.memorilabs.ai)

## Public Metrics
- GitHub: ★ not prominently listed on hermesatlas
- Hermes integration: Listed as a first-class memory provider in Hermes docs
- Weekly growth: Not tracked on hermesatlas
