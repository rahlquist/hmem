# OpenViking — Self-Evolving Context Database with Tiered Loading

## End Goal
Provide a self-evolving context database for AI agents that unifies agent memory, knowledge RAG, and skills management with deterministic context browsing and aggressive token savings.

## Storage & Security

| Aspect | Detail |
|--------|--------|
| **Storage backend** | Filesystem hierarchy (local files and directories) |
| **Database type** | None — pure filesystem storage |
| **Data at rest** | Plain files on disk; no encryption at rest by default |
| **Data in transit** | None — fully local, no network communication |
| **Authentication** | None required; filesystem permissions control access |
| **Encryption** | None; relies on OS-level filesystem permissions |
| **Compliance** | Full data sovereignty — data never leaves the machine |
| **Multi-tenant** | No — single-user, single-instance design |

## How It Works
OpenViking uses a filesystem-hierarchy-based storage model with a tiered loading system (L0 → L1 → L2). L0 loads ~50-token abstracts for quick context, L1 loads ~500-token overviews for moderate detail, and L2 loads full content on demand. The `viking://` protocol provides deterministic context browsing — agents can traverse the memory directory structure like a filesystem, and the system tracks which resolution level each query needs. This mechanism delivers 80–90% token reduction compared to full memory injection.

## Hermes Integration
- **Native plugin**: `memory.provider: openviking` in `~/.hermes/config.yaml`
- **Setup**: `hermes memory setup` → select "OpenViking"
- **Protocol**: `viking://` URIs for deterministic context browsing
- **Storage**: Filesystem hierarchy; each profile gets its own directory
- **Self-hosted only**: No cloud option; full data sovereignty

## Install Type
- **Hermes native plugin** (bundled with Hermes Agent)
- Self-contained per Hermes instance; filesystem-based storage
- Does not interconnect across instances (each has its own filesystem tree)

## Overflow / Retention
- Tiered loading naturally manages overflow — only needed resolution is loaded
- Filesystem storage bounded by disk space
- No built-in automatic pruning; manual or scripted cleanup
- L0 abstracts are always cheap to load; L2 full content is loaded on demand only

## Unique Features
- **Tiered L0/L1/L2 loading**: 80–90% token savings by loading only needed resolution depth
- **viking:// protocol**: Deterministic, filesystem-like context browsing
- **Self-evolving**: Context database adapts to usage patterns
- **Observable retrieval**: Directory-browsing trajectories are visible and auditable
- **Unified**: Combines memory, knowledge RAG, and skills in one system
- **AGPL-3.0**: Fully open-source, self-hosted only

## Compatible Agents
Hermes (primary), any agent that can use the viking:// protocol or HTTP API

## Pricing
- **Free**: Self-hosted, AGPL-3.0, no cloud tier
- **Cost**: Infrastructure only (self-hosted)

## Public Metrics
- GitHub: ★ 27.7K (volcengine/OpenViking)
- Weekly growth: +470 stars/wk
- Token reduction: 80–90% vs full memory injection
- LoCoMo benchmark leader (91% multi-hop, 95.4% single-hop, 94.4% temporal)
