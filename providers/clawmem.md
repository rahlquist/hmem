# ClawMem — On-Device Memory with Hooks + Hybrid RAG

## End Goal
Provide an on-device memory layer for AI agents that works entirely locally with no cloud dependencies, using hooks for automatic memory capture and hybrid RAG for retrieval.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Local filesystem (on-device) |
| **Database type** | None — local file storage |
| **Data at rest** | Plain files on disk; no encryption at rest |
| **Data in transit** | None — fully local, no network communication |
| **Authentication** | None — no API keys, no network |
| **Encryption** | None; relies on OS-level filesystem permissions |
| **Compliance** | Full data sovereignty; zero external exposure |
| **Multi-tenant** | No — single-device, single-user |

## How It Works
ClawMem runs entirely on-device with no cloud dependencies. It uses a hook-based system to automatically capture relevant information from agent interactions, and a hybrid RAG search combining vector similarity with keyword matching for retrieval. The system is designed to be lightweight and self-contained — it stores everything locally and requires no external services.

## Hermes Integration
- **MCP server**: HTTP-based MCP server for external agent access
- **Hooks**: Automatic memory capture from agent interactions
- **Hermes plugin**: Compatible via MCP server connection
- **Storage**: Local filesystem
- **No cloud**: 100% offline operation

## Install Type
- **Standalone MCP server** (primary) + hooks system
- Self-contained per installation; does not interconnect on its own
- Can be pointed to by multiple Hermes instances (same MCP endpoint)

## Overflow / Retention
- Bounded by local disk space
- Hook-based capture can be configured to filter what gets stored
- No built-in automatic pruning
- Hybrid RAG naturally manages relevance — stale memories rank lower in search

## Unique Features
- **On-device only**: No cloud dependencies, no API keys
- **Hooks system**: Automatic memory capture from agent interactions
- **Hybrid RAG**: Combines vector similarity + keyword matching for robust retrieval
- **Multi-agent support**: Works with Claude Code, Hermes, and OpenClaw
- **Lightweight**: Minimal dependencies, runs on consumer hardware

## Compatible Agents
Claude Code, Hermes, OpenClaw — any MCP-compatible agent

## Pricing
- **Free**: Self-hosted, no cloud tier
- **No paid plans**: Completely free

## Public Metrics
- GitHub: ★ 195 (yoloshii/ClawMem)
- Weekly growth: +1 star/wk
- Primary use case: On-device, privacy-first memory for coding agents
