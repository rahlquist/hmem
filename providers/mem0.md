# mem0 — Universal Memory Layer for AI Agents

## End Goal
Provide a universal memory layer for AI agents that automatically extracts, stores, and retrieves structured facts from conversations across sessions.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Qdrant (self-hosted) or PostgreSQL with pgvector (self-hosted server); Mem0 Cloud (managed) |
| **Database type** | Vector database (Qdrant) or relational (PostgreSQL + pgvector) |
| **Data at rest** | Encrypted by the underlying DB (Qdrant/PostgreSQL); Mem0 Cloud uses encryption at rest |
| **Data in transit** | TLS for all API calls; self-hosted can use reverse proxy with TLS termination |
| **Authentication** | API key (`MEM0_API_KEY`); optional for self-hosted servers with `AUTH_DISABLED` |
| **Encryption** | No client-side encryption; relies on transport + DB-level encryption |
| **Compliance** | SOC 2 and HIPAA on managed cloud platform |
| **Multi-tenant** | Yes — per-user, per-agent, per-session memory scoping |

## How It Works
Mem0 uses an LLM pass to extract discrete facts from each conversation turn, creates embeddings for each fact, and stores them across a triple-store (vector + key-value + knowledge graph). On retrieval, it performs hybrid search across all three layers and returns the most relevant memories injected into the agent's context window.

## Hermes Integration
- **Native plugin**: `memory.provider: mem0` in `~/.hermes/config.yaml`
- **MCP server**: Available via `mcp_servers` config
- **Setup**: `hermes memory setup` → select "mem0" → choose Platform, Self-hosted, or OSS mode
- **Tools exposed**: `mem0_profile`, `mem0_search`, `mem0_conclude`
- **Config file**: `$HERMES_HOME/mem0.json`
- **Auth**: `MEM0_API_KEY` in `~/.hermes/.env`

## Install Type
- **Hermes native plugin** (primary) + **MCP server** (alternative)
- Single install per Hermes instance; profile-isolated data
- Does not interconnect across instances on its own (each instance has its own `mem0.json`)

## Overflow / Retention
- Managed cloud: configurable retention policies via dashboard
- Self-hosted/OSS: storage bounded by your own infrastructure; supports Qdrant or PostgreSQL backend
- No built-in deduplication beyond the LLM extraction layer

## Unique Features
- Triple-store architecture (vector + KV + graph) — unique among memory providers
- LLM auto-extraction of facts from conversations (zero manual memory management)
- Multi-level scoping: per-user, per-agent, per-session
- Temporal reasoning support
- Self-hosted mode with full data sovereignty
- SOC 2 and HIPAA compliance on managed platform

## Compatible Agents
Claude, Codex, Cursor, Hermes, OpenClaw, Gemini, any MCP-compatible agent

## Pricing
- **Free**: 10K memory adds, 1K recalls/month (Hobby)
- **$19/mo**: 50K adds, 5K recalls (Starter)
- **$249/mo**: Unlimited + graph memory features (Pro)
- **Self-hosted**: Free (Apache 2.0), infrastructure costs only

## Public Metrics
- GitHub: ★ 62.3K (mem0ai/mem0)
- LongMemEval: 67.6% (benchmark score)
- LoCoMo: disputed (self-reported results contested by competitors)
- Funding: $24M Series A (Oct 2025, Basis Set Ventures)
