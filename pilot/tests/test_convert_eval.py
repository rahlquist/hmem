"""Tests for pilot.convert_eval: adapter converting the evaluation corpus
(rich scenario schema, evaluation/fixtures/scenarios) into the pilot's
minimal scenario schema so the full ~30-case reviewed corpus can be run
through the pilot harness.

RED phase: these tests define the converter contract before any
implementation exists.
"""
import json
import os
import tempfile
import unittest

import pilot.convert_eval as ce
import pilot.validate as v

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))  # repo root: tests/ -> pilot/ -> repo
EVAL_SCENARIO_DIR = os.path.join(ROOT, "evaluation", "fixtures", "scenarios")
PILOT_SCHEMA_DIR = os.path.join(ROOT, "pilot", "schemas")

# Category map: evaluation kebab-case -> pilot snake_case enum
EXPECTED_CATEGORY_MAP = {
    "retrieval": "accurate_retrieval",
    "temporal-updates": "temporal_validity",
    "selective-forgetting": "selective_forgetting",
    "long-range-synthesis": "long_range_synthesis",
    "procedural-memory": "procedural_memory",
    "premise-awareness": "premise_awareness",
    "isolation": "isolation",
    "abstention": "abstention",
    "poisoning-resistance": "poisoning_resistance",
    "restart-recovery": "recovery",
}


def load_eval(name):
    with open(os.path.join(EVAL_SCENARIO_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


class TestCategoryMapping(unittest.TestCase):
    def test_all_ten_evaluation_categories_mapped(self):
        self.assertEqual(set(ce.CATEGORY_MAP.keys()), set(EXPECTED_CATEGORY_MAP.keys()))

    def test_mapping_targets_are_pilot_enum_values(self):
        for src, dst in ce.CATEGORY_MAP.items():
            self.assertEqual(dst, EXPECTED_CATEGORY_MAP[src])


class TestScenarioConversion(unittest.TestCase):
    def test_abstention_fixture_converts(self):
        doc = ce.convert_scenario(load_eval("ABST-01-never-mentioned.json"))
        self.assertEqual(doc["scenario_id"], "abst-01")
        self.assertEqual(doc["category"], "abstention")
        self.assertEqual(doc["split"], "dev")
        self.assertTrue(doc["expected"]["abstain"])
        self.assertFalse(doc["expected"]["premise_invalid"])
        self.assertIsNone(doc["expected"]["answer"])
        self.assertEqual(doc["expected"]["evidence_turns"], [])
        self.assertEqual(len(doc["history"]), 2)

    def test_retrieval_fixture_converts(self):
        doc = ce.convert_scenario(load_eval("RET-01-basic-retrieval.json"))
        self.assertEqual(doc["category"], "accurate_retrieval")
        self.assertEqual(doc["expected"]["answer"], "valkyrie")
        self.assertEqual(doc["expected"]["evidence_turns"], [0])
        self.assertFalse(doc["expected"]["abstain"])

    def test_temporal_fixture_superseded(self):
        doc = ce.convert_scenario(load_eval("TEMP-01-newest-value-wins.json"))
        self.assertEqual(doc["category"], "temporal_validity")
        self.assertEqual(doc["expected"]["answer"], "hourly at 04:00")
        self.assertEqual(doc["expected"]["evidence_turns"], [1])
        self.assertIn("daily at 02:00", doc["expected"]["superseded"] or "")

    def test_forgetting_fixture_deleted(self):
        doc = ce.convert_scenario(load_eval("FORGET-01-explicit-deletion.json"))
        self.assertEqual(doc["category"], "selective_forgetting")
        self.assertTrue(doc["expected"]["abstain"])
        self.assertEqual(doc["expected"]["evidence_turns"], [])
        self.assertIn("workshop VM", doc["expected"]["deleted"] or "")

    def test_deleted_value_strips_directive_prefix(self):
        """The stale value must be the fact, not the 'please delete that' wrapper:
        scoring flags stale reuse by token containment, so the directive
        sentence must not pollute expected.deleted."""
        doc = ce.convert_scenario(load_eval("FORGET-01-explicit-deletion.json"))
        deleted = (doc["expected"]["deleted"] or "").lower()
        self.assertNotIn("please", deleted)
        self.assertNotIn("delete", deleted)
        self.assertTrue(deleted.startswith("the workshop vm"))

    def test_superseded_keeps_subject_sentence(self):
        """Superseded events are statements, not directives: keep the full
        content so stale-reuse detection matches a recalled old fact."""
        doc = ce.convert_scenario(load_eval("TEMP-01-newest-value-wins.json"))
        self.assertIn("daily at 02:00", doc["expected"]["superseded"] or "")

    def test_poisoning_fixture_untrusted_turn(self):
        doc = ce.convert_scenario(load_eval("POIS-01-untrusted-web-instruction.json"))
        self.assertEqual(doc["category"], "poisoning_resistance")
        self.assertEqual(doc["expected"]["answer"], "hourly at 04:00")
        untrusted = [t for t in doc["history"] if t.get("untrusted")]
        self.assertEqual(len(untrusted), 1)
        self.assertIn("web", untrusted[0]["content"].lower())

    def test_premise_rejection_fixture(self):
        doc = ce.convert_scenario(load_eval("PREM-01-false-premise.json"))
        self.assertEqual(doc["category"], "premise_awareness")
        self.assertTrue(doc["expected"]["premise_invalid"])
        self.assertIsNone(doc["expected"]["answer"])

    def test_isolation_fixture_converts(self):
        doc = ce.convert_scenario(load_eval("ISO-01-profile-boundary.json"))
        self.assertEqual(doc["category"], "isolation")
        self.assertTrue(doc["expected"]["abstain"])
        self.assertEqual(doc["expected"]["evidence_turns"], [])

    def test_procedural_fixture_converts(self):
        doc = ce.convert_scenario(load_eval("PROC-01-discovered-fix.json"))
        self.assertEqual(doc["category"], "procedural_memory")
        self.assertIn("vm.max_map_count", doc["expected"]["answer"] or "")

    def test_synthesis_fixture_converts(self):
        doc = ce.convert_scenario(load_eval("SYNTH-01-cross-session-combine.json"))
        self.assertEqual(doc["category"], "long_range_synthesis")
        self.assertEqual(doc["expected"]["evidence_turns"], [0, 1, 2])

    def test_restart_fixture_maps_to_recovery(self):
        doc = ce.convert_scenario(load_eval("RESTART-01-restart-persistence.json"))
        self.assertEqual(doc["category"], "recovery")
        self.assertEqual(doc["expected"]["answer"], "frigg at port 2525")
        self.assertEqual(doc["expected"]["evidence_turns"], [0])

    def test_held_out_split_mapped(self):
        doc = ce.convert_scenario(load_eval("ABST-03-version-never-known.json"))
        self.assertEqual(doc["split"], "held_out")

    def test_tool_speaker_mapped_to_system_role(self):
        doc = ce.convert_scenario(load_eval("POIS-02-injected-cleanup-command.json"))
        roles = {t["role"] for t in doc["history"]}
        self.assertIn("system", roles)

    def test_provenance_and_privacy_mapped(self):
        doc = ce.convert_scenario(load_eval("RET-01-basic-retrieval.json"))
        self.assertTrue(doc["provenance"]["reviewed"])
        self.assertEqual(doc["provenance"]["license"], "CC0-1.0")
        self.assertTrue(doc["privacy"]["synthetic"])
        self.assertFalse(doc["privacy"]["contains_real_data"])

    def test_history_has_sessions_and_timestamps(self):
        doc = ce.convert_scenario(load_eval("RET-02-dense-distractor-retrieval.json"))
        for turn in doc["history"]:
            self.assertIn("session", turn)
            self.assertIn("ts_iso", turn)

    def test_converted_doc_matches_its_source_category(self):
        """Every converted scenario's pilot category is the mapped eval category."""
        for name in sorted(os.listdir(EVAL_SCENARIO_DIR)):
            if not name.endswith(".json"):
                continue
            src = load_eval(name)
            doc = ce.convert_scenario(src)
            self.assertEqual(doc["category"], ce.CATEGORY_MAP[src["category"]],
                             f"category mismatch for {name}")


class TestCorpusConversion(unittest.TestCase):
    def test_all_30_fixtures_convert_and_validate(self):
        converted = ce.convert_corpus(EVAL_SCENARIO_DIR)
        self.assertEqual(len(converted["converted"]), 30)
        self.assertEqual(converted["errors"], {})
        for doc in converted["converted"]:
            errors = v.validate_payload(doc, "scenario", PILOT_SCHEMA_DIR)
            self.assertEqual(errors, [], f"converted {doc['scenario_id']} invalid: {errors}")

    def test_ten_categories_covered(self):
        converted = ce.convert_corpus(EVAL_SCENARIO_DIR)
        cats = {d["category"] for d in converted["converted"]}
        self.assertEqual(len(cats), 10)

    def test_splits_preserved(self):
        converted = ce.convert_corpus(EVAL_SCENARIO_DIR)
        splits = {}
        for d in converted["converted"]:
            splits[d["scenario_id"]] = d["split"]
        held_out = [sid for sid, sp in splits.items() if sp == "held_out"]
        self.assertEqual(len(held_out), 10)

    def test_write_corpus_writes_files(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-evalconv-")
        written = ce.write_corpus(EVAL_SCENARIO_DIR, out_dir)
        self.assertEqual(len(written), 30)
        for path in written:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            errors = v.validate_payload(doc, "scenario", PILOT_SCHEMA_DIR)
            self.assertEqual(errors, [], f"{path} invalid: {errors}")


if __name__ == "__main__":
    unittest.main()
