# hmem Pilot — Integration & Verification Note

**Task:** t_390f8f9e (integrate, execute, and verify the reproducible hmem pilot)
**Date:** 2026-08-04
**Workspace:** the hmem repo (branch `main`, commit `2b205c3` + this integration)
**Artifact path (run outputs, local-only):** `pilot-out/integration/`
  (manifest.json, results/*.json = 120 raw results, validation_errors.json,
   report.md, report.json). `pilot-out/` is git-ignored by design — these are
   regenerable local run outputs, never published.
**Committed integration:** `pilot/convert_eval.py`, `pilot/tests/test_convert_eval.py`,
  Makefile targets, pilot/README.md, this note.

## What was integrated

The predecessor tasks produced (a) a 30-case reviewed synthetic corpus with
versioned schemas under `evaluation/`, (b) the deterministic dry-run runner
and report under `pilot/` (15 self-contained fixtures), and (c) a provider
audit (`evaluation/provider-audit.md`). This task integrated them: a thin
converter (`pilot/convert_eval.py`) adapts the full 30-case reviewed corpus
into the pilot's minimal scenario schema so the documented clean-machine
dry-run path runs the complete corpus. No valid predecessor work was
overwritten; the pilot's own 15 fixtures remain and still validate.

Mapping is deterministic and documented in the module docstring: eval ids
lowercased (`ABST-01` -> `abst-01`, original kept in provenance notes),
kebab-case categories mapped to the pilot enum (10/10), `held-out` split
preserved, setup events -> history turns (session/timestamp/untrusted kept),
`expected` fields (answer/abstain/reject_premise/superseded/deleted with the
directive wrapper stripped) mapped for scoring, provenance marked reviewed,
privacy marked fully synthetic. Known limitation recorded (not hidden):
isolation boundaries live in eval probe prose, so converted ISO scenarios
carry no machine-readable boundary and the deterministic stubs measure
leakage with all facts in scope.

## Exact commands and results

```bash
cd hmem   # repo root (path shown relative; no real home paths in this note)

# 1) Unit tests: 63 runner tests + 23 converter tests = 86, all pass
python3 -m unittest discover -s pilot/tests 2>&1 | tail -3
# Ran 86 tests ... OK

# 2) Schema validation of the pilot's own schemas + 15 fixtures (exit 0)
make pilot-validate
# schema documents: OK / scenarios: 15 valid, 0 invalid

# 3) Converter: 30 reviewed cases -> pilot schema, all valid (exit 0)
python3 -m pilot.convert_eval --validate-only
# converted: 30 total, 30 valid, 0 invalid, 0 conversion error(s)

# 4) Documented clean-machine reproduction path (full corpus)
make pilot-eval-dryrun     # convert + run 30 scenarios x 4 providers
# manifest:      dryrun-20260804T193401
# mode:          dry_run
# scenarios:     30
# results:       120
# outcomes:      60 ok, 0 failure, 60 unsupported, 0 setup_failed
# simulated:     120 (all stub results are simulated, provenance=inferred)
# report:        pilot-out/integration/report.md
```

## Verification checklist (task acceptance criteria)

| Requirement | Evidence |
|---|---|
| ~30 reviewed synthetic cases, all 10 categories | 30 scenarios converted; 10 categories x 3 (abstention, accurate_retrieval, isolation, long_range_synthesis, poisoning_resistance, premise_awareness, procedural_memory, recovery, selective_forgetting, temporal_validity); 20 dev / 10 held-out preserved |
| Every published scenario validated against schema | converter `--validate-only` -> 30 valid, 0 invalid (pilot scenario.schema.json v1.0.0) |
| Every raw result validated against schema | 120/120 result payloads pass `result@1.0.0` validation; `validation_errors.json` empty; report.json `validation_errors: {}`, `schema_errors: {}` |
| Failures retained, none discarded | runner captures failures/setup_failed/unsupported as first-class schema-valid results; this run: 60 unsupported retained with availability-failure detail (`provider hindsight marked unavailable: no configured endpoint/credentials for this run`), 0 discarded |
| Report: category-level metrics | report.md "Category Results": per-category tables (n, correctness mean/std, ev-precision, ev-recall, p50/p95 ms, failures, unsupported) for all 10 categories, never collapsed to one ranking scale |
| Report: provenance separation | "Provenance" section: 120 simulated / 0 measured / 0 vendor-reported; every result carries `measurement_kind=simulated`, `provenance=inferred`; explicit "must never be promoted to hmem-measured evidence" |
| Report: limitations | 8 limitations listed (dry-run stubs, no real provider invoked, latency in-process only, token estimates, resource best-effort, lexical scoring, scenario coverage, 60 unsupported recorded not fabricated) |
| Report: variance | "Variance" section: overall correctness std + per-provider std + note that stubs are deterministic so variance ~0 |
| Provider unavailability honest, no fabricated measurements | hindsight/mnemosyne pinned `--unavailable` (both not-configured per provider audit: Hindsight bundled-but-not-configured, Mnemosyne absent from Hermes v0.20.0); recorded as unsupported with reason, never measured; dry-run simulation clearly distinguished from hmem measurements |
| No PDFs / DOCX / archives / extracted texts / private seeds / real conversations staged | `git status --porcelain` + `git ls-files` scan: no such files; run outputs in git-ignored `pilot-out/`; public-safety scan (evaluation/tools/validate_fixtures.py) passes on evaluation fixtures; converted corpus carries `privacy: {synthetic: true, contains_real_data: false}` |
| Git diff reviewed | see below |

## Public-safety scan

```bash
# Sibling corpus fixture scan (spec task's tool, still PASS after integration)
python3 evaluation/tools/validate_fixtures.py | tail -2
# result: PASS

# Forbidden markers (PRIV-10 list from evaluation/tools/validate_fixtures.py)
# over every file this integration stages: scan programmatically so the
# committed note never embeds the markers themselves.
python3 - <<'EOF'
import pathlib, sys
sys.path.insert(0, "evaluation/tools")
from validate_fixtures import FORBIDDEN
targets = ["pilot/convert_eval.py", "pilot/tests/test_convert_eval.py",
           "pilot/README.md", "evaluation/pilot-integration-verification.md",
           "Makefile"]
hits = [(f, m) for f in targets
        for m in FORBIDDEN if m in pathlib.Path(f).read_text()]
print("clean" if not hits else hits)
EOF
# clean
```

## What is committed vs local-only

- **Committed:** converter + tests, Makefile targets, README docs, this note.
  All synthetic, schema-valid, public-safe.
- **Local-only (git-ignored `pilot-out/`):** converted scenarios
  (`pilot-out/scenarios-eval/`), run manifest, 120 raw results,
  `validation_errors.json`, `report.md`, `report.json`. Regenerate anytime
  with `make pilot-eval-dryrun`.

## How to reproduce on a clean machine

```bash
git clone <repo> && cd hmem
python3 -m venv .venv && source .venv/bin/activate   # or use system python3
make pilot-validate && make pilot-test && make pilot-eval-dryrun
# Expect: validation OK, 86/86 tests pass, 30 scenarios / 120 results
# (60 ok + 60 unsupported), exit 0, report at pilot-out/integration/report.md
```

No network, no credentials, no real provider endpoints are touched anywhere
in this path — every result is a deterministic stub simulation.
