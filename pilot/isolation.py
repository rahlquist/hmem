"""Run isolation and stale-result validation for the hmem pilot.

Every benchmark invocation writes into a unique run directory (isolated mode,
``<out_dir>/runs/<manifest_id>/``) or replaces only its exact target files.
``validate_run_outputs`` then proves that every result file on disk belongs
to the current manifest and exactly matches the expected scenario/provider
matrix, so stale results from earlier runs can never contaminate current
manifests or reports.
"""
import json
import os

from . import validate as v


def unique_run_dir(out_dir, run_id, base="runs"):
    """Create and return ``<out_dir>/<base>/<run_id>``.

    Guarantees uniqueness: if the directory already exists, a ``-1``, ``-2``
    ... suffix is appended so a re-run can never overwrite an earlier run.
    """
    root = os.path.join(out_dir, base)
    os.makedirs(root, exist_ok=True)
    candidate = os.path.join(root, run_id)
    n = 0
    while os.path.exists(candidate):
        n += 1
        candidate = os.path.join(root, f"{run_id}-{n}")
    os.makedirs(candidate, exist_ok=True)
    return candidate


def validate_run_outputs(run_dir, manifest, results, schema_dir=None):
    """Check on-disk run outputs exactly match this run's manifest + results.

    Returns a list of issue strings; an empty list means the run directory is
    clean (no stale results, no missing results, every result schema-valid and
    belonging to the current manifest).
    """
    schema_dir = schema_dir or v.DEFAULT_SCHEMA_DIR
    issues = []
    manifest_id = manifest["manifest_id"]

    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        issues.append("manifest.json missing in run directory")
    else:
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                on_disk = json.load(fh)
            if on_disk.get("manifest_id") != manifest_id:
                issues.append(
                    f"manifest.json manifest_id {on_disk.get('manifest_id')!r} "
                    f"!= current {manifest_id!r} (stale manifest)")
        except Exception as exc:
            issues.append(f"manifest.json unreadable: {exc}")

    results_dir = os.path.join(run_dir, "results")
    if not os.path.isdir(results_dir):
        issues.append(f"results directory missing: {results_dir}")
        return issues

    expected = {r["result_id"]: r for r in results}
    seen = set()
    for name in sorted(os.listdir(results_dir)):
        rid = name[:-5] if name.endswith(".json") else name
        if not name.endswith(".json"):
            issues.append(f"unexpected non-result file in results/: {name}")
            continue
        if rid not in expected:
            issues.append(
                f"stale/unexpected result file {name}: not in the current "
                f"manifest's scenario/provider matrix")
            continue
        seen.add(rid)
        path = os.path.join(results_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception as exc:
            issues.append(f"result file {name} unreadable: {exc}")
            continue
        if doc.get("result_id") != rid:
            issues.append(
                f"result file {name}: embedded result_id {doc.get('result_id')!r} "
                f"!= filename")
        if doc.get("manifest_id") != manifest_id:
            issues.append(
                f"result file {name}: embedded manifest_id {doc.get('manifest_id')!r} "
                f"!= current {manifest_id!r} (stale content)")
        schema_errors = v.validate_payload(doc, "result", schema_dir)
        if schema_errors:
            issues.append(f"result file {name} schema-invalid: {schema_errors}")

    for rid in expected:
        if rid not in seen:
            issues.append(f"missing expected result file: {rid}.json")
    return issues
