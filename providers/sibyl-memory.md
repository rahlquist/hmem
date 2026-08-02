# Sibyl-Memory — Durable File-Based Memory with 5-Package Plugin Family

## End Goal
Provide durable, file-based long-term memory for AI agents using a five-package plugin architecture (SDK, CLI, MCP server, Hermes adapter, LangGraph BaseStore) — no vector database, no embeddings required.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Structured files on disk (no database) |
| **Database type** | None — file-based storage |
| **Data at rest** | Plain structured files; no encryption at rest |
| **Data in transit** | None for local use; MCP server uses HTTP if remote |
| **Authentication** | None for local; MCP server can use headers for auth |
| **Encryption** | None; relies on filesystem permissions |
| **Compliance** | Full data sovereignty; no cloud dependency |
| **Multi-tenant** | No — single-user; file-based isolation |

## How It Works
Sibyl-Memory stores memories as structured files on disk. It uses a five-package architecture where each component can be used independently or together:
- **SDK**: Core memory operations library
- **CLI**: Command-line interface for memory management
- **MCP server**: Expose memory tools to any MCP-compatible agent
- **Hermes adapter**: Native Hermes plugin integration
- **LangGraph BaseStore**: Integration with LangGraph for graph-based workflows

The system does not use a vector database or embeddings — it relies on file-based storage with structured metadata for retrieval. This makes it lightweight and easy to deploy without any ML infrastructure.

## Hermes Integration
- **Hermes adapter**: Native plugin (`hermes-memory-provider` tag)
- **MCP server**: HTTP-based MCP for external agent access
- **CLI**: `sibyl` command for memory management
- **Config**: File-based, no database required
- **Storage**: Structured files on disk

## Install Type
- **Hermes adapter** (native plugin) + MCP server + CLI
- Each package installs independently
- File-based storage allows sharing across instances (shared filesystem)
- Profile isolation via directory structure

## Overflow / Retention
- Bounded by filesystem space
- File-based structure allows manual curation and pruning
- No built-in automatic decay or pruning
- Structured metadata enables precise querying without full-text scans

## Unique Features
- **5-package plugin family**: SDK, CLI, MCP, Hermes adapter, LangGraph BaseStore
- **No vector DB required**: Pure file-based storage — no embeddings, no ML infrastructure
- **Durable**: File-based storage is inherently durable and portable
- **Hermes adapter**: First-class Hermes integration
- **LangGraph integration**: BaseStore for graph-based memory workflows
- **No cloud dependency**: Fully self-hosted

## Compatible Agents
Hermes (native adapter), any MCP-compatible agent (MCP server), LangGraph (BaseStore)

## Pricing
- **Free**: Open-source, self-hosted
- **No cloud tier**: Local only

## Public Metrics
- GitHub: ★ 98 (Sibyl-Labs/Sibyl-Memory)
- Weekly growth: +1 star/wk
- Five-package architecture is unique among memory providers
