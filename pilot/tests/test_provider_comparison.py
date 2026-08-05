"""Tests for measured provider comparison reporting."""

import json
import os
import tempfile
import unittest

from pilot import provider_comparison as pc
from pilot import runner as rn
from pilot.adapters import BaseAdapter

from pilot.tests import test_measured_report as fixtures


SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas")


def write_provider_run(parent, run_id, provider, correctness, measured=True):
    run_dir = fixtures._write_run(
        parent,
        run_id,
        {
            "accurate_retrieval": [correctness],
            "abstention": [correctness],
        },
        measured=measured,
    )
    manifest_path = os.path.join(run_dir, "manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest["run"]["measured_providers"] = [provider] if measured else []
    manifest["provider_versions"][provider]["version"] = "measured-test"
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    results_dir = os.path.join(run_dir, "results")
    for name in os.listdir(results_dir):
        path = os.path.join(results_dir, name)
        with open(path, encoding="utf-8") as handle:
            result = json.load(handle)
        result["provider_id"] = provider
        result["result_id"] = result["result_id"].replace(
            "lexical_baseline", provider
        )
        os.unlink(path)
        with open(os.path.join(results_dir, f"{result['result_id']}.json"), "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
    return run_dir


class TestProviderComparison(unittest.TestCase):
    def test_separates_provider_scores(self):
        parent = tempfile.mkdtemp(prefix="hmem-comparison-")
        runs = []
        for index in range(3):
            runs.append(write_provider_run(parent, f"bm25-{index}", "lexical_baseline", 0.5))
            runs.append(write_provider_run(parent, f"hermes-{index}", "hermes_memory", 1.0))
        report = pc.aggregate_comparison(runs, SCHEMA_DIR)
        self.assertEqual(report["totals"]["providers_measured"], 2)
        self.assertEqual(report["totals"]["runs"], 6)
        self.assertEqual(report["providers"]["lexical_baseline"]["overall_correctness_mean"], 0.5)
        self.assertEqual(report["providers"]["hermes_memory"]["overall_correctness_mean"], 1.0)

    def test_excludes_simulated_results(self):
        parent = tempfile.mkdtemp(prefix="hmem-comparison-")
        run = write_provider_run(parent, "simulated", "lexical_baseline", 1.0, measured=False)
        report = pc.aggregate_comparison([run], SCHEMA_DIR)
        self.assertNotIn("lexical_baseline", report["providers"])
        self.assertTrue(any("excluded non-measured result" in issue for issue in report["issues"]))

    def test_lists_unimplemented_providers_as_not_measured(self):
        parent = tempfile.mkdtemp(prefix="hmem-comparison-")
        run = write_provider_run(parent, "hermes", "hermes_memory", 1.0)
        report = pc.aggregate_comparison([run], SCHEMA_DIR)
        unavailable = {entry["provider_id"] for entry in report["not_measured"]}
        self.assertIn("hindsight", unavailable)
        self.assertIn("mnemosyne", unavailable)

    def test_markdown_contains_side_by_side_tables(self):
        parent = tempfile.mkdtemp(prefix="hmem-comparison-")
        runs = [
            write_provider_run(parent, "bm25", "lexical_baseline", 0.5),
            write_provider_run(parent, "hermes", "hermes_memory", 1.0),
        ]
        markdown = pc.generate_comparison(runs, SCHEMA_DIR)["report_md"]
        self.assertIn("Overall Comparison", markdown)
        self.assertIn("Category Comparison", markdown)
        self.assertIn("BM25 lexical baseline", markdown)
        self.assertIn("Hermes built-in memory", markdown)

    def test_markdown_explains_metrics_and_every_category(self):
        parent = tempfile.mkdtemp(prefix="hmem-comparison-")
        run = write_provider_run(parent, "bm25", "lexical_baseline", 0.5)
        report = pc.aggregate_comparison([run], SCHEMA_DIR)
        # Exercise all documented categories even though this small synthetic
        # fixture only contains two categories.
        template = next(iter(report["providers"]["lexical_baseline"]["categories"].values()))
        for category in pc.CATEGORY_EXPLANATIONS:
            report["providers"]["lexical_baseline"]["categories"].setdefault(
                category, dict(template)
            )
        markdown = pc.render_markdown(report)
        self.assertIn("## How to Read This Report", markdown)
        self.assertIn("**correctness:**", markdown)
        self.assertIn("**p50 ms:**", markdown)
        self.assertIn("**p95 ms:**", markdown)
        self.assertIn("**retrieved tokens:**", markdown)
        self.assertIn("**n:**", markdown)
        for category in pc.CATEGORY_EXPLANATIONS:
            self.assertIn(f"### {category}", markdown)
        self.assertEqual(
            markdown.count("**What this tests:**"), len(pc.CATEGORY_EXPLANATIONS)
        )
        self.assertEqual(
            markdown.count("**Why it matters in Hermes:**"),
            len(pc.CATEGORY_EXPLANATIONS),
        )
        self.assertEqual(markdown.count("**Example:**"), len(pc.CATEGORY_EXPLANATIONS))


class RecordingAdapter(BaseAdapter):
    provider_id = "lexical_baseline"
    measured = True
    work_dirs = []

    def __init__(self, ctx):
        super().__init__(ctx)
        self.work_dirs.append(ctx.work_dir)

    def ingest(self, history):
        return {"stored_tokens": 0}

    def recall(self, query):
        return {"text": None, "evidence_turns": [], "abstained": True}


class TestCellIsolation(unittest.TestCase):
    def test_each_scenario_gets_unique_state_directory(self):
        RecordingAdapter.work_dirs = []
        out_dir = tempfile.mkdtemp(prefix="hmem-cell-state-")
        root = os.path.dirname(os.path.dirname(__file__))
        config = rn.RunConfig(
            schema_dir=os.path.join(root, "schemas"),
            scenarios_dir=os.path.join(root, "scenarios"),
            out_dir=out_dir,
            providers=["lexical_baseline"],
            unavailable=set(),
            repetitions=1,
            seed=7,
            mode="measured",
            measured=set(),
        )
        summary = rn.run_dry_run(
            config, adapter_registry={"lexical_baseline": RecordingAdapter}
        )
        self.assertEqual(len(RecordingAdapter.work_dirs), len(summary["results"]))
        self.assertEqual(len(set(RecordingAdapter.work_dirs)), len(summary["results"]))
        self.assertTrue(all(path.startswith(os.path.join(out_dir, "state")) for path in RecordingAdapter.work_dirs))


if __name__ == "__main__":
    unittest.main()
