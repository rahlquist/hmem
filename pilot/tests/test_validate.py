"""Tests for pilot.validate: stdlib JSON-Schema validator and versioned payload validation."""
import copy
import json
import os
import unittest

import pilot.validate as v

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(ROOT, "schemas")
SCENARIOS_DIR = os.path.join(ROOT, "scenarios")

VALID_SCENARIO = {
    "schema_version": "scenario@1.0.0",
    "scenario_id": "test-0001",
    "category": "accurate_retrieval",
    "split": "dev",
    "name": "Test scenario",
    "description": "Minimal valid scenario used in tests.",
    "history": [
        {"role": "user", "content": "The staging database for project Quercus runs on host willow-01."},
        {"role": "assistant", "content": "Noted."},
    ],
    "query": "Which host runs the Quercus staging database?",
    "expected": {
        "answer": "willow-01",
        "evidence_turns": [0],
        "abstain": False,
        "premise_invalid": False,
    },
    "provenance": {
        "source": "hmem synthetic test fixture",
        "license": "MIT",
        "author": "hmem pilot",
        "created_iso": "2026-08-04T00:00:00Z",
        "reviewed": True,
    },
    "privacy": {"synthetic": True, "contains_real_data": False},
}


class TestStdlibValidator(unittest.TestCase):
    """The documented standard-library fallback must cover the keywords our schemas use."""

    def setUp(self):
        self.schema = {
            "type": "object",
            "required": ["a", "b"],
            "properties": {
                "a": {"type": "string", "pattern": "^x"},
                "b": {"type": "integer", "enum": [1, 2, 3]},
                "c": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        }

    def test_required_enforced(self):
        errors = v.validate_document({"a": "xy"}, self.schema)
        self.assertTrue(any("b" in e and "required" in e for e in errors))

    def test_type_enforced(self):
        errors = v.validate_document({"a": "xy", "b": "not-an-int"}, self.schema)
        self.assertTrue(any("b" in e for e in errors))

    def test_enum_enforced(self):
        errors = v.validate_document({"a": "xy", "b": 9}, self.schema)
        self.assertTrue(any("enum" in e for e in errors))

    def test_pattern_enforced(self):
        errors = v.validate_document({"a": "nope", "b": 1}, self.schema)
        self.assertTrue(any("pattern" in e for e in errors))

    def test_items_enforced(self):
        errors = v.validate_document({"a": "xy", "b": 1, "c": [1, 2]}, self.schema)
        self.assertTrue(any("c" in e for e in errors))

    def test_additional_properties_rejected(self):
        errors = v.validate_document({"a": "xy", "b": 1, "zzz": 5}, self.schema)
        self.assertTrue(any("zzz" in e for e in errors))

    def test_valid_document_has_no_errors(self):
        self.assertEqual(v.validate_document({"a": "xy", "b": 2, "c": ["ok"]}, self.schema), [])


class TestScenarioSchema(unittest.TestCase):
    def test_all_fixtures_validate(self):
        result = v.validate_all_scenarios(SCENARIOS_DIR, SCHEMA_DIR)
        self.assertEqual(result["invalid"], {}, f"invalid fixtures: {result['invalid']}")
        self.assertGreaterEqual(len(result["valid"]), 10, "need at least one fixture per category cluster")

    def test_missing_required_rejected(self):
        bad = copy.deepcopy(VALID_SCENARIO)
        del bad["query"]
        errors = v.validate_payload(bad, "scenario", SCHEMA_DIR)
        self.assertTrue(any("query" in e for e in errors))

    def test_bad_category_rejected(self):
        bad = copy.deepcopy(VALID_SCENARIO)
        bad["category"] = "not_a_category"
        errors = v.validate_payload(bad, "scenario", SCHEMA_DIR)
        self.assertTrue(any("category" in e for e in errors))

    def test_schema_version_mismatch_rejected(self):
        bad = copy.deepcopy(VALID_SCENARIO)
        bad["schema_version"] = "scenario@9.9.9"
        errors = v.validate_payload(bad, "scenario", SCHEMA_DIR)
        self.assertTrue(any("schema_version" in e for e in errors))

    def test_non_synthetic_fixture_rejected(self):
        bad = copy.deepcopy(VALID_SCENARIO)
        bad["privacy"]["synthetic"] = False
        errors = v.validate_payload(bad, "scenario", SCHEMA_DIR)
        self.assertTrue(any("synthetic" in e for e in errors))

    def test_valid_payload_accepts(self):
        self.assertEqual(v.validate_payload(VALID_SCENARIO, "scenario", SCHEMA_DIR), [])


class TestManifestSchema(unittest.TestCase):
    def _manifest(self):
        return {
            "schema_version": "run_manifest@1.0.0",
            "manifest_id": "run-test-0001",
            "created_iso": "2026-08-04T00:00:00Z",
            "mode": "dry_run",
            "hermes": {"version": "test", "commit": "test"},
            "provider_versions": {
                "hermes_memory": {"version": "builtin-stub", "deployment_mode": "bundled"},
                "lexical_baseline": {"version": "stub", "deployment_mode": "in_process"},
                "hindsight": {"version": "stub", "deployment_mode": "self_hosted"},
                "mnemosyne": {"version": "stub", "deployment_mode": "local_sqlite"},
            },
            "budgets": {"recall_tokens": 4096},
            "scenario_set": {"name": "smoke", "version": "1.0.0", "split": "dev", "scenario_count": 1},
            "run": {"seed": 7, "repetitions": 3, "deterministic": True},
            "generator": {"name": "test", "version": "0", "commit": "none"},
            "environment": {
                "os": "test", "python_version": "3", "machine": "x86_64",
                "cpu_count": 2, "captured_iso": "2026-08-04T00:00:00Z",
            },
        }

    def test_valid_manifest_accepts(self):
        self.assertEqual(v.validate_payload(self._manifest(), "run_manifest", SCHEMA_DIR), [])

    def test_bad_provider_id_rejected(self):
        bad = self._manifest()
        bad["provider_versions"]["ghost"] = {"version": "x", "deployment_mode": "y"}
        errors = v.validate_payload(bad, "run_manifest", SCHEMA_DIR)
        self.assertTrue(any("ghost" in e or "provider" in e for e in errors))

    def test_bad_mode_rejected(self):
        bad = self._manifest()
        bad["mode"] = "magic"
        errors = v.validate_payload(bad, "run_manifest", SCHEMA_DIR)
        self.assertTrue(any("mode" in e for e in errors))


class TestResultSchema(unittest.TestCase):
    def _result(self):
        return {
            "schema_version": "result@1.0.0",
            "result_id": "res-test-0001",
            "manifest_id": "run-test-0001",
            "scenario_id": "test-0001",
            "provider_id": "hermes_memory",
            "category": "accurate_retrieval",
            "scenario_split": "dev",
            "measurement_kind": "simulated",
            "provenance": "inferred",
            "vendor": {"vendor_reported": False, "label": None, "reported_at_iso": None},
            "outcome": "ok",
            "setup": {
                "success": True,
                "steps": [{"name": "availability", "status": "ok", "detail": "stub"}],
                "recovery": {"attempted": False, "success": False, "detail": None},
            },
            "measurements": {
                "latency_ms": {"p50": 0.1, "p95": 0.2, "n": 3, "samples": [0.1, 0.1, 0.2]},
                "ingest_latency_ms": {"p50": 0.05, "p95": 0.1, "n": 3, "samples": [0.05, 0.05, 0.1]},
                "recall_latency_ms": {"p50": 0.05, "p95": 0.1, "n": 3, "samples": [0.05, 0.05, 0.1]},
                "tokens": {"stored": 10, "retrieved": 3, "injected": 3},
                "resources": {
                    "cpu_percent": None,
                    "peak_ram_mb": None,
                    "disk_growth_mb": None,
                    "network_egress_bytes": None,
                },
            },
            "answer": {"text": "willow-01", "evidence_turns": [0], "abstained": False},
            "scores": {
                "correctness": 1.0,
                "evidence_precision": 1.0,
                "evidence_recall": 1.0,
                "stale_reuse": None,
                "leakage": None,
                "abstention_correct": None,
                "poisoning_success": None,
                "synthesis": None,
                "recovery_success": None,
                "setup_success": 1.0,
            },
            "scoring_note": "test",
        }

    def test_valid_result_accepts(self):
        self.assertEqual(v.validate_payload(self._result(), "result", SCHEMA_DIR), [])

    def test_bad_outcome_rejected(self):
        bad = self._result()
        bad["outcome"] = "exploded"
        errors = v.validate_payload(bad, "result", SCHEMA_DIR)
        self.assertTrue(any("outcome" in e for e in errors))

    def test_bad_measurement_kind_rejected(self):
        bad = self._result()
        bad["measurement_kind"] = "hallucinated"
        errors = v.validate_payload(bad, "result", SCHEMA_DIR)
        self.assertTrue(any("measurement_kind" in e for e in errors))

    def test_bad_provenance_rejected(self):
        bad = self._result()
        bad["provenance"] = "trust-me-bro"
        errors = v.validate_payload(bad, "result", SCHEMA_DIR)
        self.assertTrue(any("provenance" in e for e in errors))

    def test_failure_result_accepts(self):
        res = self._result()
        res["outcome"] = "failure"
        res["failure"] = {"stage": "ingest", "error_type": "RuntimeError", "message": "boom"}
        self.assertEqual(v.validate_payload(res, "result", SCHEMA_DIR), [])


if __name__ == "__main__":
    unittest.main()
