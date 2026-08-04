"""Tests for pilot.runner: dry-run orchestration, failure capture, unavailable providers."""
import os
import tempfile
import unittest

import pilot.adapters as ad
import pilot.runner as rn
import pilot.validate as v

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(ROOT, "schemas")
SCENARIOS_DIR = os.path.join(ROOT, "scenarios")


class RaisingAdapter(ad.BaseAdapter):
    """Adapter that blows up during ingest, to prove failures are captured, not discarded."""

    provider_id = "hermes_memory"
    display_name = "raising stub"
    integration_state = "test"
    policy = {"raises": True}

    def ingest(self, history):
        raise RuntimeError("simulated ingest crash")


class TestDryRun(unittest.TestCase):
    def setUp(self):
        self.out_dir = tempfile.mkdtemp(prefix="hmem-run-")
        self.config = rn.RunConfig(
            schema_dir=SCHEMA_DIR,
            scenarios_dir=SCENARIOS_DIR,
            out_dir=self.out_dir,
            providers=["hermes_memory", "lexical_baseline", "hindsight", "mnemosyne"],
            unavailable=set(),
            repetitions=2,
            seed=7,
            mode="dry_run",
        )

    def test_dry_run_produces_manifest_and_results(self):
        summary = rn.run_dry_run(self.config)
        self.assertGreater(len(summary["results"]), 0)
        self.assertIn("manifest", summary)
        self.assertIn("validation_errors", summary)

    def test_every_result_validates_against_result_schema(self):
        summary = rn.run_dry_run(self.config)
        for res in summary["results"]:
            errors = v.validate_payload(res, "result", SCHEMA_DIR)
            self.assertEqual(errors, [], f"result {res['result_id']} invalid: {errors}")

    def test_manifest_validates_against_manifest_schema(self):
        summary = rn.run_dry_run(self.config)
        errors = v.validate_payload(summary["manifest"], "run_manifest", SCHEMA_DIR)
        self.assertEqual(errors, [], f"manifest invalid: {errors}")

    def test_outputs_written_to_disk(self):
        summary = rn.run_dry_run(self.config)
        paths = rn.write_outputs(self.out_dir, summary)
        self.assertTrue(os.path.exists(paths["manifest"]))
        self.assertTrue(os.path.exists(paths["results_dir"]))
        self.assertTrue(os.path.exists(paths["validation_errors"]))

    def test_validation_errors_reported_not_discarded(self):
        bad_dir = tempfile.mkdtemp(prefix="hmem-badscen-")
        with open(os.path.join(bad_dir, "bad.json"), "w") as fh:
            fh.write('{"schema_version": "scenario@1.0.0", "scenario_id": "broken"}')
        cfg = rn.RunConfig(
            schema_dir=SCHEMA_DIR, scenarios_dir=bad_dir, out_dir=self.out_dir,
            providers=["hermes_memory"], unavailable=set(), repetitions=1, seed=1, mode="dry_run",
        )
        summary = rn.run_dry_run(cfg)
        self.assertGreater(len(summary["validation_errors"]), 0)


class TestFailureCapture(unittest.TestCase):
    def test_adapter_crash_is_captured_not_discarded(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-fail-")
        config = rn.RunConfig(
            schema_dir=SCHEMA_DIR, scenarios_dir=SCENARIOS_DIR, out_dir=out_dir,
            providers=["hermes_memory"], unavailable=set(), repetitions=1, seed=1, mode="dry_run",
        )
        summary = rn.run_dry_run(config, adapter_registry={"hermes_memory": RaisingAdapter})
        failures = [r for r in summary["results"] if r["outcome"] == "failure"]
        self.assertGreater(len(failures), 0)
        res = failures[0]
        self.assertEqual(res["failure"]["stage"], "ingest")
        self.assertIn("simulated ingest crash", res["failure"]["message"])
        # Failure results must still be schema-valid.
        errors = v.validate_payload(res, "result", SCHEMA_DIR)
        self.assertEqual(errors, [])


class TestUnavailableProvider(unittest.TestCase):
    def test_unavailable_provider_reported_as_unsupported_and_valid(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-unavail-")
        config = rn.RunConfig(
            schema_dir=SCHEMA_DIR, scenarios_dir=SCENARIOS_DIR, out_dir=out_dir,
            providers=["hindsight"], unavailable={"hindsight"}, repetitions=1, seed=1, mode="dry_run",
        )
        summary = rn.run_dry_run(config)
        results = summary["results"]
        self.assertGreater(len(results), 0)
        for res in results:
            self.assertEqual(res["outcome"], "unsupported")
            self.assertFalse(res["setup"]["success"])
            errors = v.validate_payload(res, "result", SCHEMA_DIR)
            self.assertEqual(errors, [])


class TestScoring(unittest.TestCase):
    def test_correct_answer_scores_1(self):
        scenario = {
            "scenario_id": "test-0001",
            "category": "accurate_retrieval",
            "expected": {"answer": "willow-01", "evidence_turns": [0], "abstain": False, "premise_invalid": False},
        }
        adapter_out = {"text": "willow-01", "evidence_turns": [0], "abstained": False, "premise_invalid": False}
        scores = rn.score_result(scenario, adapter_out)
        self.assertEqual(scores["correctness"], 1.0)
        self.assertEqual(scores["evidence_precision"], 1.0)
        self.assertEqual(scores["evidence_recall"], 1.0)

    def test_wrong_answer_scores_0(self):
        scenario = {
            "scenario_id": "test-0002",
            "category": "accurate_retrieval",
            "expected": {"answer": "willow-01", "evidence_turns": [0], "abstain": False, "premise_invalid": False},
        }
        adapter_out = {"text": "beech-02", "evidence_turns": [1], "abstained": False, "premise_invalid": False}
        scores = rn.score_result(scenario, adapter_out)
        self.assertEqual(scores["correctness"], 0.0)

    def test_expected_abstain_scores_1_when_abstained(self):
        scenario = {
            "scenario_id": "test-0003",
            "category": "abstention",
            "expected": {"answer": None, "evidence_turns": [], "abstain": True, "premise_invalid": False},
        }
        adapter_out = {"text": None, "evidence_turns": [], "abstained": True, "premise_invalid": False}
        scores = rn.score_result(scenario, adapter_out)
        self.assertEqual(scores["correctness"], 1.0)

    def test_expected_abstain_scores_0_when_hallucinated(self):
        scenario = {
            "scenario_id": "test-0004",
            "category": "abstention",
            "expected": {"answer": None, "evidence_turns": [], "abstain": True, "premise_invalid": False},
        }
        adapter_out = {"text": "smtp.relay.example", "evidence_turns": [], "abstained": False, "premise_invalid": False}
        scores = rn.score_result(scenario, adapter_out)
        self.assertEqual(scores["correctness"], 0.0)


if __name__ == "__main__":
    unittest.main()
