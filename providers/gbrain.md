# gbrain — Opinionated Knowledge Graph Brain for Hermes/OpenClaw

## End Goal
Provide an opinionated, self-hosted knowledge graph brain for AI agents that integrates with Obsidian for knowledge management and uses fabric for structured memory extraction.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Obsidian vault (Markdown files on disk) |
| **Database type** | None — plain Markdown files in an Obsidian vault |
| **Data at rest** | Plain text Markdown files; no encryption at rest |
| **Data in transit** | None — fully local |
| **Authentication** | None; relies on filesystem permissions |
| **Encryption** | None; OS-level filesystem permissions only |
| **Compliance** | Full data sovereignty; data never leaves the machine |
| **Multi-tenant** | No — single vault per instance |

## How It Works
gbrain is a knowledge graph engine built specifically for Hermes Agent and OpenClaw. It stores memories as a graph of interconnected concepts, with each node representing a fact, entity, or relationship. It uses Obsidian as its primary knowledge store (reading and writing Markdown notes) and leverages the fabric plugin system for structured memory extraction and recall. The graph structure enables multi-hop reasoning across stored memories.

## Hermes Integration
- **Native plugin**: Configured via `memory.provider: gbrain` or as a Hermes plugin
- **MCP server**: Available for external agent access
- **Obsidian integration**: Reads/writes directly to Obsidian vault
- **Fabric integration**: Uses fabric prompts for structured memory extraction
- **Profile isolation**: Each Hermes profile gets its own gbrain instance

## Install Type
- **Hermes native plugin** + standalone MCP server
- Installs per Hermes instance; does not interconnect on its own
- Obsidian vault is shared if multiple instances point to the same vault

## Overflow / Retention
- Bounded by Obsidian vault size (filesystem limit)
- No built-in automatic pruning or decay
- Graph structure allows manual curation of nodes and edges
- Obsidian's native organization (folders, tags, links) provides overflow management

## Unique Features
- **Knowledge graph**: Relationships between memories are explicit and traversable
- **Obsidian-native**: Uses your existing Obsidian vault as the source of truth
- **Fabric integration**: Structured memory extraction via fabric prompts
- **Opinionated**: Comes with pre-built prompts and workflows — not a blank slate
- **Multi-hop reasoning**: Graph traversal enables finding connections across stored facts
- **Self-hosted**: No cloud dependencies, no API keys needed

## Compatible Agents
Hermes, OpenClaw (primary targets); any MCP-compatible agent via MCP server

## Pricing
- **Free**: Self-hosted, open-source
- **No cloud tier**: Fully local operation

## Public Metrics
- GitHub: ★ 27.6K (garrytan/gbrain)
- Weekly growth: +406 stars/wk
- Primary ecosystem: Hermes Agent + OpenClaw
