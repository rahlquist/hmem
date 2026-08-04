# hmem Pilot — Corpus, Schemas, and Scoring Specification

**Spec version:** 1.0.0  
**Status:** reviewed, public-safe, ready for implementation  
**Task:** t_fce4a2e2 (hmem pilot corpus, schemas, and scoring rubric)  
**Upstream spec:** [EVALUATION_ENHANCEMENTS.md](../../EVALUATION_ENHANCEMENTS.md)

This directory specifies the reproducible hmem pilot: a corpus of 30 fully
synthetic memory-behavior cases, versioned JSON Schemas, a category-level
scoring rubric, provider compatibility/integration state, dev/held-out split
metadata, and privacy rules. It contains **no PDFs, no extracted paper text,
no private seeds, and no real conversation material**.

---

## 1. Scope

**IN**
- 30 synthetic scenario fixtures covering 10 required capability categories
  (3 each), validated against `scenario.schema.json`.
- Versioned JSON Schemas: scenario, run manifest, result payload, pilot registry.
- Category-level scoring rubric with verdict logic, metrics, and reporting rules.
- Provider registry: compatibility/integration state, claim provenance/evidence
  classes, dev/held-out split metadata, privacy rules.
- Validation tooling with a real JSON Schema validator and a documented
  standard-library fallback.

**OUT (for this task; covered by successor tasks)**
- Runner/report implementation (task t_8728060f).
- Provider reproducibility audit (task t_4f309a57).
- End-to-end integration and clean-machine dry run (task t_390f8f9e).

**ASSUMPTIONS (unresolved items are tracked in §8)**
- The pilot runs against built-in Hermes memory plus whichever providers are
  configured; unconfigured providers are recorded as `not-configured` and are
  never scored as measured.
- Held-out scenarios are published (they are synthetic); "held-out" means
  excluded from the development/tuning loop.
- All scenario timestamps are synthetic (July 2026) and exist only for temporal
  ordering.

---

## 2. Directory Layout

```
evaluation/
├── README.md                        <- this specification
├── PRIVACY.md                       <- privacy/public-safety rules (PRIV-01..10)
├── schemas/
│   ├── scenario.schema.json         <- v1.0.0
│   ├── run-manifest.schema.json     <- v1.0.0
│   ├── result.schema.json           <- v1.0.0
│   └── pilot-registry.schema.json   <- v1.0.0
├── rubric/
│   └── scoring-rubric.md            <- v1.0.0
├── fixtures/
│   ├── scenarios/                   <- 30 synthetic cases (10 categories x 3)
│   │   ├── RET-01-basic-retrieval.json
│   │   ├── ... (see §4)
│   ├── pilot-registry.json          <- providers, split, evidence classes, privacy rules
│   └── examples/
│       ├── example-manifest.json    <- conforming run manifest (dry-run example)
│       └── example-result.json      <- conforming result payload (dry-run example)
└── tools/
    └── validate_fixtures.py         <- schema validation + public-safety scan
```

---

## 3. Schemas (all v1.0.0, JSON Schema draft-07)

| Schema | File | Purpose |
|---|---|---|
| Scenario | `schemas/scenario.schema.json` | One synthetic case: id, category, split, origin, fictional world, privacy declaration, event history (`setup`), `probe`, answer key (`expected`), metric hints. |
| Run manifest | `schemas/run-manifest.schema.json` | Pinned environment/configuration for one comparable run: Hermes + provider versions, integration state, evidence class, models, retrieval config, hardware, dataset, seeds, baselines, redacted config. |
| Result payload | `schemas/result.schema.json` | One scenario outcome: raw answer, answer class, verdict, category metrics, evidence trace, latency/tokens/resources/cost, provenance. |
| Pilot registry | `schemas/pilot-registry.schema.json` | Provider integration states, dev/held-out split, claim evidence classes, integration-state definitions, privacy rules. |

Versioning: each schema has `"version"` and a stable `$id`; fixtures declare
`spec_version` and must match the schema version exactly. Breaking changes
bump the minor/major version; the `$id` changes accordingly.

---

## 4. Corpus — 30 Synthetic Cases

Fictional universe: user "Alex" runs a home-lab with hosts `valkyrie` (compute),
`thor` (NAS), `frigg` (edge), `odin` (router); projects `project-nimbus`
(data pipeline) and `project-cairn` (docs); tool `hlabctl`; fictional values
are used throughout so the base model cannot know them in advance
(see EVALUATION_ENHANCEMENTS, "Preventing Overfitting").

| Category | Dev | Held-out | Cases |
|---|---|---|---|
| retrieval | RET-01, RET-02 | RET-03 | paraphrase recall, distractor density, one-shot preference |
| temporal-updates | TEMP-01, TEMP-02 | TEMP-03 | newest-value-wins, superseded path, two-step change |
| selective-forgetting | FORGET-01, FORGET-03 | FORGET-02 | explicit deletion, invalidated+deleted, deleted+replacement |
| long-range-synthesis | SYNTH-01, SYNTH-02 | SYNTH-03 | cross-session combine, endpoint assembly, migration inference |
| procedural-memory | PROC-01, PROC-03 | PROC-02 | discovered fix, multi-step workflow, environment-specific |
| premise-awareness | PREM-01, PREM-02 | PREM-03 | false premise, assumed credential, obsolete host |
| isolation | ISO-01, ISO-02 | ISO-03 | profile boundary, project boundary, host boundary |
| abstention | ABST-01, ABST-02 | ABST-03 | never mentioned, related-but-absent, version never known |
| poisoning-resistance | POIS-01, POIS-02 | POIS-03 | untrusted web instruction, injected cleanup command, persistence |
| restart-recovery | RESTART-01, RESTART-03 | RESTART-02 | restart persistence, failed-init recovery, backup/restore |

Each fixture declares `split`, `difficulty`, `origin` (synthetic, public seed,
CC0-style license note), `privacy`, the full event history the runner must
ingest, the probe, and the answer key with `must_use_evidence` /
`must_not_use_evidence` event references.

---

## 5. Split Metadata

`fixtures/pilot-registry.json` → `split`:

- **dev (20):** RET-01, RET-02, TEMP-01, TEMP-02, FORGET-01, FORGET-03, SYNTH-01,
  SYNTH-02, PROC-01, PROC-03, PREM-01, PREM-02, ISO-01, ISO-02, ABST-01, ABST-02,
  POIS-01, POIS-02, RESTART-01, RESTART-03
- **held-out (10):** RET-03, TEMP-03, FORGET-02, SYNTH-03, PROC-02, PREM-03,
  ISO-03, ABST-03, POIS-03, RESTART-02
- **immutable regression core (7):** RET-01, TEMP-01, FORGET-01, SYNTH-01,
  ABST-01, POIS-01, RESTART-01 (never changed; refresh rotates the rest)

Policy: dev cases may be used to develop and tune the harness; held-out cases
are frozen and excluded from the development loop, reserved for final reporting.
Both are published because all cases are synthetic (PRIV-08).

---

## 6. Provider Compatibility / Integration State

`fixtures/pilot-registry.json` → `providers` records, for each pilot target,
its integration state (bundled / third-party-plugin / mcp-only /
hook-integration / documented-untested / tested-hermes-release /
not-configured) and claim evidence class. Pilot targets:

- **hermes-builtin-memory** — bundled, always active alongside any external provider.
- **hermes-session-search** — bundled retrieval baseline over past sessions.
- **lexical-baseline** — reference retrieval baseline (no provider claims).
- **no-memory** — reference: no provider at all (measures the base model).
- **hindsight** — third-party plugin; currently `not-configured` in this
  environment (recorded, never scored as measured until configured).
- **mnemosyne** — third-party plugin; currently `not-configured`.

The registry's `status` field records the observed state of each provider in
the development environment. The integration task must record setup failures
verbatim and must distinguish dry-run/simulated results from `hmem-measured`
measurements (EVALUATION_ENHANCEMENTS, "Controlled Run Contract").

---

## 7. Claim Provenance / Evidence Classes

From EVALUATION_ENHANCEMENTS ("Evidence and Catalogue Improvements"):

| Class | Meaning |
|---|---|
| `hmem-measured` | Measured by this benchmark in a controlled run. |
| `independently-reproduced` | Reproduced by an independent party. |
| `vendor-documented` | Documented by the vendor. |
| `vendor-benchmark` | Vendor-published benchmark score. |
| `community-reported` | Reported by community/users. |
| `inferred` | Inferred from architecture or documentation. |
| `unknown` | No evidence. |

Every provider record and every result payload carries an evidence class;
downstream reports must keep evidence classes visible and never promote a
`vendor-benchmark` or `dry-run` result to `hmem-measured`.

---

## 8. Unresolved Assumptions

1. **External provider availability.** Hindsight and Mnemosyne are not
   configured in the development environment (checked 2026-08-04). If the
   integrator cannot configure them, the report records setup failure and
   scores only built-in/reference providers; no provider measurement is
   fabricated.
2. **Held-out semantics.** Held-out cases are published (synthetic); a future
   private rotating challenge set is out of scope for the pilot.
3. **Judge reproducibility.** `answer_class` classification depends on the
   named judge model; manual adjudication overrides are recorded, not silent.
4. **License of adapted cases.** Pilot v1 fixtures are original synthetic
   content (no adaptation); future adapted cases must populate `origin.source_ref`
   and `license` before inclusion (PRIV-09).
5. **Timestamps.** Scenario timestamps are synthetic and only used for temporal
   ordering; they do not claim real-world dates.

---

## 9. Traceability to EVALUATION_ENHANCEMENTS.md

| Requirement | Where satisfied |
|---|---|
| Versioned scenario schema, run manifest, result schema (Implementation Sequence #2) | `schemas/*.json` v1.0.0 |
| ~30 reviewed cases across 10 capabilities (Implementation Sequence #3, Capability Matrix) | `fixtures/scenarios/` (30 cases, 3 per category) |
| Category-level results before aggregate (Measurements) | `rubric/scoring-rubric.md` §3, §5 |
| Dev/held-out separation, immutable regression core (Preventing Overfitting) | `pilot-registry.json` → `split` |
| Public seeds retained, private seeds held out (Preventing Overfitting) | `origin.seed_kind`, manifest `seeds` (PRIV-04) |
| Invented facts the base model cannot know (Preventing Overfitting) | Fictional `world` + invented values in every fixture |
| Evidence classes (Evidence and Catalogue Improvements) | `pilot-registry.json` → `claim_evidence_classes`, result `provider.evidence_class` |
| Integration state, not boolean (Evidence and Catalogue Improvements) | `pilot-registry.json` → `integration_states`, provider records |
| Privacy-safe interaction shapes, no transcripts (Sources of Test Material) | `PRIVACY.md` (PRIV-01..02), fixtures' `privacy` blocks |
| Public docs cite stable URLs, local copies stay local (Sources of Test Material) | `PRIVACY.md` (PRIV-03, PRIV-09) |
| Controlled Run Contract pinning | `run-manifest.schema.json` (all pinned fields required) |
| Compare vs built-in memory, session_search, lexical baseline, no-memory | `pilot-registry.json` → providers list |

---

## 10. Review Status

Reviewed against EVALUATION_ENHANCEMENTS.md requirements and the child task
t_390f8f9e acceptance criteria (validate every scenario, ~30 cases across all
10 categories, no private material staged). Public-safety scan and schema
validation are run by `tools/validate_fixtures.py`; commands and results are
reported in the task handoff.
