"""Tests for pilot.measured_report: cross-run aggregation of isolated
measured lexical baseline runs into a category-first baseline report with
variance across the runs, provenance separation, and explicit limitations.
"""
import json
import os
import tempfile
import unittest

import pilot.measured_report as mr
import pilot.validate as v

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(ROOT, "schemas")

CATEGORIES = ["accurate_retrieval", "abstention"]


def _manifest(manifest_id, mode="measured"):
    return {
        "schema_version": "run_manifest@1.0.0",
        "manifest_id": manifest_id,
        "created_iso": "2026-08-04T00:00:00Z",
        "mode": mode,
        "hermes": {"version": "test", "commit": "test"},
        "provider_versions": {
            "hermes_memory": {"version": "stub", "deployment_mode": "bundled"},
            "lexical_baseline": {"version": "bm25-1.0.0", "deployment_mode": "in_process"},
            "hindsight": {"version": "stub", "deployment_mode": "self_hosted"},
            "mnemosyne": {"version": "stub", "deployment_mode": "local_sqlite"},
        },
        "budgets": {"recall_tokens": 4096},
        "scenario_set": {"name": "corpus", "version": "1.0.0", "split": "dev",
                         "scenario_count": 2},
        "run": {"seed": 7, "repetitions": 3, "deterministic": True,
                "measured_providers": ["lexical_baseline"]},
        "generator": {"name": "test", "version": "0", "commit": "none"},
        "environment": {"os": "test", "python_version": "3", "machine": "x86_64",
                        "cpu_count": 2, "captured_iso": "2026-08-04T00:00:00Z"},
    }


def _result(result_id, manifest_id, scenario_id, category, correctness,
            p50=1.0, p95=2.0, outcome="ok", measured=True):
    kind = "measured" if measured else "simulated"
    prov = "hmem-measured" if measured else "inferred"
    return {
        "schema_version": "result@1.0.0",
        "result_id": result_id,
        "manifest_id": manifest_id,
        "scenario_id": scenario_id,
        "provider_id": "lexical_baseline",
        "category": category,
        "scenario_split": "dev",
        "measurement_kind": kind,
        "provenance": prov,
        "vendor": {"vendor_reported": False, "label": None, "reported_at_iso": None},
        "outcome": outcome,
        "setup": {"success": True,
                  "steps": [{"name": "availability", "status": "ok", "detail": "ok"}],
                  "recovery": {"attempted": False, "success": False, "detail": None}},
        "measurements": {
            "latency_ms": {"p50": p50, "p95": p95, "n": 3, "samples": [p50, p50, p95]},
            "ingest_latency_ms": {"p50": 0.1, "p95": 0.2, "n": 3, "samples": [0.1]},
            "recall_latency_ms": {"p50": 0.1, "p95": 0.2, "n": 3, "samples": [0.1]},
            "tokens": {"stored": 20, "retrieved": 4, "injected": 4},
            "resources": {"cpu_percent": 1.0, "peak_ram_mb": 10.0,
                          "disk_growth_mb": 0.0, "network_egress_bytes": 0},
        },
        "answer": {"text": "valkyrie", "evidence_turns": [0], "abstained": False},
        "scores": {
            "correctness": correctness, "evidence_precision": 1.0, "evidence_recall": 1.0,
            "stale_reuse": None, "leakage": None, "abstention_correct": None,
            "poisoning_success": None, "synthesis": None,
            "recovery_success": None, "setup_success": 1.0,
        },
        "scoring_note": "test",
    }


def _write_run(parent, run_id, correctness_by_category, latency_by_category=None,
               measured=True):
    """Write one synthetic run dir under parent; returns its absolute path."""
    run_dir = os.path.join(parent, run_id)
    os.makedirs(os.path.join(run_dir, "results"), exist_ok=True)
    manifest = _manifest(f"dryrun-{run_id}")
    results = []
    for cat in CATEGORIES:
        for i, corr in enumerate(correctness_by_category.get(cat, [1.0])):
            p50, p95 = (latency_by_category or {}).get(cat, (1.0, 2.0))
            results.append(_result(
                f"dryrun-{run_id}--{cat}-{i}--lexical_baseline",
                manifest["manifest_id"], f"{cat}-{i}", cat, corr, p50=p50, p95=p95,
                measured=measured))
    with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    for res in results:
        with open(os.path.join(run_dir, "results", f"{res['result_id']}.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
    return run_dir


class TestDiscoverRuns(unittest.TestCase):
    def test_expands_parent_dir_children(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        a = _write_run(parent, "run-a", {"accurate_retrieval": [1.0]})
        b = _write_run(parent, "run-b", {"accurate_retrieval": [0.5]})
        found = mr.discover_runs([parent])
        self.assertEqual([os.path.basename(p) for p in found], ["run-a", "run-b"])
        self.assertIn(a, found)
        self.assertIn(b, found)

    def test_accepts_explicit_run_dir(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        a = _write_run(parent, "run-a", {"accurate_retrieval": [1.0]})
        found = mr.discover_runs([a])
        self.assertEqual(found, [a])

    def test_dedupes_repeated_paths(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        a = _write_run(parent, "run-a", {"accurate_retrieval": [1.0]})
        b = _write_run(parent, "run-b", {"accurate_retrieval": [0.5]})
        # a is given directly twice AND once via parent expansion; the
        # two distinct run dirs (a, b) must survive, duplicates must not.
        found = mr.discover_runs([a, parent, a])
        self.assertEqual(len(found), 2)
        self.assertIn(a, found)
        self.assertIn(b, found)


class TestLoadRun(unittest.TestCase):
    def test_load_run_returns_manifest_and_results(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        run_dir = _write_run(parent, "run-a", {"accurate_retrieval": [1.0]})
        loaded = mr.load_run(run_dir, SCHEMA_DIR)
        self.assertEqual(loaded["issues"], [])
        self.assertEqual(loaded["manifest"]["manifest_id"], "dryrun-run-a")
        self.assertEqual(len(loaded["results"]), 2)

    def test_schema_invalid_result_surfaces_issue(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        run_dir = _write_run(parent, "run-a", {"accurate_retrieval": [1.0]})
        bad_path = os.path.join(run_dir, "results")
        name = sorted(os.listdir(bad_path))[0]
        with open(os.path.join(bad_path, name), "w", encoding="utf-8") as fh:
            json.dump({"schema_version": "result@1.0.0", "result_id": "x"}, fh)
        loaded = mr.load_run(run_dir, SCHEMA_DIR)
        self.assertGreater(len(loaded["issues"]), 0)


class TestAggregateRuns(unittest.TestCase):
    def test_aggregates_three_runs_with_category_stats(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        _write_run(parent, "run-1", {"accurate_retrieval": [1.0], "abstention": [0.5]},
                   latency_by_category={"accurate_retrieval": (1.0, 2.0),
                                        "abstention": (3.0, 5.0)})
        _write_run(parent, "run-2", {"accurate_retrieval": [1.0], "abstention": [0.5]},
                   latency_by_category={"accurate_retrieval": (1.2, 2.5),
                                        "abstention": (3.5, 6.0)})
        _write_run(parent, "run-3", {"accurate_retrieval": [1.0], "abstention": [0.5]},
                   latency_by_category={"accurate_retrieval": (0.9, 1.8),
                                        "abstention": (2.8, 4.5)})
        rep = mr.aggregate_runs(mr.discover_runs([parent]), SCHEMA_DIR)
        self.assertEqual(rep["totals"]["runs"], 3)
        self.assertEqual(rep["totals"]["results"], 6)
        self.assertEqual(rep["totals"]["measured"], 6)
        self.assertEqual(rep["totals"]["simulated"], 0)
        ar = rep["categories"]["accurate_retrieval"]
        self.assertEqual(ar["correctness_mean_across_runs"], 1.0)
        self.assertEqual(ar["correctness_std_across_runs"], 0.0)
        ab = rep["categories"]["abstention"]
        self.assertEqual(ab["correctness_mean_across_runs"], 0.5)
        # latency variance across runs is real
        self.assertGreater(ab["latency_p50_std_across_runs"], 0.0)
        self.assertEqual(ab["latency_p50_mean_across_runs"], 3.1)
        self.assertEqual(len(rep["per_run"]), 3)

    def test_correctness_variance_across_runs_reflected(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        _write_run(parent, "run-1", {"accurate_retrieval": [1.0]})
        _write_run(parent, "run-2", {"accurate_retrieval": [0.0]})
        rep = mr.aggregate_runs(mr.discover_runs([parent]), SCHEMA_DIR)
        ar = rep["categories"]["accurate_retrieval"]
        self.assertEqual(ar["correctness_mean_across_runs"], 0.5)
        self.assertEqual(ar["correctness_std_across_runs"], 0.5)
        self.assertEqual(ar["correctness_min"], 0.0)
        self.assertEqual(ar["correctness_max"], 1.0)

    def test_provenance_counts_separate_measured_from_simulated(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        _write_run(parent, "run-1", {"accurate_retrieval": [1.0]}, measured=True)
        _write_run(parent, "run-2", {"accurate_retrieval": [1.0]}, measured=False)
        rep = mr.aggregate_runs(mr.discover_runs([parent]), SCHEMA_DIR)
        self.assertEqual(rep["provenance_counts"]["measured"], 2)
        self.assertEqual(rep["provenance_counts"]["simulated"], 2)

    def test_failures_totalled(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        run_dir = _write_run(parent, "run-1", {"accurate_retrieval": [1.0]})
        # Corrupt one result into a failure outcome.
        res_path = os.path.join(run_dir, "results")
        for name in os.listdir(res_path):
            with open(os.path.join(res_path, name), "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            doc["outcome"] = "failure"
            doc["failure"] = {"stage": "recall", "error_type": "RuntimeError",
                              "message": "boom"}
            with open(os.path.join(res_path, name), "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
        rep = mr.aggregate_runs([run_dir], SCHEMA_DIR)
        self.assertEqual(rep["totals"]["failures"], 2)


class TestReportGeneration(unittest.TestCase):
    def test_generate_measured_report_emits_md_and_json(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        _write_run(parent, "run-1", {"accurate_retrieval": [1.0], "abstention": [0.5]})
        _write_run(parent, "run-2", {"accurate_retrieval": [1.0], "abstention": [0.5]})
        rep = mr.generate_measured_report(mr.discover_runs([parent]), SCHEMA_DIR)
        self.assertIn("report_md", rep)
        self.assertIn("report_json", rep)
        md = rep["report_md"]
        self.assertIn("Measured", md)
        self.assertIn("accurate_retrieval", md)
        self.assertIn("abstention", md)
        self.assertIn("variance", md.lower())
        self.assertIn("limitations", md.lower())

    def test_report_limitations_mention_separation(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        _write_run(parent, "run-1", {"accurate_retrieval": [1.0]})
        rep = mr.generate_measured_report(mr.discover_runs([parent]), SCHEMA_DIR)
        joined = "\n".join(rep["report_json"]["limitations"]).lower()
        self.assertIn("simulated", joined)
        self.assertIn("measured", joined)

    def test_schema_valid_roundtrip_of_factory_artifacts(self):
        parent = tempfile.mkdtemp(prefix="hmem-mr-")
        run_dir = _write_run(parent, "run-1", {"accurate_retrieval": [1.0]})
        loaded = mr.load_run(run_dir, SCHEMA_DIR)
        self.assertEqual(v.validate_payload(loaded["manifest"], "run_manifest", SCHEMA_DIR), [])
        for res in loaded["results"]:
            self.assertEqual(v.validate_payload(res, "result", SCHEMA_DIR), [])


if __name__ == "__main__":
    unittest.main()
