"""Tests for pilot.cli: isolated + measured run wiring.

The CLI must support --isolated (unique run dir per invocation) and
--measured <provider-ids> (real lexical baseline executes, results labeled
measured/hmem-measured). Critically, in isolated mode every artifact
(manifest, results, validation_errors, report) must land inside the unique
run directory — never in the out_dir root, where a later invocation would
silently overwrite a previous run's manifest/report (stale-result leakage).
"""
import json
import os
import tempfile
import unittest

import pilot.cli as cli
import pilot.validate as v

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(ROOT, "schemas")
SCENARIOS_DIR = os.path.join(ROOT, "scenarios")


class TestIsolatedMeasuredCli(unittest.TestCase):
    def test_isolated_measured_run_writes_into_unique_run_dir(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-cli-")
        code = cli.main([
            "--out-dir", out_dir,
            "--scenarios-dir", SCENARIOS_DIR,
            "--providers", "lexical_baseline",
            "--mode", "measured",
            "--isolated",
            "--measured", "lexical_baseline",
            "--repetitions", "1",
            "--seed", "7",
        ])
        self.assertEqual(code, 0)
        runs_root = os.path.join(out_dir, "runs")
        self.assertTrue(os.path.isdir(runs_root), "runs/ dir missing")
        run_dirs = [d for d in os.listdir(runs_root)
                    if os.path.isdir(os.path.join(runs_root, d))]
        self.assertEqual(len(run_dirs), 1, "expected exactly one run dir")
        run_dir = os.path.join(runs_root, run_dirs[0])

        # Every artifact must be inside the run dir, NOT the out_dir root.
        self.assertTrue(os.path.isfile(os.path.join(run_dir, "manifest.json")))
        self.assertTrue(os.path.isdir(os.path.join(run_dir, "results")))
        self.assertGreater(len(os.listdir(os.path.join(run_dir, "results"))), 0)
        self.assertFalse(os.path.isfile(os.path.join(out_dir, "manifest.json")),
                         "stale manifest leaked into out_dir root")
        self.assertFalse(os.path.isfile(os.path.join(out_dir, "report.md")),
                         "stale report leaked into out_dir root")

    def test_two_isolated_runs_do_not_collide(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-cli2-")
        args = [
            "--out-dir", out_dir,
            "--scenarios-dir", SCENARIOS_DIR,
            "--providers", "lexical_baseline",
            "--mode", "measured",
            "--isolated",
            "--measured", "lexical_baseline",
            "--repetitions", "1",
            "--seed", "7",
        ]
        self.assertEqual(cli.main(args), 0)
        self.assertEqual(cli.main(args), 0)
        run_dirs = sorted(os.listdir(os.path.join(out_dir, "runs")))
        self.assertEqual(len(run_dirs), 2,
                         "second invocation must create a NEW run dir, "
                         "never overwrite the first")
        ids = set()
        for name in run_dirs:
            with open(os.path.join(out_dir, "runs", name, "manifest.json"),
                      encoding="utf-8") as fh:
                ids.add(json.load(fh)["manifest_id"])
        self.assertEqual(len(ids), 2, "run dirs must carry distinct manifests")

    def test_measured_run_results_labeled_measured_and_schema_valid(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-cli3-")
        code = cli.main([
            "--out-dir", out_dir,
            "--scenarios-dir", SCENARIOS_DIR,
            "--providers", "lexical_baseline",
            "--mode", "measured",
            "--isolated",
            "--measured", "lexical_baseline",
            "--repetitions", "1",
            "--seed", "7",
        ])
        self.assertEqual(code, 0)
        run_dir = os.path.join(out_dir, "runs",
                               sorted(os.listdir(os.path.join(out_dir, "runs")))[0])
        results_dir = os.path.join(run_dir, "results")
        for name in sorted(os.listdir(results_dir)):
            with open(os.path.join(results_dir, name), encoding="utf-8") as fh:
                doc = json.load(fh)
            self.assertEqual(doc["measurement_kind"], "measured")
            self.assertEqual(doc["provenance"], "hmem-measured")
            errors = v.validate_payload(doc, "result", SCHEMA_DIR)
            self.assertEqual(errors, [], f"{name} invalid: {errors}")


class TestPlainCli(unittest.TestCase):
    def test_non_isolated_run_keeps_out_dir_layout(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-cli-plain-")
        code = cli.main([
            "--out-dir", out_dir,
            "--scenarios-dir", SCENARIOS_DIR,
            "--providers", "hermes_memory",
            "--repetitions", "1",
            "--seed", "7",
        ])
        self.assertEqual(code, 0)
        # Plain mode keeps the historical layout: artifacts in out_dir root.
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "manifest.json")))
        self.assertTrue(os.path.isfile(os.path.join(out_dir, "report.md")))


if __name__ == "__main__":
    unittest.main()
