"""Tests for pilot.report: category-first aggregation, limitations, variance, provenance."""
import os
import tempfile
import unittest

import pilot.report as rp
import pilot.runner as rn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(ROOT, "schemas")
SCENARIOS_DIR = os.path.join(ROOT, "scenarios")


def build_report(providers=("hermes_memory", "lexical_baseline", "hindsight", "mnemosyne"),
                 unavailable=()):
    out_dir = tempfile.mkdtemp(prefix="hmem-report-")
    config = rn.RunConfig(
        schema_dir=SCHEMA_DIR, scenarios_dir=SCENARIOS_DIR, out_dir=out_dir,
        providers=list(providers), unavailable=set(unavailable), repetitions=2, seed=7, mode="dry_run",
    )
    summary = rn.run_dry_run(config)
    return rp.generate_report(summary["manifest"], summary["results"], summary["validation_errors"])


class TestReportStructure(unittest.TestCase):
    def test_report_has_markdown_and_json(self):
        report = build_report()
        self.assertIn("report_md", report)
        self.assertIn("report_json", report)
        self.assertIsInstance(report["report_md"], str)
        self.assertGreater(len(report["report_md"]), 200)

    def test_markdown_contains_required_sections(self):
        md = build_report()["report_md"]
        for section in ("Category Results", "Limitations", "Variance"):
            self.assertIn(section, md, f"missing section {section}")

    def test_json_groups_by_category(self):
        report = build_report()["report_json"]
        self.assertIn("categories", report)
        cats = set(report["categories"].keys())
        self.assertIn("accurate_retrieval", cats)
        self.assertIn("recovery", cats)
        for cat in cats:
            self.assertIn("providers", report["categories"][cat])
            self.assertIn("n", report["categories"][cat])

    def test_provenance_separation(self):
        report = build_report()["report_json"]
        counts = report["provenance_counts"]
        self.assertIn("simulated", counts)
        self.assertEqual(counts.get("measured", 0), 0)

    def test_unavailable_provider_surfaces_in_report(self):
        report = build_report(providers=("hindsight",), unavailable=("hindsight",))["report_json"]
        self.assertGreaterEqual(report["unavailable"], 1)
        md = build_report(providers=("hindsight",), unavailable=("hindsight",))["report_md"]
        self.assertIn("unsupported", md)

    def test_limitations_listed(self):
        report = build_report()["report_json"]
        self.assertGreaterEqual(len(report["limitations"]), 3)

    def test_variance_reported(self):
        report = build_report()["report_json"]
        self.assertIn("variance", report)


if __name__ == "__main__":
    unittest.main()
