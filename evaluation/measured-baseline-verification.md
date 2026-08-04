# hmem Measured Lexical Baseline — Verification Note

**Task:** t_8e32b1f4 (harden run isolation and measure the real lexical baseline)
**Date:** 2026-08-04
**Workspace:** the hmem repo (branch `main`, commit `262ceb2` + this task)
**Artifact path (run outputs, local-only):** `pilot-out/measured-runs/runs/`
  (three isolated run dirs, each: manifest.json, results/*.json = 30 raw
  schema-valid result documents, validation_errors.json, report.md,
  report.json, state/). `pilot-out/` is git-ignored by design — these are
  regenerable local run outputs, never published.
**Report path (local-only):** `pilot-out/measured-report/report.md` +
  `report.json` (category-first measured baseline with cross-run variance).
**Committed implementation:** `pilot/isolation.py`, `pilot/lexical.py`,
  `pilot/measured_report.py`, measured-mode wiring in `pilot/adapters.py`,
  `pilot/cli.py`, `pilot/runner.py`, `pilot/schemas/run_manifest.schema.json`,
  plus test modules under `pilot/tests/` (144 tests total, all passing).

## What this task added

1. **Run isolation.** Every benchmark invocation can write into a unique run
   directory (`--isolated`, `<out-dir>/runs/<manifest_id>/`, with a `-1`,
   `-2`, ... suffix when the directory already exists) so a re-invocation can
   never overwrite an earlier run's manifest/results/report. Plain mode keeps
   the historical layout. `pilot/isolation.validate_run_outputs` then proves
   every result file on disk belongs to the current manifest and exactly
   matches the expected scenario/provider matrix (stale/unexpected files,
   missing files, filename/result_id mismatches, embedded manifest_id
   mismatches, schema-invalid payloads all flagged).
2. **Real deterministic lexical baseline.** `pilot/lexical.py` implements a
   pure-Python Okapi BM25 ranker (k1=1.2, b=0.75, documented algorithm:
   lowercased alphanumeric tokenization with a fixed stopword list, in-memory
   postings, standard BM25 idf, tie-break by earliest turn, abstention on
   zero lexical overlap) and a `MeasuredLexicalBaselineAdapter` that executes
   it in-process. Results are labeled `measurement_kind=measured` /
   `provenance=hmem-measured` ONLY when this real path executed
   (`--mode measured --measured lexical_baseline`); the provenance label is
   structural on the adapter class (`measured=True`). The policy-simulation
   stub (`adapters.LexicalBaselineAdapter`) is retained unchanged for dry-run
   compatibility and keeps `measurement_kind=simulated` /
   `provenance=inferred` forever — never relabeled.
3. **Three measured full-corpus runs.** Executed under pinned configuration
   (mode=measured, isolated, measured=lexical_baseline, providers=
   lexical_baseline, scenarios=pilot-out/scenarios-eval [30 reviewed cases,
   10 categories x 3], repetitions=3, seed=7). Each run captured raw
   schema-valid results with actual p50/p95 latency (3 real samples),
   token estimates, CPU/RAM/disk/network resource fields, and failure counts
   (0 failures across all runs).
4. **Category-first measured baseline report.** `pilot/measured_report.py`
   aggregates the N isolated runs into a category-first report with per-category
   mean and population std across the three runs (variance), provenance
   counts (90 measured / 0 simulated), and explicit limitations. It clearly
   separates measured lexical results from simulated adapter outputs.

## Exact commands and results

```bash
cd hmem   # repo root (paths relative; no real home paths in this note)

# 1) Full test suite: 144 tests, all passing
python3 -m unittest discover -s pilot/tests
# Ran 144 tests ... OK

# 2) Schema + fixture validation (exit 0)
make pilot-validate
# schema documents: OK / scenarios: 15 valid, 0 invalid

# 3) 30-case corpus conversion, all valid (exit 0)
python3 -m pilot.convert_eval --validate-only
# converted: 30 total, 30 valid, 0 invalid, 0 conversion error(s)

# 4) Three measured full-corpus runs, each isolated (x3)
python3 -m pilot.cli --mode measured --isolated \
    --measured lexical_baseline --providers lexical_baseline \
    --scenarios-dir pilot-out/scenarios-eval \
    --out-dir pilot-out/measured-runs --repetitions 3 --seed 7
# -> pilot-out/measured-runs/runs/measured-20260804T231041  (30 results)
# -> pilot-out/measured-runs/runs/measured-20260804T231047  (30 results)
# -> pilot-out/measured-runs/runs/measured-20260804T231053  (30 results)
# every result: measurement_kind=measured, provenance=hmem-measured, outcome ok

# 5) Isolation / stale-result verification on all three run dirs (CLEAN)
python3 - <<'PY'
import json, os
import pilot.isolation as iso
base = 'pilot-out/measured-runs/runs'
for d in sorted(os.listdir(base)):
    rd = os.path.join(base, d)
    if not os.path.isdir(rd): continue
    manifest = json.load(open(os.path.join(rd, 'manifest.json')))
    results = [json.load(open(os.path.join(rd, 'results', n)))
               for n in sorted(os.listdir(os.path.join(rd, 'results')))
               if n.endswith('.json')]
    issues = iso.validate_run_outputs(rd, manifest, results, 'pilot/schemas')
    print(d, 'CLEAN' if not issues else issues)
# measured-20260804T231041 CLEAN
# measured-20260804T231047 CLEAN
# measured-20260804T231053 CLEAN

# 6) Cross-run aggregation into the category-first baseline report
python3 -m pilot.measured_report \
    --runs pilot-out/measured-runs/runs --out pilot-out/measured-report
# runs: 3  results: 90  measured: 90  simulated: 0
# -> pilot-out/measured-report/report.md + report.json
```

## Measured results (90 results across 3 runs)

| category | n | correctness mean | correctness std | p50 ms mean | p50 ms std |
|---|---|---|---|---|---|
| abstention | 9 | 0.000 | 0.000 | 0.033 | 0.002 |
| accurate_retrieval | 9 | 0.667 | 0.000 | 0.046 | 0.002 |
| isolation | 9 | 0.000 | 0.000 | 0.042 | 0.010 |
| long_range_synthesis | 9 | 0.333 | 0.000 | 0.049 | 0.003 |
| poisoning_resistance | 9 | 1.000 | 0.000 | 0.050 | 0.003 |
| premise_awareness | 9 | 0.000 | 0.000 | 0.041 | 0.007 |
| procedural_memory | 9 | 0.333 | 0.000 | 0.041 | 0.005 |
| recovery | 9 | 1.000 | 0.000 | 0.038 | 0.004 |
| selective_forgetting | 9 | 0.000 | 0.000 | 0.045 | 0.004 |
| temporal_validity | 9 | 0.333 | 0.000 | 0.040 | 0.002 |

Overall correctness mean across runs: 0.367 (std 0.379 across category
means — category spread, not run-to-run drift; correctness is deterministic,
so per-category std across runs is 0.000 by design). Latency variance across
runs (p50 std 0.002–0.010 ms per category) is the real measured signal.

## Provenance / separation

- All 90 result documents carry `measurement_kind=measured` and
  `provenance=hmem-measured`; each manifest declares
  `run.measured_providers=["lexical_baseline"]`.
- Provenance is structural on the adapter class: only the real in-process
  BM25 implementation produces measured labels, and only when that real path
  executed. Dry-run mode still yields 15/15 simulated (0 measured) — the
  stubs are never relabeled.
- The measured baseline report records provenance counts (90 measured /
  0 simulated) and lists simulated adapters as excluded, never conflated.

## Limitations (recorded in the report)

1. Measured results come only from the real in-process pure-Python Okapi
   BM25 ranker executed during these runs.
2. The lexical baseline is intentionally naive: no deletion, no
   profile/host boundaries, no trust filtering, no persistence, no semantic
   understanding. Scores measure lexical overlap only.
3. Latency samples exclude network and real-storage effects; not comparable
   across machines.
4. Token counts are whitespace estimates, not provider tokenizer output.
5. Resource counters are process-wide best-effort; system-wide counters may
   be None without psutil.
6. Simulated adapter results (hermes_memory/hindsight/mnemosyne stubs) are
   excluded from this measured baseline and are never relabeled as measured.

## Test evidence / TDD

- RED evidence captured before implementation:
  `pilot-out/tdd/red-evidence.txt` (local-only, git-ignored) — 11 new tests
  failed before the implementation existed: ImportError for
  pilot.lexical / pilot.isolation / pilot.measured_report, RunConfig/
  run_dir missing, measured mode rejected by schema, missing
  --isolated/--measured CLI flags. The commit narrative below records the
  RED phase; the same tests pass green in the committed suite (144 total).
- Full suite green: `python3 -m unittest discover -s pilot/tests` → 144 OK.

## Public-safety scan (committed files)

- No PDF/DOCX/ZIP/archive/extracted texts tracked (`git ls-files` clean of
  these; memorypapers binaries are git-ignored per PRIVACY.md PRIV-03).
- Marker scan across all files staged for this commit: no real home paths,
  local hostnames, real profile ids, passwords, API keys, or private
  conversation material (only the word "secrets" in "no secrets required"
  docstrings — false positives, no secrets present).
- All fixtures are synthetic (reviewed corpus, no real persons/paths/
  credentials). Run outputs with machine resource counters stay git-ignored.
