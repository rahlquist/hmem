#!/usr/bin/env python3
"""hmem pilot fixture validator.

Validates every JSON artifact under evaluation/fixtures/ against the versioned
JSON Schemas in evaluation/schemas/ and runs the public-safety substring scan
required by PRIVACY.md (PRIV-10).

Validation modes:
  1. FULL (default): uses the `jsonschema` package (draft-07) if importable.
  2. STDLIB FALLBACK (--fallback or when jsonschema is missing):
     a documented standard-library-only structural check: required keys,
     enum membership, type checks, regex patterns, and format checks
     (date-time) for the artifact types. This fallback is deliberately
     conservative: it flags structural violations it can prove, but it cannot
     guarantee full draft-07 compliance, so the printed verdict says
     "STDLIB-CHECK" instead of "SCHEMA-VALID".

Public-safety scan (always runs, both modes):
  - FORBIDDEN substrings: real home paths, local hostnames, real profile
    identifiers, and private markers must not appear in any committed fixture.
  - The scan is a guard, not a substitute for human git-diff review (PRIV-10).

Cross-checks (always run):
  - Every id in expected.must_use_evidence / must_not_use_evidence exists in
    the scenario's setup event ids.
  - pilot-registry.json split lists contain exactly the scenario_ids present
    in fixtures/scenarios/ and match each fixture's declared `split`.
  - Every scenario file id matches its filename prefix (e.g. RET-01-*.json).

Exit code 0 when everything passes; 1 otherwise.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # evaluation/
SCHEMA_DIR = ROOT / "schemas"
FIXTURE_DIR = ROOT / "fixtures"
SCENARIO_DIR = FIXTURE_DIR / "scenarios"

# --- Public-safety scan list (PRIVACY.md "Forbidden markers") -----------------
FORBIDDEN = [
    # Real repository-owner home paths
    "/home/rahlquist",
    # Local hostnames used in this environment
    "hermesvm01",
    # Real profile identifiers
    "loco-bot",
    "senna",
    # Private/local markers that must never appear in committed fixtures
    "~/.hermes/",
    "PRIVATE_SEED",
    "BEGIN PRIVATE KEY",
]

# Category prefixes allowed in scenario ids (capability matrix)
CATEGORY_PREFIXES = [
    "RET", "TEMP", "FORGET", "SYNTH", "PROC", "PREM", "ISO", "ABST", "POIS", "RESTART",
]

# Which schema applies to which artifact
ARTIFACT_SCHEMAS = {
    "scenarios": "scenario.schema.json",
    "pilot-registry.json": "pilot-registry.schema.json",
    "examples/example-manifest.json": "run-manifest.schema.json",
    "examples/example-result.json": "result.schema.json",
}


# --- Stdlib fallback: minimal structural validator ----------------------------
def _check_type(value, expected, path, errors):
    if expected == "object" and not isinstance(value, dict):
        errors.append(f"{path}: expected object, got {type(value).__name__}")
    elif expected == "array" and not isinstance(value, list):
        errors.append(f"{path}: expected array, got {type(value).__name__}")
    elif expected == "string" and not isinstance(value, str):
        errors.append(f"{path}: expected string, got {type(value).__name__}")
    elif expected == "boolean" and not isinstance(value, bool):
        errors.append(f"{path}: expected boolean, got {type(value).__name__}")
    elif expected in ("integer", "number") and not isinstance(value, (int, float)):
        errors.append(f"{path}: expected number, got {type(value).__name__}")


def _stdlib_validate_scenario(data, errors):
    required = [
        "scenario_id", "spec_version", "title", "category", "difficulty", "split",
        "origin", "world", "privacy", "setup", "probe", "expected", "metrics",
    ]
    for key in required:
        if key not in data:
            errors.append(f"scenario: missing required key {key}")
    if "scenario_id" in data and not re.fullmatch(r"[A-Z]+-[0-9]{2}", data["scenario_id"]):
        errors.append(f"scenario_id {data['scenario_id']!r} must match ^[A-Z]+-[0-9]{2}$")
    if data.get("spec_version") != "1.0.0":
        errors.append("scenario: spec_version must be 1.0.0")
    if data.get("category") not in [
        "retrieval", "temporal-updates", "selective-forgetting", "long-range-synthesis",
        "procedural-memory", "premise-awareness", "isolation", "abstention",
        "poisoning-resistance", "restart-recovery",
    ]:
        errors.append("scenario: invalid category")
    if data.get("difficulty") not in ("easy", "medium", "hard"):
        errors.append("scenario: invalid difficulty")
    if data.get("split") not in ("dev", "held-out"):
        errors.append("scenario: invalid split")
    if not isinstance(data.get("setup"), list) or len(data.get("setup", [])) < 2:
        errors.append("scenario: setup must be an array with >= 2 events")
    for ev in data.get("setup", []):
        if "event_id" not in ev:
            errors.append("scenario: event missing event_id")
        if "timestamp" in ev:
            try:
                datetime.datetime.fromisoformat(ev["timestamp"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                errors.append(f"scenario: event {ev.get('event_id')} bad timestamp {ev.get('timestamp')!r}")
    probe = data.get("probe", {})
    if not isinstance(probe.get("text"), str) or not probe["text"]:
        errors.append("scenario: probe.text must be a non-empty string")
    expected = data.get("expected", {})
    if expected.get("answer_type") not in (
        "exact", "set", "synthesis", "procedure", "abstain", "premise-rejection", "negative",
    ):
        errors.append("scenario: expected.answer_type invalid")
    if not isinstance(expected.get("abstain"), bool) or not isinstance(expected.get("reject_premise"), bool):
        errors.append("scenario: expected.abstain / reject_premise must be boolean")
    metrics = data.get("metrics", {})
    if not isinstance(metrics.get("primary"), list) or not metrics["primary"]:
        errors.append("scenario: metrics.primary must be a non-empty array")


def _stdlib_validate_registry(data, errors):
    for key in ("registry_id", "spec_version", "generated_by", "generated_at", "split", "providers"):
        if key not in data:
            errors.append(f"registry: missing required key {key}")
    if data.get("spec_version") != "1.0.0":
        errors.append("registry: spec_version must be 1.0.0")
    for prov in data.get("providers", []):
        for key in ("provider_id", "name", "kind", "integration_state", "evidence_class", "status"):
            if key not in prov:
                errors.append(f"registry: provider {prov.get('provider_id')} missing {key}")


def _stdlib_validate_manifest(data, errors):
    for key in ("manifest_id", "spec_version", "run_id", "mode", "created_at", "operator",
                "hermes", "provider", "dataset", "seeds", "privacy"):
        if key not in data:
            errors.append(f"manifest: missing required key {key}")
    if data.get("mode") not in ("measured", "dry-run", "simulated"):
        errors.append("manifest: invalid mode")
    if data.get("spec_version") != "1.0.0":
        errors.append("manifest: spec_version must be 1.0.0")
    if data.get("privacy", {}).get("contains_no_secrets") is not True:
        errors.append("manifest: privacy.contains_no_secrets must be true")


def _stdlib_validate_result(data, errors):
    for key in ("result_id", "spec_version", "run_id", "manifest_id", "scenario_id", "category",
                "provider", "mode", "probe", "answer", "metrics", "evidence", "verdict", "provenance"):
        if key not in data:
            errors.append(f"result: missing required key {key}")
    if data.get("mode") not in ("measured", "dry-run", "simulated"):
        errors.append("result: invalid mode")
    if data.get("verdict") not in ("pass", "partial", "fail", "skip", "error"):
        errors.append("result: invalid verdict")
    if data.get("answer", {}).get("answer_class") not in (
        "correct", "partial", "incorrect", "abstained", "premise_rejected", "refused",
    ):
        errors.append("result: invalid answer_class")


STDLIB_VALIDATORS = {
    "scenario.schema.json": _stdlib_validate_scenario,
    "pilot-registry.schema.json": _stdlib_validate_registry,
    "run-manifest.schema.json": _stdlib_validate_manifest,
    "result.schema.json": _stdlib_validate_result,
}


# --- Public-safety scan --------------------------------------------------------
def public_safety_scan(text, path):
    hits = []
    for marker in FORBIDDEN:
        if marker in text:
            hits.append(marker)
    return hits


# --- Cross-checks --------------------------------------------------------------
def cross_check_scenario(data, path, errors):
    sid = data.get("scenario_id")
    if sid and not path.name.startswith(sid + "-"):
        errors.append(f"{path.name}: filename prefix does not match scenario_id {sid!r}")
    setup_ids = {e.get("event_id") for e in data.get("setup", []) if isinstance(e, dict)}
    for field in ("must_use_evidence", "must_not_use_evidence"):
        for ref in data.get("expected", {}).get(field, []):
            if ref not in setup_ids:
                errors.append(f"{sid}: expected.{field} references unknown event {ref!r}")


def cross_check_registry(reg, scenario_data, errors):
    actual = {}
    for sid, data in scenario_data.items():
        actual[sid] = data.get("split")
    for sid in reg.get("split", {}).get("dev", []):
        if actual.get(sid) != "dev":
            errors.append(f"registry: dev lists {sid} but fixture declares {actual.get(sid)!r}")
    for sid in reg.get("split", {}).get("held_out", []):
        if actual.get(sid) != "held-out":
            errors.append(f"registry: held_out lists {sid} but fixture declares {actual.get(sid)!r}")
    all_listed = set(reg.get("split", {}).get("dev", [])) | set(reg.get("split", {}).get("held_out", []))
    all_fixtures = set(actual)
    if all_listed != all_fixtures:
        errors.append(
            f"registry: split lists {sorted(all_listed - all_fixtures)} not in fixtures; "
            f"fixtures {sorted(all_fixtures - all_listed)} not listed"
        )


# --- Main ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Validate hmem pilot fixtures and scan for private material.")
    ap.add_argument("--fallback", action="store_true", help="Force the stdlib-only structural check")
    ap.add_argument("--dir", default=str(FIXTURE_DIR), help="fixtures directory (default evaluation/fixtures)")
    args = ap.parse_args()

    fixture_dir = Path(args.dir)
    try:
        import jsonschema as _jsonschema  # noqa: F401
        mode = "full" if not args.fallback else "stdlib"
    except ImportError:
        _jsonschema = None  # noqa: F841
        mode = "stdlib"

    print(f"validator mode: {mode}")

    if mode == "full":
        assert _jsonschema is not None, "jsonschema import invariant violated"

    failures = 0
    scenario_data = {}

    # Load schema documents
    schemas = {}
    for fname in set(ARTIFACT_SCHEMAS.values()):
        try:
            schemas[fname] = json.loads((SCHEMA_DIR / fname).read_text())
        except FileNotFoundError:
            print(f"ERROR: schema file missing: {SCHEMA_DIR / fname}")
            return 1

    # 1. Scenario fixtures
    scenario_files = sorted(SCENARIO_DIR.glob("*.json")) if (SCENARIO_DIR).exists() else []
    if not scenario_files:
        print("ERROR: no scenario fixtures found")
        return 1
    for f in scenario_files:
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            print(f"FAIL {f.name}: invalid JSON: {e}")
            failures += 1
            continue
        errors = []
        if mode == "full":
            try:
                _jsonschema.validate(data, schemas["scenario.schema.json"])
            except _jsonschema.ValidationError as e:
                errors.append(f"schema: {e.message}")
        else:
            STDLIB_VALIDATORS["scenario.schema.json"](data, errors)
        cross_check_scenario(data, f, errors)
        hits = public_safety_scan(f.read_text(), f)
        for h in hits:
            errors.append(f"public-safety: forbidden marker {h!r}")
        if errors:
            failures += 1
            print(f"FAIL {f.name}")
            for e in errors:
                print(f"    - {e}")
        else:
            scenario_data[data["scenario_id"]] = data
            print(f"OK   {f.name}")

    # 2. Registry + examples
    for rel, schema_name in [
        ("pilot-registry.json", "pilot-registry.schema.json"),
        ("examples/example-manifest.json", "run-manifest.schema.json"),
        ("examples/example-result.json", "result.schema.json"),
    ]:
        f = FIXTURE_DIR / rel
        if not f.exists():
            print(f"SKIP {rel}: file missing")
            continue
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            print(f"FAIL {rel}: invalid JSON: {e}")
            failures += 1
            continue
        errors = []
        if mode == "full":
            try:
                _jsonschema.validate(data, schemas[schema_name])
            except _jsonschema.ValidationError as e:
                errors.append(f"schema: {e.message}")
        else:
            STDLIB_VALIDATORS[schema_name](data, errors)
        hits = public_safety_scan(f.read_text(), f)
        for h in hits:
            errors.append(f"public-safety: forbidden marker {h!r}")
        if errors:
            failures += 1
            print(f"FAIL {rel}")
            for e in errors:
                print(f"    - {e}")
        else:
            print(f"OK   {rel}")
        if rel == "pilot-registry.json":
            reg_errors = []
            cross_check_registry(data, scenario_data, reg_errors)
            if reg_errors:
                failures += 1
                print(f"FAIL {rel} (cross-check)")
                for e in reg_errors:
                    print(f"    - {e}")
            else:
                print(f"OK   {rel} cross-check (split <-> fixtures)")

    print(f"\nresult: {'PASS' if failures == 0 else f'FAIL ({failures} artifact(s) with errors)'}")
    if mode == "stdlib":
        print("NOTE: stdlib fallback check used; full draft-07 schema compliance not guaranteed.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
