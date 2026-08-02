# Supermemory — Vector Graph Engine with Context Fencing

## End Goal
Deliver a fast, scalable memory engine for AI agents with a custom vector graph backend and hybrid RAG search, designed to prevent context pollution from stale or irrelevant memories.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Custom vector graph engine (proprietary); self-hosted or cloud |
| **Database type** | Proprietary vector graph (not a standard vector DB) |
| **Data at rest** | Encrypted on self-hosted deployments; cloud encryption managed by Supermemory |
| **Data in transit** | TLS for all API communication |
| **Authentication** | API key (`SUPERMEMORY_API_KEY`) |
| **Encryption** | No client-side encryption specified; relies on transport + server-side |
| **Compliance** | Not publicly documented |
| **Multi-tenant** | Yes — via container tags for project isolation |

## How It Works
Supermemory uses a custom vector graph engine that stores memories as both vector embeddings and graph relationships. It employs hybrid RAG search combining vector similarity with graph traversal. Its key innovation is **context fencing** — a mechanism that prevents the agent from accidentally capturing or polluting the memory store with transient conversation noise, ensuring only intentional memories persist.

## Hermes Integration
- **Native plugin**: `memory.provider: supermemory` in `~/.hermes/config.yaml`
- **Setup**: `hermes memory setup` → select "supermemory"
- **Config**: `$HERMES_HOME/supermemory.json` with container tags and custom instructions
- **Auth**: `SUPERMEMORY_API_KEY` in `~/.hermes/.env`
- **Tools**: Memory search, store, delete, list, and context management

## Install Type
- **Hermes native plugin** (primary) + **MCP server** (alternative)
- Single install per Hermes instance; profile-isolated via container tags
- Cloud-synced across instances when using the same project tags

## Overflow / Retention
- Configurable retention via `supermemory.json` settings
- Context fencing automatically filters low-signal captures
- Byte-level deduplication prevents duplicate storage
- Supports multi-container setups (e.g., separate containers for different projects)

## Unique Features
- **Context fencing**: Prevents capture pollution — only intentional memories persist
- **Custom vector graph engine**: Proprietary graph + vector hybrid, not a standard vector DB
- **Session graph ingest**: Builds a graph of conversation sessions for multi-hop recall
- **Multi-container support**: Isolate memory by project, user, or agent role
- **Sub-300ms recall** sustained at 100B+ tokens/month (benchmarked)
- **Connectors**: Google Drive, Gmail, GitHub integration for ingesting external context

## Compatible Agents
Claude, Codex, Cursor, Hermes, OpenClaw, Gemini

## Pricing
- **Free tier**: Available (limited)
- **Paid plans**: Contact Supermemory for pricing
- **Self-hosted**: Available (details on request)

## Public Metrics
- GitHub: ★ 28.7K (supermemoryai/supermemory)
- Weekly growth: +103 stars/wk
- Benchmark: Sub-300ms recall at 100B+ tokens/month
