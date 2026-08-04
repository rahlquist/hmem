# Evaluation Enhancements

## Assessment

`hmem` can become a useful memory-provider evaluation, but its value will come
from longitudinal evidence rather than catalogue size. The current repository
is a sound discovery baseline: it records candidates, architectures, operating
models, and claimed differentiators. The next maturity step is to make every
recommendation reproducible under a pinned Hermes workload.

The present Hindsight recommendation should therefore be treated as a working
hypothesis. It becomes a supported conclusion only after the same workload,
models, budgets, and scoring rules have been applied to Hindsight, competing
providers, and simple baselines.

Over time the repository can support three distinct decisions:

1. Which providers are technically compatible with a given Hermes release?
2. Which memory behaviors does each provider implement correctly?
3. Which provider offers the best quality, cost, and operational tradeoff for a
   stated workload?

Keeping those questions separate prevents popularity, feature count, and
vendor benchmark scores from being mistaken for observed effectiveness.

## Proposed Benchmark

The benchmark should evaluate memory behavior, not general world knowledge. A
provider should not be rewarded because its model already knows an answer. It
should be rewarded when the answer depends on information supplied during the
test history and when it correctly ignores information that is stale,
irrelevant, deleted, or untrusted.

### Sources of Test Material

No single corpus represents the random things humans may ask an AI. Use a
stratified mixture instead:

- **Public benchmark adapters.** Import or adapt cases from LoCoMo,
  LongMemEval, MemoryAgentBench, Memora/FAMA, LongMemEval-V2, and MPBench where
  licenses permit. These provide externally defined tasks for conversational
  recall, temporal reasoning, selective forgetting, experiential knowledge,
  and memory poisoning.
- **Hermes workload scenarios.** Build synthetic histories modeled on research,
  coding, configuration, and infrastructure work: host-specific facts,
  procedures discovered through failures, project conventions, user
  preferences, and facts that change across sessions.
- **Privacy-safe interaction shapes.** Derive categories and event structures
  from real Hermes use, but replace names, addresses, credentials, file paths,
  and distinctive facts. Do not publish conversation transcripts.
- **Generated mutation families.** Transform seed scenarios by changing entity
  names, values, ordering, paraphrase, distractor density, time gaps, and the
  point at which a fact is corrected or deleted. Generation creates coverage;
  deterministic validators and human review establish correctness.
- **Community challenge cases.** Accept small, schema-validated cases with an
  answer key, provenance, license, and declared capability category. Hold some
  accepted cases out of public development runs.

The public papers previously collected under `memorypapers/` may inform the
taxonomy and metrics. Their local PDF, DOCX, archive, and extracted-text copies
must remain local-only. Public documentation should cite stable DOI, arXiv, or
publisher URLs rather than committing those source files or copied full text.

### Capability Matrix

Each case should isolate one primary capability while recording secondary
requirements:

| Capability | Example behavior |
|---|---|
| Accurate retrieval | Recall a supplied fact despite paraphrases and distractors |
| Temporal validity | Use the newest valid value and reject superseded values |
| Selective forgetting | Exclude explicitly deleted or invalidated facts |
| Long-range synthesis | Combine evidence introduced in separate sessions |
| Procedural memory | Reuse a discovered workflow or environment-specific fix |
| Premise awareness | Reject a question whose premise conflicts with current memory |
| Isolation | Prevent facts crossing user, profile, project, or host boundaries |
| Abstention | Say that evidence is absent instead of inventing a memory |
| Poisoning resistance | Keep untrusted retrieved instructions from becoming authority |
| Recovery | Preserve or restore valid memory after restart or provider failure |

### Preventing Overfitting

- Keep development and held-out test sets separate.
- Publish scenario generators and schemas, but retain private random seeds and a
  rotating challenge set.
- Use invented facts that the base model cannot know in advance.
- Run multiple paraphrases and entity substitutions per semantic case.
- Test at multiple history lengths and distractor ratios.
- Freeze the provider before revealing held-out results.
- Report repeated-run variance and failures, not only the best run.
- Refresh part of the challenge set periodically while preserving an immutable
  regression core.

### Controlled Run Contract

Every comparable run must pin and report:

- Hermes version or commit
- Provider version or commit and deployment mode
- Generator, embedding, reranking, and judge models
- Prompt and retrieval configuration
- Recall/token budget
- Hardware and operating system
- Dataset and benchmark versions
- Random seeds and repetition count
- Whether a result is independently reproduced or vendor-reported

Compare external providers against built-in Hermes memory, `session_search`, a
simple lexical or vector retrieval baseline, full-context replay where
feasible, and no-memory operation. Scores from different benchmarks must not be
placed on one ranking scale.

### Measurements

Report category-level results before any aggregate score:

- Evidence retrieval precision and recall
- Answer correctness and evidence-groundedness
- Stale or deleted memory reuse rate
- Abstention correctness
- Cross-boundary leakage rate
- Poisoning attack success and persistence
- Ingest and recall p50/p95 latency
- Tokens stored, retrieved, and injected
- CPU, peak RAM, disk growth, and network egress
- Setup success, restart recovery, backup/restore, and deletion verification
- Monetary cost at a declared workload

If an aggregate is eventually added, publish the weights and retain the raw
metrics. Different users should be able to apply different weights without
rerunning the benchmark.

## Evidence and Catalogue Improvements

Each provider claim should include a canonical source, upstream revision,
access date, deployment mode, and evidence class:

- `hmem-measured`
- `independently-reproduced`
- `vendor-documented`
- `vendor-benchmark`
- `community-reported`
- `inferred`
- `unknown`

Hermes compatibility should be recorded as an integration state rather than a
boolean: bundled plugin, third-party plugin, MCP-only, hook integration,
documented but untested, or tested against a named Hermes release. Known setup
and runtime failures belong beside compatibility claims.

Candidate eligibility should distinguish memory providers from context
managers, session stores, knowledge bases, identity stores, and memory-hygiene
skills. Track excluded candidates with a reason so catalogue completeness can
be audited.

## Implementation Sequence

1. Add provenance fields and correct stale provider records.
2. Define a versioned scenario schema, run manifest, and result schema.
3. Implement a small end-to-end pilot using built-in Hermes memory, Hindsight,
   Mnemosyne, and one simple baseline across approximately 30 reviewed cases.
4. Add temporal updates, deletion, isolation, and poisoning cases before
   expanding provider coverage.
5. Add public benchmark adapters and larger held-out suites.
6. Automate environment capture, repeated runs, result validation, and report
   generation.
7. Publish workload-specific conclusions with limitations and confidence, then
   revise them as provider versions and evidence change.

## Success Criteria

The evaluation is useful when another person can reproduce a run, inspect the
evidence behind every material claim, apply their own metric weights, and reach
the same conclusion within stated variance. Until then, recommendations should
remain explicitly provisional.

## Public References

- MemoryAgentBench: https://arxiv.org/abs/2507.05257
- Memora and FAMA: https://arxiv.org/abs/2604.20006
- LongMemEval-V2: https://arxiv.org/abs/2605.12493
- MPBench: https://arxiv.org/abs/2606.04329
- Existing local source index: `memorypapers/README.md`