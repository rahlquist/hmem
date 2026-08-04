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
  adapters.py     deterministic provider adapter stubs (policies, no LLM/network)
  validate.py     versioned payload validation (jsonschema or stdlib fallback)
  env.py          declared environment + resource capture (p50/p95, tokens, CPU/RAM/disk/network)
  runner.py       dry-run orchestration: failures captured, unavailable reported
  report.py       category-first aggregate report (limitations, variance, provenance)
  cli.py          command-line entrypoint
  tests/          unittest suite (63 tests)
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

### Make targets (from repo root)

```bash
make pilot-validate   # schemas + fixtures validation
make pilot-test       # unittest suite
make pilot-dryrun     # full dry run into pilot-out/
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
