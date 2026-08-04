# hmem Pilot Runner and Reporting

Deterministic, clean-machine-oriented memory-provider evaluation harness.
Dry-run safe: runs synthetic scenarios against provider adapter **stubs**
(built-in Hermes memory, session_search / simple lexical baseline, Hindsight,
Mnemosyne) with no real providers, network, or secrets required.

**Status:** implementation complete, dry-run verified. All results are
simulations (`measurement_kind=simulated`, `provenance=inferred`) and must
never be promoted to `hmem-measured` evidence.

**Task:** t_4f309a57 (runner/report implementation).
**Upstream spec:** [EVALUATION_ENHANCEMENTS.md](../EVALUATION_ENHANCEMENTS.md).
**Sibling spec:** [evaluation/](../evaluation/README.md) (corpus, schemas,
scoring rubric, privacy rules — this pilot establishes a compatible minimal
versioned schema structure the sibling specification can extend; the harness
accepts `--schema-dir` so adapted documents can be dropped in).

## Layout

```
pilot/
  __init__.py     versioned payload kinds, categories, provider ids
  schemas/        scenario / run_manifest / result JSON Schema documents (v1.0.0)
  scenarios/      15 synthetic deterministic fixtures (dev/held-out declared)
  convert_eval.py thin converter: evaluation/ corpus (30 reviewed cases) -> pilot schema
  adapters.py     deterministic provider adapter stubs (policies, no LLM/network)
  validate.py     versioned payload validation (jsonschema or stdlib fallback)
  env.py          declared environment + resource capture (p50/p95, tokens, CPU/RAM/disk/network)
  runner.py       dry-run orchestration: failures captured, unavailable reported
  report.py       category-first aggregate report (limitations, variance, provenance)
  cli.py          command-line entrypoint
  tests/          unittest suite (86 tests)
```

## Usage

Python 3.9+; `jsonschema` is optional (stdlib fallback). No other
dependencies (psutil is used only when installed).

```bash
# Automated validation: schemas + scenario fixtures (exit 0 = clean)
python -m pilot.cli --validate-only

# Automated test suite (63 tests)
python -m unittest discover -s pilot/tests -v

# Deterministic dry run (all providers), output to pilot-out/
python -m pilot.cli --out-dir pilot-out --repetitions 3 --seed 7

# Subset of providers
python -m pilot.cli --providers hermes_memory,lexical_baseline

# Report unavailable providers as unsupported (schema-valid results, no failure)
python -m pilot.cli --unavailable hindsight,mnemosyne
```

### Full reviewed-corpus integration (30 cases, 10 categories)

The sibling `evaluation/` specification ships a reviewed corpus of 30
synthetic scenarios (10 categories x 3, 20 dev / 10 held-out). The thin
converter `pilot/convert_eval.py` adapts them to the pilot's minimal schema
(deterministic mapping, documented in the module docstring; original ids kept
in provenance notes). Run the documented clean-machine reproduction path:

```bash
# 1) Convert the 30 reviewed cases and validate them against the pilot schema
make pilot-eval-convert        # python -m pilot.convert_eval --out pilot-out/scenarios-eval
#    -> "wrote 30 converted scenarios ..." then each file validates (schema)

# 2) Full dry run over the converted corpus
make pilot-eval-dryrun         # convert + run all 30 x 4 providers -> pilot-out/integration/
#    -> 30 scenarios, 120 results; hindsight/mnemosyne reported unsupported
#       (not-configured per evaluation/provider-audit.md), never measured
```

The integration run pins `--unavailable hindsight,mnemosyne` because the
provider audit (2026-08-04) found Hindsight bundled-but-not-configured and
Mnemosyne absent from Hermes v0.20.0. Unavailable providers are recorded as
schema-valid `unsupported` results with the availability failure detail; no
provider measurement is fabricated. Everything remains `measurement_kind=
simulated` / `provenance=inferred` (dry-run simulation), clearly separated
from any future `hmem-measured` evidence in the report's provenance section.

The converter is covered by its own unittest module (pilot/tests/
test_convert_eval.py, 23 tests) — run `make pilot-test` (86 tests total).

### Make targets (from repo root)

```bash
make pilot-validate   # schemas + fixtures validation
make pilot-test       # unittest suite
make pilot-dryrun     # full dry run into pilot-out/
make pilot-eval-convert   # 30-case reviewed corpus -> pilot-out/scenarios-eval
make pilot-eval-dryrun    # convert + full-corpus dry run -> pilot-out/integration/
```

## Outputs

`manifest.json` (pinned controlled-run contract: hermes/provider versions,
budgets, seeds, declared environment), `results/*.json` (one schema-valid raw
result per scenario x provider; failures and unsupported providers are
first-class outcomes, never discarded), `validation_errors.json`,
`report.md` + `report.json` (category-first aggregate with provenance
counts, variance, and explicit limitations).

## Schema Coordination

Payloads are versioned via `schema_version` (`<kind>@<version>`); the
registered document versions live in `pilot/schemas/`. The sibling
`evaluation/` specification defines a richer corpus schema; the pilot uses a
minimal compatible structure so scenarios can be adapted by writing a thin
converter and pointing `--schema-dir` at the extended documents.

## Privacy / Publishing

- All fixtures are synthetic; no real persons, paths, credentials, or
  conversation material (PRIV-01/02 in `evaluation/PRIVACY.md`).
- Run outputs (pilot-out/) and the local virtualenv are git-ignored.
- Committed pilot materials must pass the public-safety scan (forbidden
  markers: real home paths, local hostnames, real profile ids).
