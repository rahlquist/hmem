"""Tests for pilot.isolation: unique run directories and stale-result
validation. Every benchmark invocation must write to a unique run directory
(or replace only its exact targets), and validation must prove that every
result file on disk belongs to the current manifest and exactly matches the
expected scenario/provider matrix.
"""
import json
import os
import tempfile
import unittest

import pilot.isolation as iso
import pilot.validate as v

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(ROOT, "schemas")


def _manifest(manifest_id="dryrun-test-0001"):
    return {
        "schema_version": "run_manifest@1.0.0",
        "manifest_id": manifest_id,
        "created_iso": "2026-08-04T00:00:00Z",
        "mode": "measured",
        "hermes": {"version": "test", "commit": "test"},
        "provider_versions": {
            "hermes_memory": {"version": "stub", "deployment_mode": "bundled"},
            "lexical_baseline": {"version": "bm25-1.0.0", "deployment_mode": "in_process"},
            "hindsight": {"version": "stub", "deployment_mode": "self_hosted"},
            "mnemosyne": {"version": "stub", "deployment_mode": "local_sqlite"},
        },
        "budgets": {"recall_tokens": 4096},
        "scenario_set": {"name": "smoke", "version": "1.0.0", "split": "dev", "scenario_count": 1},
        "run": {"seed": 7, "repetitions": 1, "deterministic": True,
                "measured_providers": ["lexical_baseline"]},
        "generator": {"name": "test", "version": "0", "commit": "none"},
        "environment": {"os": "test", "python_version": "3", "machine": "x86_64",
                        "cpu_count": 2, "captured_iso": "2026-08-04T00:00:00Z"},
    }


def _result(result_id, manifest_id="dryrun-test-0001", scenario_id="s-0001",
            measurement_kind="measured", provenance="hmem-measured"):
    return {
        "schema_version": "result@1.0.0",
        "result_id": result_id,
        "manifest_id": manifest_id,
        "scenario_id": scenario_id,
        "provider_id": "lexical_baseline",
        "category": "accurate_retrieval",
        "scenario_split": "dev",
        "measurement_kind": measurement_kind,
        "provenance": provenance,
        "vendor": {"vendor_reported": False, "label": None, "reported_at_iso": None},
        "outcome": "ok",
        "setup": {"success": True,
                  "steps": [{"name": "availability", "status": "ok", "detail": "ok"}],
                  "recovery": {"attempted": False, "success": False, "detail": None}},
        "measurements": {
            "latency_ms": {"p50": 0.1, "p95": 0.2, "n": 1, "samples": [0.1]},
            "ingest_latency_ms": {"p50": 0.05, "p95": 0.1, "n": 1, "samples": [0.05]},
            "recall_latency_ms": {"p50": 0.05, "p95": 0.1, "n": 1, "samples": [0.05]},
            "tokens": {"stored": 10, "retrieved": 3, "injected": 3},
            "resources": {"cpu_percent": None, "peak_ram_mb": None,
                          "disk_growth_mb": None, "network_egress_bytes": None},
        },
        "answer": {"text": "valkyrie", "evidence_turns": [0], "abstained": False},
        "scores": {
            "correctness": 1.0, "evidence_precision": 1.0, "evidence_recall": 1.0,
            "stale_reuse": None, "leakage": None, "abstention_correct": None,
            "poisoning_success": None, "synthesis": None,
            "recovery_success": None, "setup_success": 1.0,
        },
        "scoring_note": "test",
    }


def _write_run(out_dir, manifest, results):
    os.makedirs(os.path.join(out_dir, "results"), exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    for res in results:
        with open(os.path.join(out_dir, "results", f"{res['result_id']}.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
    return out_dir


class TestUniqueRunDir(unittest.TestCase):
    def test_creates_run_dir_under_runs(self):
        base = tempfile.mkdtemp(prefix="hmem-iso-")
        run_dir = iso.unique_run_dir(base, "run-0001")
        self.assertTrue(os.path.isdir(run_dir))
        self.assertEqual(os.path.basename(run_dir), "run-0001")
        self.assertEqual(os.path.dirname(run_dir), os.path.join(base, "runs"))

    def test_same_run_id_gets_suffixed_unique_dir(self):
        base = tempfile.mkdtemp(prefix="hmem-iso-")
        first = iso.unique_run_dir(base, "run-0001")
        second = iso.unique_run_dir(base, "run-0001")
        self.assertNotEqual(first, second)
        self.assertTrue(os.path.isdir(second))
        self.assertTrue(second.endswith("run-0001-1"))

    def test_different_run_ids_give_different_dirs(self):
        base = tempfile.mkdtemp(prefix="hmem-iso-")
        a = iso.unique_run_dir(base, "run-a")
        b = iso.unique_run_dir(base, "run-b")
        self.assertNotEqual(a, b)


class TestValidateRunOutputs(unittest.TestCase):
    def setUp(self):
        self.manifest = _manifest()
        self.results = [
            _result(f"{self.manifest['manifest_id']}--s-0001--lexical_baseline", scenario_id="s-0001"),
            _result(f"{self.manifest['manifest_id']}--s-0002--lexical_baseline", scenario_id="s-0002"),
        ]
        self.run_dir = _write_run(tempfile.mkdtemp(prefix="hmem-val-"), self.manifest, self.results)

    def test_clean_run_has_no_issues(self):
        issues = iso.validate_run_outputs(self.run_dir, self.manifest, self.results, SCHEMA_DIR)
        self.assertEqual(issues, [])

    def test_stale_result_file_flagged(self):
        stale = _result(f"dryrun-OLD--s-0001--lexical_baseline",
                        manifest_id="dryrun-OLD", scenario_id="s-0001")
        with open(os.path.join(self.run_dir, "results", f"{stale['result_id']}.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(stale, fh)
        issues = iso.validate_run_outputs(self.run_dir, self.manifest, self.results, SCHEMA_DIR)
        self.assertTrue(any("stale" in i and "dryrun-OLD" in i for i in issues))

    def test_missing_expected_result_flagged(self):
        os.remove(os.path.join(self.run_dir, "results",
                               f"{self.results[0]['result_id']}.json"))
        issues = iso.validate_run_outputs(self.run_dir, self.manifest, self.results, SCHEMA_DIR)
        self.assertTrue(any("missing" in i and self.results[0]["result_id"] in i for i in issues))

    def test_result_with_wrong_embedded_manifest_id_flagged(self):
        tampered = dict(self.results[0])
        tampered["manifest_id"] = "dryrun-OTHER"
        with open(os.path.join(self.run_dir, "results", f"{tampered['result_id']}.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(tampered, fh)
        issues = iso.validate_run_outputs(self.run_dir, self.manifest, self.results, SCHEMA_DIR)
        self.assertTrue(any("manifest_id" in i and "stale" in i for i in issues))

    def test_filename_result_id_mismatch_flagged(self):
        tampered = dict(self.results[1])
        with open(os.path.join(self.run_dir, "results", "wrong-name.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(tampered, fh)
        issues = iso.validate_run_outputs(self.run_dir, self.manifest, self.results, SCHEMA_DIR)
        self.assertTrue(any("wrong-name" in i for i in issues))

    def test_schema_invalid_result_flagged(self):
        bad = dict(self.results[0])
        bad["outcome"] = "exploded"
        with open(os.path.join(self.run_dir, "results", f"{bad['result_id']}.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(bad, fh)
        issues = iso.validate_run_outputs(self.run_dir, self.manifest, self.results, SCHEMA_DIR)
        self.assertTrue(any("schema-invalid" in i for i in issues))

    def test_missing_manifest_flagged(self):
        os.remove(os.path.join(self.run_dir, "manifest.json"))
        issues = iso.validate_run_outputs(self.run_dir, self.manifest, self.results, SCHEMA_DIR)
        self.assertTrue(any("manifest.json missing" in i for i in issues))

    def test_stale_manifest_id_flagged(self):
        with open(os.path.join(self.run_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(_manifest("dryrun-OLD"), fh)
        issues = iso.validate_run_outputs(self.run_dir, self.manifest, self.results, SCHEMA_DIR)
        self.assertTrue(any("manifest_id" in i for i in issues))

    def test_non_json_stray_file_flagged(self):
        with open(os.path.join(self.run_dir, "results", "junk.txt"), "w") as fh:
            fh.write("not a result")
        issues = iso.validate_run_outputs(self.run_dir, self.manifest, self.results, SCHEMA_DIR)
        self.assertTrue(any("junk.txt" in i for i in issues))

    def test_validates_result_schema_roundtrip(self):
        # The factory results must themselves be schema-valid.
        for res in self.results:
            self.assertEqual(v.validate_payload(res, "result", SCHEMA_DIR), [])


if __name__ == "__main__":
    unittest.main()
