# Plur — Shared Memory with Open Engram YAML Format

## End Goal
Provide a shared memory layer for multi-agent systems using an open, portable engram format based on YAML — enabling multiple agents and instances to share and synchronize memories.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | YAML engram files on shared filesystem |
| **Database type** | None — plain YAML files |
| **Data at rest** | Plain text YAML; no encryption at rest |
| **Data in transit** | None — local filesystem; shared FS if multi-instance |
| **Authentication** | None; relies on filesystem permissions |
| **Encryption** | None; OS-level filesystem permissions only |
| **Compliance** | Full data sovereignty; files are human-readable |
| **Multi-tenant** | Yes — shared filesystem allows multiple agents/instances |

## How It Works
Plur stores memories as "engrams" — structured YAML documents that are portable across agents and platforms. The engram format is open and well-defined, meaning any system that can read YAML can access Plur memories. This makes Plur uniquely suited for multi-agent setups where different agents (Hermes, Claude, etc.) need to share a common memory base. Engrams are stored as files on disk, making them version-controllable and portable.

## Hermes Integration
- **Native plugin**: `memory.provider: plur` in `~/.hermes/config.yaml`
- **MCP server**: Available for external agent access
- **Shared storage**: Engrams stored as YAML files — can be on a shared filesystem
- **Multi-agent**: Designed for multi-agent systems from the ground up

## Install Type
- **Hermes native plugin** (primary) + MCP server
- Shared storage model — multiple instances can read/write the same engram files
- Self-contained per installation but designed for sharing

## Overflow / Retention
- File-based storage bounded by disk space
- YAML format is human-readable and manually editable
- No built-in automatic pruning — engrams accumulate until manually managed
- Version control (git) is a natural fit for engram files

## Unique Features
- **Open engram YAML format**: Portable across agents and platforms
- **Multi-agent by design**: Built for shared memory across multiple agents
- **No proprietary format**: Plain YAML — any system can read/write
- **Version-controllable**: Engrams are files; use git for history
- **MIT license**: Permissive, fully open-source

## Compatible Agents
Hermes, Claude, any MCP-compatible agent, any system that reads YAML

## Pricing
- **Free**: MIT license, self-hosted
- **No cloud tier**: Local only

## Public Metrics
- GitHub: ★ 232 (plur-ai/plur)
- Weekly growth: +3 stars/wk
- Primary use case: Multi-agent shared memory
