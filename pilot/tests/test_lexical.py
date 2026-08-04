"""Tests for pilot.lexical: the REAL deterministic Okapi BM25 lexical
baseline (BM25Index ranker + MeasuredLexicalBaselineAdapter).

The measured baseline must rank by real BM25 scores (not the stub's
content-overlap policy simulation), be deterministic, abstain on zero
lexical overlap, and carry measured=True so the runner labels its results
measurement_kind=measured / provenance=hmem-measured.
"""
import os
import tempfile
import unittest

import pilot.adapters as ad
import pilot.lexical as lx
import pilot.runner as rn
import pilot.validate as v

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(ROOT, "schemas")
SCENARIOS_DIR = os.path.join(ROOT, "scenarios")


class TestBM25Index(unittest.TestCase):
    def test_ranks_doc_with_query_terms_above_non_overlapping_doc(self):
        idx = lx.BM25Index()
        idx.add("the compute server is named valkyrie")
        idx.add("the router handles dhcp reservations")
        scores = idx.score("what server is named valkyrie")
        # score() is a sparse dict: docs with zero overlap are absent
        # (implicit score 0.0), never stored.
        self.assertGreater(scores[0], scores.get(1, 0.0))
        self.assertEqual(scores.get(1, 0.0), 0.0)

    def test_rarer_query_term_has_higher_idf(self):
        idx = lx.BM25Index()
        idx.add("rare term appears once")
        idx.add("common term appears twice")
        idx.add("common term appears twice again")
        self.assertGreater(idx._idf("rare"), idx._idf("common"))

    def test_search_returns_top_doc_and_score(self):
        idx = lx.BM25Index()
        idx.add("valkyrie is the main compute box")
        idx.add("thor is the nas")
        hits = idx.search("main compute box", top_k=1)
        self.assertEqual(hits[0][0], 0)
        self.assertGreater(hits[0][1], 0.0)

    def test_no_overlap_scores_zero_and_abstains(self):
        idx = lx.BM25Index()
        idx.add("the nas stores media backups")
        self.assertEqual(idx.score("unrelated quantum entanglement"), {})
        self.assertEqual(idx.search("unrelated quantum entanglement"), [])

    def test_deterministic_scores(self):
        idx1 = lx.BM25Index()
        idx1.add("alpha beta gamma")
        idx1.add("beta gamma delta")
        idx2 = lx.BM25Index()
        idx2.add("alpha beta gamma")
        idx2.add("beta gamma delta")
        self.assertEqual(idx1.score("beta gamma"), idx2.score("beta gamma"))

    def test_tie_breaks_to_earliest_document(self):
        idx = lx.BM25Index()
        idx.add("alpha beta")
        idx.add("alpha beta")
        hits = idx.search("alpha", top_k=1)
        self.assertEqual(hits[0][0], 0)

    def test_stopword_only_query_has_no_terms(self):
        self.assertEqual(lx.tokenize("the is a and of"), [])
        self.assertEqual(lx.tokenize("The server IS valkyrie"), ["server", "valkyrie"])

    def test_empty_corpus_scores_empty(self):
        idx = lx.BM25Index()
        self.assertEqual(idx.score("anything"), {})
        self.assertEqual(idx.search("anything"), [])

    def test_stats_report_docs_and_terms(self):
        idx = lx.BM25Index()
        idx.add("valkyrie compute")
        idx.add("thor nas")
        st = idx.stats()
        self.assertEqual(st["n_docs"], 2)
        self.assertEqual(st["terms"], 4)

    def test_avgdl_tracks_mean_document_length(self):
        idx = lx.BM25Index()
        idx.add("one two")
        idx.add("one two three four")
        self.assertEqual(idx.stats()["avgdl"], 3.0)

    def test_add_many_assigns_sequential_doc_ids(self):
        idx = lx.BM25Index()
        idx.add_many(["valkyrie compute", "thor nas"])
        self.assertEqual(len(idx._docs), 2)
        hits = idx.search("valkyrie", top_k=1)
        self.assertEqual(hits[0][0], 0)


class TestMeasuredAdapter(unittest.TestCase):
    def _ctx(self):
        work = tempfile.mkdtemp(prefix="hmem-lx-")
        scenario = {
            "scenario_id": "lex-test",
            "category": "accurate_retrieval",
            "history": [
                {"role": "user", "content": "the main compute server is now valkyrie"},
                {"role": "user", "content": "thor is the nas for backups"},
            ],
        }
        return ad.AdapterContext(work_dir=work, seed=7, scenario=scenario,
                                 budgets={"recall_tokens": 4096})

    def test_adapter_is_measured_and_versioned(self):
        self.assertTrue(lx.MeasuredLexicalBaselineAdapter.measured)
        self.assertEqual(lx.MeasuredLexicalBaselineAdapter.version, "bm25-1.0.0")
        self.assertEqual(lx.MeasuredLexicalBaselineAdapter.provider_id, "lexical_baseline")

    def test_ingest_builds_index_and_recall_returns_top_hit(self):
        a = lx.MeasuredLexicalBaselineAdapter(self._ctx())
        stats = a.ingest(self._ctx().scenario["history"])
        self.assertEqual(stats["facts"], 2)
        self.assertGreater(stats["stored_tokens"], 0)
        out = a.recall("which server is the main compute box")
        self.assertFalse(out["abstained"])
        self.assertEqual(out["evidence_turns"], [0])
        self.assertIn("valkyrie", out["text"])

    def test_recall_abstains_on_zero_overlap(self):
        a = lx.MeasuredLexicalBaselineAdapter(self._ctx())
        a.ingest(self._ctx().scenario["history"])
        out = a.recall("quantum entanglement experiment")
        self.assertTrue(out["abstained"])
        self.assertIsNone(out["text"])

    def test_recover_reports_process_local(self):
        a = lx.MeasuredLexicalBaselineAdapter(self._ctx())
        rec = a.recover()
        self.assertFalse(rec["success"])
        self.assertIn("process-local", rec["detail"])

    def test_available_in_process(self):
        a = lx.MeasuredLexicalBaselineAdapter(self._ctx())
        ok, reason = a.available()
        self.assertTrue(ok)
        self.assertIn("BM25", reason)

    def test_policy_is_naive_lexical(self):
        policy = lx.MeasuredLexicalBaselineAdapter.policy
        self.assertFalse(policy["forgets"])
        self.assertFalse(policy["boundary_aware"])
        self.assertFalse(policy["trust_aware"])
        self.assertFalse(policy["persistent"])


class TestMeasuredThroughRunner(unittest.TestCase):
    def test_measured_run_labels_results_measured(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-measured-run-")
        config = rn.RunConfig(
            schema_dir=SCHEMA_DIR, scenarios_dir=SCENARIOS_DIR, out_dir=out_dir,
            providers=["lexical_baseline"], unavailable=set(),
            repetitions=1, seed=7, mode="measured", measured={"lexical_baseline"},
        )
        summary = rn.run_dry_run(config)
        self.assertGreater(len(summary["results"]), 0)
        for res in summary["results"]:
            self.assertEqual(res["measurement_kind"], "measured")
            self.assertEqual(res["provenance"], "hmem-measured")
            self.assertEqual(res["outcome"], "ok")

    def test_stub_lexical_baseline_never_relabeled(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-stub-run-")
        config = rn.RunConfig(
            schema_dir=SCHEMA_DIR, scenarios_dir=SCENARIOS_DIR, out_dir=out_dir,
            providers=["lexical_baseline"], unavailable=set(),
            repetitions=1, seed=7, mode="dry_run",
        )
        summary = rn.run_dry_run(config)
        for res in summary["results"]:
            self.assertEqual(res["measurement_kind"], "simulated")
            self.assertEqual(res["provenance"], "inferred")

    def test_measured_run_results_are_schema_valid(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-measured-schema-")
        config = rn.RunConfig(
            schema_dir=SCHEMA_DIR, scenarios_dir=SCENARIOS_DIR, out_dir=out_dir,
            providers=["lexical_baseline"], unavailable=set(),
            repetitions=1, seed=7, mode="measured", measured={"lexical_baseline"},
        )
        summary = rn.run_dry_run(config)
        for res in summary["results"]:
            errors = v.validate_payload(res, "result", SCHEMA_DIR)
            self.assertEqual(errors, [], f"result {res['result_id']} invalid: {errors}")

    def test_measured_manifest_declares_measured_providers(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-measured-manifest-")
        config = rn.RunConfig(
            schema_dir=SCHEMA_DIR, scenarios_dir=SCENARIOS_DIR, out_dir=out_dir,
            providers=["lexical_baseline"], unavailable=set(),
            repetitions=1, seed=7, mode="measured", measured={"lexical_baseline"},
        )
        summary = rn.run_dry_run(config)
        self.assertEqual(summary["manifest"]["run"]["measured_providers"],
                         ["lexical_baseline"])
        errors = v.validate_payload(summary["manifest"], "run_manifest", SCHEMA_DIR)
        self.assertEqual(errors, [], f"manifest invalid: {errors}")

    def test_measured_manifest_id_uses_measured_prefix(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-measured-prefix-")
        config = rn.RunConfig(
            schema_dir=SCHEMA_DIR, scenarios_dir=SCENARIOS_DIR, out_dir=out_dir,
            providers=["lexical_baseline"], unavailable=set(),
            repetitions=1, seed=7, mode="measured", measured={"lexical_baseline"},
        )
        summary = rn.run_dry_run(config)
        self.assertTrue(summary["manifest"]["manifest_id"].startswith("measured-"),
                        f"measured manifest_id should use 'measured-' prefix, got "
                        f"{summary['manifest']['manifest_id']!r}")

    def test_unknown_measured_provider_raises(self):
        out_dir = tempfile.mkdtemp(prefix="hmem-measured-unknown-")
        config = rn.RunConfig(
            schema_dir=SCHEMA_DIR, scenarios_dir=SCENARIOS_DIR, out_dir=out_dir,
            providers=["hindsight"], unavailable=set(),
            repetitions=1, seed=7, mode="measured", measured={"hindsight"},
        )
        with self.assertRaises(ValueError):
            rn.run_dry_run(config)

    def test_measured_registry_lists_lexical_baseline(self):
        reg = ad.measured_registry()
        self.assertIn("lexical_baseline", reg)
        self.assertTrue(reg["lexical_baseline"].measured)


if __name__ == "__main__":
    unittest.main()
