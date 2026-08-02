# Mnemosyne — Zero-Dependency Sub-Millisecond AI Memory

## End Goal
Provide the simplest possible memory system for Hermes Agents — zero external dependencies, sub-millisecond recall, and a single SQLite database. No API keys, no network calls, no Docker required.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Single SQLite file |
| **Database type** | Relational (SQLite) with FTS5 full-text search |
| **Data at rest** | Encrypted by SQLite (optional); file-level permissions |
| **Data in transit** | None — fully local, no network communication |
| **Authentication** | None — no API keys, no network |
| **Encryption** | None by default; SQLite can be encrypted with SQLCipher |
| **Compliance** | Full data sovereignty; zero external exposure |
| **Multi-tenant** | No — single SQLite file per Hermes instance |

## How It Works
Mnemosyne stores all memories in a single SQLite database with no external dependencies. It uses a combination of BM25 keyword search and vector similarity (via SQLite's built-in FTS5 and vector extensions) for retrieval. The entire system runs in-process — there is no server, no daemon, and no network communication. Memory operations are direct Python SDK calls or MCP stdio/SSE connections.

## Hermes Integration
- **Native plugin**: `memory.provider: mnemosyne` in `~/.hermes/config.yaml`
- **MCP server**: Stdio or SSE transport
- **Setup**: Install via pip, configure in Hermes config
- **Storage**: Single SQLite file in `$HERMES_HOME/`
- **No config file**: Everything is in the SQLite database

## Install Type
- **Hermes native plugin** (primary) + MCP server (alternative)
- Single install per Hermes instance; each instance has its own SQLite file
- Does not interconnect across instances (each SQLite is independent)

## Overflow / Retention
- Bounded by disk space (single SQLite file)
- No built-in automatic pruning or decay
- SQLite's size is manageable for thousands of memories
- No cloud sync — each instance is fully self-contained

## Unique Features
- **Zero dependencies**: No API keys, no network calls, no Docker, no external services
- **Sub-millisecond recall**: In-process SQLite queries are extremely fast
- **Single SQLite file**: Simple, portable, backup-friendly
- **Direct MCP**: Stdio or SSE transport — no server process needed
- **Fully local**: 100% offline operation
- **MIT license**: Permissive

## Compatible Agents
Hermes (primary); any MCP-compatible agent via MCP server

## Pricing
- **Free**: Completely free, self-hosted, zero cost
- **No cloud tier**: Local only

## Public Metrics
- GitHub: ★ 2.0K (mnemosyne-oss/mnemosyne)
- Tagline: "The Zero-Dependency, Sub-Millisecond AI Memory System for Hermes Agents and Everyone Else!"
