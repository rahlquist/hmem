# ByteRover — Memory as a Git Repo

## End Goal
Provide a portable, version-controlled memory layer for autonomous coding agents where memories are managed like source code — committed, branched, and merged.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Git repository (plain text files) |
| **Database type** | None — plain text files in a git repo |
| **Data at rest** | Plain text files; no encryption at rest |
| **Data in transit** | None — fully local; git remote optional |
| **Authentication** | None for local; git credentials for remote |
| **Encryption** | None; relies on filesystem/git permissions |
| **Compliance** | Full data sovereignty; files are human-readable |
| **Multi-tenant** | No — single repo per instance; can be shared via git remote |

## How It Works
ByteRover (formerly "Cipher") treats memory as a git repository. Each memory operation is a commit, each context switch is a branch, and memory consolidation across sessions is a merge. It uses a 5-tier retrieval system where 4 tiers are non-LLM (sub-100ms) and only the 5th tier uses LLM-based semantic search. This architecture makes retrieval extremely fast for the common case while still supporting deep semantic search when needed.

## Hermes Integration
- **Native plugin**: `memory.provider: byterover` in `~/.hermes/config.yaml`
- **Setup**: `hermes memory setup` → select "byterover"
- **CLI**: `brv` CLI for memory management (commit, branch, merge, log)
- **Storage**: Local git repo (portable, version-controlled)
- **MCP server**: Available for external agent access

## Install Type
- **Hermes native plugin** (primary) + standalone CLI + MCP server
- Single install per Hermes instance; memory stored in a git repo
- Portable: the git repo can be shared across instances or backed up

## Overflow / Retention
- Git-based storage: bounded by repo size
- Built-in version control: old memories are never deleted, just branched or pruned manually
- `brv vc commit/branch/merge` provides explicit memory lifecycle management
- 5-tier retrieval naturally manages context — only needed tiers are loaded

## Unique Features
- **Memory as git repo**: Full version control — commit, branch, merge, log for memories
- **5-tier retrieval**: 4 non-LLM tiers (sub-100ms) + 1 LLM semantic tier
- **Portable**: The memory repo is a standard git repo — backup, share, or migrate with git
- **brv CLI**: Full command-line interface for memory operations
- **Pre-compression extraction**: Memories are pre-compressed before storage, saving context window
- **LoCoMo benchmark leader**: 92.2% overall (95.4% single-hop, 94.4% temporal)

## Compatible Agents
Hermes, Claude, any MCP-compatible agent

## Pricing
- **Free**: Open-source CLI, self-hosted
- **Cloud sync**: Available (details on repo)

## Public Metrics
- GitHub: ★ 4.9K (campfirein/byterover-cli)
- Weekly growth: -1 star/wk (stable)
- LoCoMo: 92.2% overall
