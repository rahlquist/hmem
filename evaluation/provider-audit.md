# Provider Integration & Reproducibility Audit — hmem Pilot

**Task:** t_8728060f · **Author profile:** infra · **Date:** 2026-08-04
**Scope:** exact, evidence-backed integration/setup/restart-recovery paths for built-in Hermes memory,
`session_search`/lexical baseline, Hindsight, and Mnemosyne; version pinning / environment capture;
compatibility matrix; clean-machine prerequisites; verification commands.

**Constraints honored:** no Hermes config modified, no secrets read or printed, no external provider
provisioning run, no local-only source material copied into the repo. All external claims carry a
public URL and were checked 2026-08-04.

---

## 1. Observed environment (local Hermes install, read-only inspection)

| Item | Observed value |
|---|---|
| Hermes version | v0.20.0 (2026.8.3) |
| Upstream commit | `9712b8f0` |
| Local commit | `f5be9236` (+1 carried commit) |
| Install method | git (`/home/rahlquist/.hermes/hermes-agent`) |
| Python | 3.11.15 |
| OpenAI SDK | 2.24.0 |
| `hermes memory status` | Built-in (MEMORY.md/USER.md) enabled; **Provider: (none — built-in only)** |
| Installed memory plugins | byterover, hindsight, holographic, honcho, mem0, openviking, retaindb, supermemory |
| mnemosyne plugin | **absent** (not in `plugins/memory/`, not in `hermes memory setup` provider list, no lazy-dep entry; only docstring/test mentions in source) |
| Provider SDKs in venv | hindsight-client / mnemosyne-memory **not installed** (lazy dep `hindsight-client==0.6.1` installs on first use) |
| session_search backend | SQLite state DB present (`state.db`, FTS5) |
| Host | Linux hermesvm01 (CachyOS 7.1.4-1), 6 CPU, ~15 GiB RAM |

## 2. Integration paths (exact commands)

### 2.1 hermes-builtin-memory — bundled, always active
- Files: `$HERMES_HOME/memories/MEMORY.md` (2,200 chars) + `USER.md` (1,375 chars); injected as a
  frozen system-prompt snapshot at session start; `memory` tool actions `add`/`replace`/`remove`;
  exact-duplicate rejection; injection/exfiltration scan on writes.
- Setup: none required (always on alongside any external provider).
- Restart-recovery: state lives on disk; re-injected on next session start. No service to restart.
- Config keys (docs): `memory.memory_enabled`, `memory.user_profile_enabled`,
  `memory.memory_char_limit`, `memory.user_char_limit`.
- Verify: `hermes memory status` shows built-in enabled.

### 2.2 hermes-session-search — bundled retrieval baseline
- Tool: `session_search` — FTS5 retrieval over the SQLite session store (`state.db`), no LLM calls.
  Four shapes: discovery (`query`), scroll (`session_id`+`around_message_id`), read (`session_id`),
  browse (no args); `limit` clamp [1,10]; `role_filter`, `sort` newest/oldest, cross-profile read.
- Setup: none; requires the SQLite state DB (auto-created).
- Restart-recovery: DB persists on disk; nothing to configure.
- Verify: `hermes sessions list`; a live chat that calls `session_search`.

### 2.3 lexical-baseline — harness reference (no provider claims)
- Not a Hermes integration. Runner must implement a deterministic, dependency-light baseline over the
  fixture corpus (recommend SQLite FTS5/BM25 over the synthetic event text, fixed `top_k`). Never
  promoted to a provider measurement; evidence class `inferred`/`hmem-measured` only if implemented
  and run by this harness.

### 2.4 hindsight — third-party plugin, bundled in Hermes v0.20.0
- Plugin ships at `plugins/memory/hindsight/` (config schema + MemoryProvider). Two modes:
  - **cloud** (default): needs API key from `ui.hindsight.vectorize.io`; endpoint `https://api.hindsight.vectorize.io`.
  - **local_external**: connect to an existing daemon, default `http://localhost:8888` (Docker `vectorizeio/hindsight` or `pip install hindsight-all`); needs an LLM provider key (e.g. `OPENAI_API_KEY`) for the daemon.
- Setup:
  ```
  hermes memory setup          # interactive → select "hindsight" (installs deps for chosen mode)
  # or manual:
  hermes config set memory.provider hindsight
  echo "HINDSIGHT_API_KEY=your-key" >> ~/.hermes/.env   # cloud mode only; never commit
  ```
- Deps: wizard installs `hindsight-client` (cloud) or `hindsight-all` (local); v0.20.0 pins
  `hindsight-client==0.6.1` (lazy dep). Docs require `hindsight-client >= 0.4.22`.
- Config: `$HERMES_HOME/hindsight/config.json` (env fallbacks `HINDSIGHT_API_KEY`, `HINDSIGHT_BANK_ID`,
  `HINDSIGHT_BUDGET`, `HINDSIGHT_API_URL`, `HINDSIGHT_MODE`, `HINDSIGHT_TIMEOUT`=120,
  `HINDSIGHT_IDLE_TIMEOUT`=300). Keys: `mode`, `api_key`, `api_url`, `bank_id` (default `hermes`),
  `recall_budget` (low/mid/high, default mid), `memory_mode` (hybrid/context/tools), `auto_retain`,
  `auto_recall`, `retain_context`, `retain_tags`, `retain_source`, `recall_tags`.
- Restart-recovery: after enabling, start a new session or `hermes gateway restart`. Rollback:
  `hermes memory off` (external provider only; built-in untouched).
- Verify: `hermes memory status` shows `hindsight` active.

### 2.5 mnemosyne — third-party plugin, NOT bundled in v0.20.0
- Vendor README claims "Hermes Agent | MCP + Plugin | Native — ships enabled", but this was **not
  observed** in v0.20.0: the shipped provider list is the 8 plugins above and mnemosyne is absent.
  Treat the native-plugin claim as `vendor-documented` / `documented-untested` for this release.
- Realistic path (vendor docs, `docs/hermes-integration.md`):
  ```
  pip install mnemosyne-memory[embeddings]   # or core / [all]; see RAM notes in §5
  pip install mnemosyne-hermes               # Hermes wrapper: plugin manifest + entry points
  hermes config set memory.provider mnemosyne
  # new session or hermes gateway restart
  ```
  Plugin manifest registers under `$HERMES_HOME/plugins/mnemosyne`, where Hermes discovers it.
- Embeddings: default model `BAAI/bge-small-en-v1.5` via `MNEMOSYNE_EMBEDDING_API_URL` /
  `MNEMOSYNE_EMBEDDING_API_KEY` (falls back to `OPENROUTER_API_KEY`, then `OPENAI_API_KEY`), or use
  the `[embeddings]` profile for local `fastembed`.
- MCP alternative: `mnemosyne mcp` (stdio/SSE) registered via `hermes mcp add`.
- Restart-recovery: after install/config, new session or `hermes gateway restart`; upgrades require
  `hermes gateway restart` too; rollback `hermes memory off`. Do **not** use `hermes tools disable memory`
  (disables the whole memory toolset).
- Verify: `hermes memory status` shows `mnemosyne` active.

## 3. Compatibility matrix (integration state per pilot-registry schema)

| Pilot target | Integration state | Deployment | Evidence class | Tested here? | Notes |
|---|---|---|---|---|---|
| hermes-builtin-memory | bundled | bundled-plugin | vendor-documented + observed | yes (active) | Always on; restart-safe |
| hermes-session-search | bundled | bundled-plugin | vendor-documented + source | yes (DB present) | Needs populated session DB for meaningful retrieval |
| lexical-baseline | documented-untested | none (harness) | inferred | no | Runner-implemented reference; not a provider |
| no-memory | bundled (reference) | none | n/a | yes (default) | Base-model reference |
| hindsight | third-party-plugin | cloud or local-daemon | vendor-documented | **no (not-configured)** | Plugin present; requires credential (cloud) or endpoint (local daemon) |
| mnemosyne | documented-untested / mcp-only | third-party-plugin (if installed) or mcp-server | vendor-documented | **no (absent, not-configured)** | Not bundled in v0.20.0; requires user install + embedding endpoint |

**Unavailable until the user supplies:**
- Hindsight cloud → `HINDSIGHT_API_KEY` (credential).
- Hindsight local → running daemon endpoint (`http://localhost:8888`) + LLM provider key.
- Mnemosyne → package install (`mnemosyne-hermes` + memory profile) + embedding API key
  (`MNEMOSYNE_EMBEDDING_API_KEY`/`OPENROUTER_API_KEY`/`OPENAI_API_KEY`) or ~800 MB RAM for local embeddings.

Per the Controlled Run Contract, unconfigured providers must be recorded with `setup_failures` verbatim,
integration_state `not-configured`, and must **never** be scored as measured; dry-run/simulated results
must be labelled separately from `hmem-measured`.

## 4. Version pinning / environment capture (run-manifest schema v1.0.0)

Capture every required manifest field with:

```bash
hermes version                                   # hermes.version + upstream/local commits
git -C "$(hermes version | sed -n 's/Install directory: //p')" rev-parse HEAD   # exact commit
<hermes-venv>/bin/pip list                       # full environment (provider SDK versions)
pip show hindsight-client mnemosyne-memory 2>/dev/null   # provider SDK pins when installed
uname -a; lscpu | head -5; free -h               # hardware (host/os/cpu/ram)
nvidia-smi --query-gpu=name,memory.total --format=csv   # gpu, if present
git -C <provider-repo> rev-parse HEAD            # provider commit when source-installed
```

Also record: models (`embedding`, `reranker`, `judge`, `extractor`), `retrieval_config`
(`recall_budget`, `top_k`, `context_window_chars`, `prompt_template_ref`, `injection_style`),
`dataset` (spec_version, scenario_ids, split, count), `seeds` (public_seed, repetition_count,
`private_seed_used:false` unless a private seed is supplied), `baselines` flags
(session_search/lexical_baseline/full_context_replay/no_memory), and `privacy.contains_no_secrets:true`.
`config_redacted` must be a human-readable summary with no secrets/tokens/paths.

## 5. Clean-machine prerequisites

- Python 3.11+ (Hermes v0.20.0 runs on 3.11.15), `uv` or pip, `git` (for commit pinning).
- Hermes install: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`
  (docs: https://hermes-agent.nousresearch.com/docs/).
- Built-in memory: writable `$HERMES_HOME/memories/`.
- session_search: writable `$HERMES_HOME/state.db` (auto-created).
- Hindsight cloud: egress to `api.hindsight.vectorize.io`; API key.
- Hindsight local: Docker (recommended, API :8888 / UI :9999) or `pip install hindsight-all`
  (~RAM varies; needs LLM provider key). Intel Mac: `hindsight-all-slim`.
- Mnemosyne: `mnemosyne-memory` core ~50 MB RAM / `[embeddings]` ~800 MB / `[all]` ~1.5 GB;
  embedding endpoint reachable (or local embeddings).

## 6. Verification commands

```bash
hermes version                       # version + commit
hermes memory status                 # built-in + active external provider
hermes sessions list                 # session-search backend alive
hermes memory setup                  # interactive; select hindsight/mnemosyne (only when provisioning is allowed)
hermes config set memory.provider <name>   # manual switch
hermes gateway restart               # apply provider change (or start a new session)
hermes mcp list && hermes mcp test <server>   # MCP path (mnemosyne)
hermes memory off                    # rollback to built-in only
```

Expected: `hermes memory status` lists the configured provider; after rollback it shows
`Provider: (none — built-in only)`.

## 7. Public citations (all checked 2026-08-04)

- Hermes Persistent Memory: https://hermes-agent.nousresearch.com/docs/user-guide/features/memory
- Hermes Memory Providers: https://hermes-agent.nousresearch.com/docs/user-guide/features/memory-providers
- Hermes Configuration: https://hermes-agent.nousresearch.com/docs/user-guide/configuration
- Session Search tool: https://hermes-agent.nousresearch.com/docs/user-guide/sessions#session-search-tool
- Hindsight repo (MIT): https://github.com/vectorize-io/hindsight · paper: https://arxiv.org/abs/2512.12818 · docs: https://hindsight.vectorize.io
- Mnemosyne repo (MIT): https://github.com/mnemosyne-oss/mnemosyne · Hermes guide: https://github.com/mnemosyne-oss/mnemosyne/blob/main/docs/hermes-integration.md · PyPI: https://pypi.org/project/mnemosyne-memory/
- Repo provider records: `providers/hindsight.md`, `providers/mnemosyne.md` (hmem, 2026-07-31)

## 8. Handoff notes for integrator (t_390f8f9e)

1. In this environment, hindsight and mnemosyne are **not configured**; record setup unavailability
   honestly (integration_state `not-configured`, `setup_failures` verbatim) and score only
   built-in/reference providers as measured.
2. `pilot-registry.json` (`evaluation/fixtures/`) was still missing at audit time (sibling deliverable);
   map this matrix's states into it when it lands.
3. Do not fabricate provider measurements; distinguish `dry-run`/`simulated` from `hmem-measured`.
4. This audit ran no provisioning, modified no Hermes config, and read no secrets.
