# Hindsight — Agent Memory That Learns (Retain → Recall → Reflect)

## End Goal
Provide agent memory that actively learns from experience through a three-phase cycle: retain (ingest), recall (retrieve), and reflect (synthesize across stored knowledge to produce new insights).

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Local filesystem (self-hosted) or cloud backend |
| **Database type** | Knowledge graph (self-hosted) or cloud-managed |
| **Data at rest** | Encrypted on self-hosted; cloud encryption managed by Vectorize |
| **Data in transit** | TLS for cloud; none for self-hosted |
| **Authentication** | API key for cloud; none for self-hosted daemon |
| **Encryption** | No client-side encryption specified |
| **Compliance** | Not publicly documented for self-hosted |
| **Multi-tenant** | Self-hosted: single-user; Cloud: multi-tenant possible |

## How It Works
Hindsight implements a three-phase memory lifecycle:
1. **Retain**: Conversation turns are captured and stored with metadata (session, timestamp, entities).
2. **Recall**: When the agent needs context, Hindsight retrieves relevant memories using a combination of vector similarity and knowledge graph traversal.
3. **Reflect**: After retrieval, Hindsight synthesizes across stored knowledge to produce new insights — connecting dots between previously unrelated memories.

It uses a knowledge graph as its primary storage backbone, with vector embeddings for semantic search and graph edges for relationship traversal.

## Hermes Integration
- **Native plugin**: `memory.provider: hindsight` in `~/.hermes/config.yaml`
- **Setup**: `hermes memory setup` → select "hindsight"
- **Config**: `bank_id`, `recall_budget` (low/mid/high), `retain_context` label
- **Auth**: Optional API key for cloud; works without for local daemon
- **Tools**: retain, recall, reflect, list_memories, search, delete

## Install Type
- **Hermes native plugin** (primary) + MCP server (alternative)
- Single install per Hermes instance; profile-isolated via `bank_id`
- Cloud sync available for cross-instance sharing (optional)

## Overflow / Retention
- `recall_budget` controls thoroughness: `low` / `mid` / `high` — higher budgets recall more but consume more tokens
- `retain_context` label scopes what gets retained (default: "conversation between Hermes Agent and the User")
- Knowledge graph structure allows selective pruning of low-value edges
- Cloud tier has configurable retention policies

## Unique Features
- **Three-phase lifecycle**: Retain → Recall → Reflect (synthesis is unique)
- **Knowledge graph backbone**: Relationships between memories are explicit
- **Reflect synthesis**: Connects dots across previously unrelated memories — produces new insights
- **Configurable recall budget**: Trade off thoroughness vs token usage
- **MIT license**: Permissive, self-hostable
- **Strong benchmarks**: 94.6% on LongMemEval

## Compatible Agents
Hermes, Claude, any MCP-compatible agent

## Pricing
- **Self-hosted**: Free (MIT license)
- **Cloud**: Usage-based; free credits available; enterprise pricing on request

## Public Metrics
- GitHub: ★ 19.0K (vectorize-io/hindsight)
- Weekly growth: +183 stars/wk
- LongMemEval: 94.6%
