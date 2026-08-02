# YantrikDB — Self-Maintaining Memory with Explainable Recall

## End Goal
Provide a self-maintaining memory system for Hermes Agent that benchmarks its own recall quality, tunes its ranking automatically, tracks contradictions, and explains why each memory was retrieved — all with an embedded-by-default architecture.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Embedded SQLite (Rust, in-process) |
| **Database type** | Relational (SQLite, embedded) |
| **Data at rest** | Encrypted by SQLite; file-level permissions |
| **Data in transit** | None — fully embedded, no network |
| **Authentication** | None — embedded in Hermes process |
| **Encryption** | SQLite file-level; no network exposure |
| **Compliance** | Full data sovereignty; zero external exposure |
| **Multi-tenant** | No — embedded per Hermes profile |

## How It Works
YantrikDB is an embedded database (Rust backend) that runs inside Hermes as a native plugin. It maintains itself — no manual tuning required. It benchmarks recall quality against a held-out set, self-tunes ranking parameters, detects and tracks contradictions in stored memories, and proactively performs hygiene (pruning stale or conflicting entries). Every recall is tagged with `why_retrieved` — an explainable tag showing exactly why that memory was returned for a given query.

## Hermes Integration
- **Hermes native plugin**: Primary integration — embedded by default
- **Config**: Hermes `~/.hermes/config.yaml` memory provider section
- **No external services**: Fully self-contained, embedded database
- **Tools**: Recall, store, delete, list, explain (why_retrieved), benchmark

## Install Type
- **Hermes native plugin** (embedded-by-default)
- Single install per Hermes instance
- Each profile has its own YantrikDB instance
- Does not interconnect across instances

## Overflow / Retention
- **Self-maintaining**: Automatic hygiene — prunes stale and conflicting entries
- **Contradiction tracking**: Detects when new memories contradict old ones
- **Benchmarked recall**: Continuously measures and tunes retrieval quality
- **No manual pruning needed**: The system manages its own size

## Unique Features
- **Self-maintaining**: Automatic hygiene, no manual intervention
- **Explainable recall**: Every memory retrieval is tagged with `why_retrieved`
- **Contradiction tracking**: Detects and flags conflicting memories
- **Self-tuning ranking**: Automatically optimizes retrieval parameters
- **Benchmarked recall**: Continuously measures recall quality
- **Embedded-by-default**: No external services, no API keys
- **Rust backend**: High performance, low resource usage
- **Hermes-native**: Not a generic MCP server — built specifically for Hermes

## Compatible Agents
Hermes Agent (primary); not designed for cross-framework use

## Pricing
- **Free**: Open-source, self-hosted, embedded
- **No cloud tier**: Local only

## Public Metrics
- GitHub: ★ 76 (yantrikos/yantrikdb-hermes-plugin)
- Weekly growth: 0 stars/wk (stable)
- Unique among memory providers: embedded-by-default, Hermes-specific
