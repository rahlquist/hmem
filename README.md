# hmem — Hermes Memory Provider Comparison

> A community-maintained comparison of memory add-ons and providers compatible with Hermes Agent.
> Last updated: 2026-08-07.

## Measured Benchmark Results

The current controlled benchmark compares the two providers with real measured
adapters over 30 reviewed scenarios, 10 categories, and three isolated runs
(180 measured result documents, zero failures):

| Provider | Overall correctness | Runs | Results |
|---|---:|---:|---:|
| BM25 lexical baseline | 0.367 | 3 | 90 |
| Hermes built-in memory | 0.333 | 3 | 90 |

See the [full category-by-category comparison](evaluation/results/provider-comparison.md)
and [machine-readable JSON](evaluation/results/provider-comparison.json). Hindsight
and Mnemosyne are listed as **not measured** because real measured adapters have
not been implemented; their simulated stubs are excluded from these scores.

## Quick Reference — All Providers

| # | Provider | Repo | Stars | Storage | Security | Type | Cost | Agents | Key Differentiator |
|---|----------|------|-------|---------|----------|------|------|--------|--------------------|
| 1 | [mem0](#mem0) | [mem0ai/mem0](https://github.com/mem0ai/mem0) | ★ 62.3K | Qdrant/PostgreSQL (self-hosted) or cloud | TLS in transit; API-key auth; SOC 2 + HIPAA (cloud) | MCP + native plugin | Free tier / $19/mo / $249/mo Pro | Claude, Codex, Cursor, Hermes, OpenClaw, Gemini | Triple-store (vector + KV + graph); LLM auto-extraction of facts |
| 2 | [Supermemory](#supermemory) | [supermemoryai/supermemory](https://github.com/supermemoryai/supermemory) | ★ 28.7K | Custom vector graph engine (self-hosted or cloud) | TLS; API-key auth; context fencing prevents pollution | MCP + native plugin | Free tier / paid plans | Claude, Codex, Cursor, Hermes | Custom vector graph + hybrid RAG; context fencing |
| 3 | [OpenViking](#openviking) | [volcengine/OpenViking](https://github.com/volcengine/OpenViking) | ★ 27.7K | Filesystem hierarchy (self-hosted only) | AGPL-3.0; fully local; no network exposure | MCP + native plugin | Free (self-hosted, AGPL-3.0) | Claude, Hermes | Tiered L0/L1/L2 loading; 80–90% token reduction |
| 4 | [gbrain](#gbrain) | [garrytan/gbrain](https://github.com/garrytan/gbrain) | ★ 27.6K | Obsidian vault (Markdown files on disk) | Local-only; no network; file-level access control | MCP + native plugin | Free (self-hosted) | Hermes, OpenClaw | Knowledge graph brain; Obsidian-native; fabric integration |
| 5 | [Hindsight](#hindsight) | [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) | ★ 19.0K | Local filesystem or cloud backend | MIT license; local-first; optional cloud TLS | MCP + native plugin | Free self-hosted / paid cloud | Hermes, Claude | Retain/recall/reflect cycles; knowledge graph synthesis |
| 6 | [Honcho](#honcho) | [plastic-labs/honcho](https://github.com/plastic-labs/honcho) | ★ 6.4K | Honcho Cloud (PostgreSQL) or self-hosted | TLS; OAuth; API-key auth; self-hosted option | MCP + native plugin | Free (self-hosted) / cloud | Hermes, Claude | User modeling with dialectic reasoning |
| 7 | [ByteRover](#byterover) | [campfirein/byterover-cli](https://github.com/campfirein/byterover-cli) | ★ 4.9K | Git repository (plain text files) | Git-based; file-level permissions; fully local | MCP + native plugin | Free / paid | Hermes, Claude | Memory as a git repo; 5-tier retrieval; version-controlled |
| 8 | [Mnemosyne](#mnemosyne) | [mnemosyne-oss/mnemosyne](https://github.com/mnemosyne-oss/mnemosyne) | ★ 2.0K | Single SQLite file (local) | Zero network exposure; no API keys; file-level permissions | MCP + native plugin | Free (self-hosted, MIT) | Hermes | Zero-dependency; sub-millisecond recall |
| 9 | [Memori](#memori) | [MemoriLabs/Memori](https://github.com/MemoriLabs/Memori) | ★ ? | Memori Cloud (backend not disclosed) | TLS; API-key auth; cloud-only (no local option) | MCP + native plugin | Free tier / paid | Hermes | Tool-aware memory; structured project/session attribution |
| 10 | [ClawMem](#clawmem) | [yoloshii/ClawMem](https://github.com/yoloshii/ClawMem) | ★ 195 | Local filesystem (on-device) | Zero cloud deps; no network calls; fully local | MCP server + hooks | Free (self-hosted) | Claude, Hermes, OpenClaw | On-device memory; hooks + hybrid RAG; no cloud |
| 11 | [Sibyl-Memory](#sibyl-memory) | [Sibyl-Labs/Sibyl-Memory](https://github.com/Sibyl-Labs/Sibyl-Memory) | ★ 98 | Structured files on disk (no DB) | No vector DB; no embeddings; fully local | MCP server + Hermes adapter | Free (self-hosted) | Hermes, Claude, Codex | 5-package family; file-based; no vector DB needed |
| 12 | [Plur](#plur) | [plur-ai/plur](https://github.com/plur-ai/plur) | ★ 232 | YAML engram files on disk (shared FS) | Open format; file-level permissions; git-compatible | MCP + native plugin | Free (MIT) | Hermes, Claude | Shared memory; open engram YAML format; multi-agent |
| 13 | [SignetAI](#signetai) | [Signet-AI/signetai](https://github.com/Signet-AI/signetai) | ★ 227 | Local filesystem (portable state file) | Local-first; no cloud; secrets encrypted at rest | MCP server | Free / paid | Hermes, Claude, Codex, OpenClaw | Identity + memory + secrets in one portable package |
| 14 | [YantrikDB](#yantrikdb) | [yantrikos/yantrikdb-hermes-plugin](https://github.com/yantrikos/yantrikdb-hermes-plugin) | ★ 76 | Embedded SQLite (Rust, in-process) | Zero network; embedded; no external services | Hermes native plugin | Free (self-hosted) | Hermes | Self-maintaining; contradiction tracking; explainable recall |
| 15 | [AgentMemory](#agentmemory) | [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) | ★ ? | Server-side (configurable backend) | TLS; API-key auth; Docker deployment option | MCP server (53 tools) | Free (self-hosted) | Hermes, Claude, Codex, Cursor, Gemini, Copilot | Most comprehensive toolkit; 53 tools; real-time viewer |

## Provider Detail Pages

Each provider listed above has a dedicated subdirectory under `providers/` with a full specification page.

| # | Provider | Spec Page |
|---|----------|-----------|
| 1 | mem0 | [providers/mem0.md](providers/mem0.md) |
| 2 | Supermemory | [providers/supermemory.md](providers/supermemory.md) |
| 3 | OpenViking | [providers/openviking.md](providers/openviking.md) |
| 4 | gbrain | [providers/gbrain.md](providers/gbrain.md) |
| 5 | Hindsight | [providers/hindsight.md](providers/hindsight.md) |
| 6 | Honcho | [providers/honcho.md](providers/honcho.md) |
| 7 | ByteRover | [providers/byterover.md](providers/byterover.md) |
| 8 | Mnemosyne | [providers/mnemosyne.md](providers/mnemosyne.md) |
| 9 | Memori | [providers/memori.md](providers/memori.md) |
| 10 | ClawMem | [providers/clawmem.md](providers/clawmem.md) |
| 11 | Sibyl-Memory | [providers/sibyl-memory.md](providers/sibyl-memory.md) |
| 12 | Plur | [providers/plur.md](providers/plur.md) |
| 13 | SignetAI | [providers/signetai.md](providers/signetai.md) |
| 14 | YantrikDB | [providers/yantrikdb.md](providers/yantrikdb.md) |
| 15 | AgentMemory | [providers/agentmemory.md](providers/agentmemory.md) |

## Nightly Scan — New Providers Detected (2026-08-07)

The automated scanner (GitHub topic `hermes-memory-provider`, HermesAtlas, awesome-hermes-agent) found 4 repositories not yet listed in the table above. They are logged here for review; add full spec pages if/when they warrant inclusion:

- [1ch1n/mychatarchive](https://github.com/1ch1n/mychatarchive) (★ 58) — Local-first AI memory archive; imports ChatGPT, Claude, and Grok exports, generates semantic embeddings, searches via MCP server. Zero cloud, zero cost.
- [penfieldlabs/hermes-penfield](https://github.com/penfieldlabs/hermes-penfield) (★ 3) — Penfield memory provider for Hermes agent.
- [raman325/hermes-mempalace-mcporter](https://github.com/raman325/hermes-mempalace-mcporter) (★ 2) — Hermes MemoryProvider plugin routing through mempalace's MCP server via mcporter + an MCP aggregator (phase 2 companion to MemPalace/mempalace#1684).
- [hermes-pro/mem0](https://github.com/hermes-pro/mem0) (★ 1) — Codex & OpenRouter compatible local Mem0 memory for Hermes agent.

Also refreshed from the scan: `yantrikos/yantrikdb-hermes-plugin` now ★ 78 (previously listed ★ 76).

## Nightly Scan — No New Providers (2026-08-08)

The automated scanner (GitHub topic `hermes-memory-provider`, HermesAtlas, awesome-hermes-agent) found no new repositories since the 2026-08-07 scan. The same 5 repos remain on the topic; the cache was refreshed (star counts may have shifted slightly — see `.scan/.scan_cache/last_scan.json`).

## Nightly Scan — No New Providers (2026-08-11)

The automated scanner (GitHub topic `hermes-memory-provider`, HermesAtlas, awesome-hermes-agent) found no new repositories since the 2026-08-08 scan. The same 5 repos remain on the topic; the cache was refreshed (star counts may have shifted slightly — see `.scan/.scan_cache/last_scan.json`).

## How to Use This Repo

1. Pick a provider from the table above.
2. Read its spec page in `providers/` for installation, configuration, and feature details.
3. Configure Hermes: `hermes memory setup` or edit `~/.hermes/config.yaml`.
4. Only **one** external memory provider can be active at a time in Hermes (built-in MEMORY.md/USER.md is always active alongside it).

## Notes on Metrics

- GitHub stars are taken from public repo data at time of research (2026-07-31).
- Star counts are a rough popularity signal, not a quality ranking.
- "Agents" column indicates which AI agent frameworks the provider explicitly supports via MCP or native plugin.
- Pricing reflects publicly available tiers as of research date; always verify on the provider's site.

## Cron Job

A nightly scan job is configured to check for new memory providers and updates. See [cron setup](#cron-job).
