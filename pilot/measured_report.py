"""Cross-run measured baseline reporting for the hmem pilot.

Aggregates N isolated measured runs (each: manifest.json + results/*.json
produced by the measured lexical baseline) into a category-first baseline
report with per-category mean and population std across the runs (variance),
provenance counts, and explicit limitations. It clearly separates measured
lexical results from simulated adapter outputs: the report's provenance
section counts both kinds, and the limitations never claim simulated results
were measured.

CLI:  python -m pilot.measured_report --runs <dir|dir1,dir2> --out <dir>
"""
import argparse
import datetime
import json
import os
import statistics

from . import PILOT_VERSION
from . import validate as v

OUTCOMES = ("ok", "failure", "unsupported", "setup_failed", "skipped")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _non_none(values):
    return [x for x in values if x is not None]


def _mean(values):
    vals = _non_none(values)
    return round(statistics.fmean(vals), 4) if vals else None


def _std(values):
    vals = _non_none(values)
    if len(vals) < 2:
        return 0.0
    return round(statistics.pstdev(vals), 4)


def _fmt(value, ndigits=3):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{ndigits}f}"
    return str(value)


def load_run(run_dir, schema_dir=None):
    """Load and schema-validate one isolated run directory.

    Returns {"run_dir", "manifest", "results", "issues"}; issues lists every
    schema/consistency problem found so aggregation never silently ingests
    invalid payloads.
    """
    schema_dir = schema_dir or v.DEFAULT_SCHEMA_DIR
    issues = []
    manifest = None
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        issues.append(f"{run_dir}: manifest.json missing")
    else:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        errors = v.validate_payload(manifest, "run_manifest", schema_dir)
        if errors:
            issues.append(f"{run_dir}: manifest schema errors: {errors}")

    results = []
    results_dir = os.path.join(run_dir, "results")
    if os.path.isdir(results_dir):
        for name in sorted(os.listdir(results_dir)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(results_dir, name)
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            errors = v.validate_payload(doc, "result", schema_dir)
            if errors:
                issues.append(f"{run_dir}/{name}: schema errors: {errors}")
            results.append(doc)
    return {"run_dir": run_dir, "manifest": manifest, "results": results,
            "issues": issues}


def discover_runs(paths):
    """Expand each path: a run dir (contains manifest.json) or a parent dir
    whose immediate children are run dirs. Returns deduplicated, sorted list.
    """
    out = []
    for path in paths:
        if os.path.isfile(os.path.join(path, "manifest.json")):
            out.append(path)
        elif os.path.isdir(path):
            for child in sorted(os.listdir(path)):
                full = os.path.join(path, child)
                if os.path.isfile(os.path.join(full, "manifest.json")):
                    out.append(full)
    seen, dedup = set(), []
    for path in out:
        real = os.path.realpath(path)
        if real not in seen:
            seen.add(real)
            dedup.append(path)
    return dedup


def _run_category_stats(results):
    """Per-run aggregate over one category's results."""
    ok = [r for r in results if r["outcome"] == "ok"]
    return {
        "n": len(results),
        "ok": len(ok),
        "failures": sum(1 for r in results if r["outcome"] == "failure"),
        "unsupported": sum(1 for r in results if r["outcome"] == "unsupported"),
        "correctness_mean": _mean([r["scores"]["correctness"] for r in ok]),
        "latency_p50_ms": _mean([r["measurements"]["latency_ms"]["p50"] for r in ok]),
        "latency_p95_ms": _mean([r["measurements"]["latency_ms"]["p95"] for r in ok]),
        "tokens_retrieved_mean": _mean(
            [r["measurements"]["tokens"]["retrieved"] for r in ok]),
        "measured": sum(1 for r in results if r["measurement_kind"] == "measured"),
        "simulated": sum(1 for r in results if r["measurement_kind"] == "simulated"),
    }


def aggregate_runs(run_dirs, schema_dir=None):
    """Category-first aggregation across N isolated measured runs.

    Returns the canonical machine-readable baseline report JSON: per-run and
    per-category stats, cross-run mean/std (variance), provenance counts,
    totals, and limitations.
    """
    loaded = [load_run(d, schema_dir) for d in run_dirs]
    issues = [issue for run in loaded for issue in run["issues"]]
    all_results = [r for run in loaded for r in run["results"]]

    measured_count = sum(1 for r in all_results
                         if r["measurement_kind"] == "measured")
    simulated_count = sum(1 for r in all_results
                          if r["measurement_kind"] == "simulated")

    per_run, categories = [], {}
    for run in loaded:
        run_summary = {
            "run_dir": run["run_dir"],
            "manifest_id": (run["manifest"] or {}).get("manifest_id"),
            "n_results": len(run["results"]),
            "categories": {},
        }
        by_cat = {}
        for r in run["results"]:
            by_cat.setdefault(r["category"], []).append(r)
        for cat, res in sorted(by_cat.items()):
            run_summary["categories"][cat] = _run_category_stats(res)
            categories.setdefault(cat, []).append(run_summary["categories"][cat])
        per_run.append(run_summary)

    category_stats = {}
    for cat, run_stats in sorted(categories.items()):
        correctness = _non_none([s["correctness_mean"] for s in run_stats])
        l50 = _non_none([s["latency_p50_ms"] for s in run_stats])
        l95 = _non_none([s["latency_p95_ms"] for s in run_stats])
        category_stats[cat] = {
            "runs": len(run_stats),
            "n_total": sum(s["n"] for s in run_stats),
            "failures_total": sum(s["failures"] for s in run_stats),
            "unsupported_total": sum(s["unsupported"] for s in run_stats),
            "correctness_mean_across_runs": _mean(correctness),
            "correctness_std_across_runs": _std(correctness),
            "correctness_min": round(min(correctness), 4) if correctness else None,
            "correctness_max": round(max(correctness), 4) if correctness else None,
            "latency_p50_mean_across_runs": _mean(l50),
            "latency_p50_std_across_runs": _std(l50),
            "latency_p95_mean_across_runs": _mean(l95),
            "latency_p95_std_across_runs": _std(l95),
            "tokens_retrieved_mean_across_runs": _mean(
                _non_none([s["tokens_retrieved_mean"] for s in run_stats])),
        }

    cross_category_means = _non_none(
        [c["correctness_mean_across_runs"] for c in category_stats.values()])
    return {
        "report_version": PILOT_VERSION,
        "generated_iso": _now_iso(),
        "baseline": "measured-okapi-bm25-lexical",
        "engine": "pure-python-okapi-bm25 (k1=1.2, b=0.75), provider-independent",
        "runs": [{"run_dir": r["run_dir"], "manifest_id": r["manifest_id"],
                  "n_results": r["n_results"]} for r in per_run],
        "totals": {
            "runs": len(loaded),
            "results": len(all_results),
            "measured": measured_count,
            "simulated": simulated_count,
            "failures": sum(1 for r in all_results if r["outcome"] == "failure"),
            "unsupported": sum(1 for r in all_results if r["outcome"] == "unsupported"),
        },
        "provenance_counts": {"measured": measured_count,
                              "simulated": simulated_count},
        "categories": category_stats,
        "per_run": per_run,
        "variance": {
            "note": "Population std across the N isolated runs. Correctness is "
                    "deterministic (expected ~0 across runs); latency/token/"
                    "resource fields vary with machine load and are the "
                    "meaningful cross-run variance.",
            "overall_correctness_mean_across_runs": _mean(cross_category_means),
            "overall_correctness_std_across_runs": _std(cross_category_means),
            "categories": {
                cat: {"correctness_std_across_runs": c["correctness_std_across_runs"],
                      "latency_p50_std_across_runs": c["latency_p50_std_across_runs"]}
                for cat, c in category_stats.items()
            },
        },
        "issues": issues,
        "limitations": [
            "Measured lexical baseline: results were produced by executing the "
            "real in-process pure-Python Okapi BM25 ranker (BM25Index, "
            "k1=1.2, b=0.75) over each scenario's history; "
            "measurement_kind=measured / provenance=hmem-measured only where "
            "that real path executed.",
            "The lexical baseline is intentionally naive: no deletion, no "
            "profile/host boundaries, no trust filtering, no persistence, no "
            "semantic understanding. Scores measure lexical overlap only.",
            "Correctness is deterministic (identical scenario inputs produce "
            "identical scores), so cross-run correctness variance is expected "
            "to be ~0; cross-run variance in latency/tokens/resources is the "
            "real measured signal.",
            "Latency samples are in-process BM25 timings (milliseconds); they "
            "exclude network and real-storage effects and are not comparable "
            "across machines.",
            "Token counts are whitespace estimates (env.estimate_tokens), not "
            "provider tokenizer output.",
            "Resource counters are process-wide best-effort; system-wide "
            "counters may be None on machines without psutil.",
            "Simulated adapter results (hermes_memory/hindsight/mnemosyne "
            "stubs, measurement_kind=simulated / provenance=inferred) are "
            "excluded from this measured baseline; see the dry-run "
            "integration report for simulated coverage. Simulated results are "
            "never relabeled as measured.",
        ],
    }


def _render_markdown(report_json):
    t = report_json["totals"]
    lines = [
        "# hmem Measured Lexical Baseline — Category-First Report",
        "",
        f"- **Baseline:** {report_json['baseline']}",
        f"- **Engine:** {report_json['engine']}",
        f"- **Generated:** {report_json['generated_iso']}",
        f"- **Runs:** {t['runs']} isolated run(s)  |  **Results:** {t['results']}",
        f"- **Provenance:** {t['measured']} measured (hmem-measured), "
        f"{t['simulated']} simulated (never relabeled)",
        f"- **Failures:** {t['failures']}  |  **Unsupported:** {t['unsupported']}",
        "",
        "## Runs",
        "",
        "| run dir | manifest | results |",
        "|---|---|---|",
    ]
    for run in report_json["runs"]:
        lines.append(f"| {run['run_dir']} | `{run['manifest_id']}` | "
                     f"{run['n_results']} |")
    lines += ["", "## Category Results (across runs)", "",
              "| category | runs | n | correctness mean | correctness std | "
              "min | max | p50 ms mean | p50 ms std | p95 ms mean | failures |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for cat, st in sorted(report_json["categories"].items()):
        lines.append(
            f"| {cat} | {st['runs']} | {st['n_total']} | "
            f"{_fmt(st['correctness_mean_across_runs'])} | "
            f"{_fmt(st['correctness_std_across_runs'])} | "
            f"{_fmt(st['correctness_min'])} | {_fmt(st['correctness_max'])} | "
            f"{_fmt(st['latency_p50_mean_across_runs'])} | "
            f"{_fmt(st['latency_p50_std_across_runs'])} | "
            f"{_fmt(st['latency_p95_mean_across_runs'])} | "
            f"{st['failures_total']} |")
    lines += ["", "## Per-Run Detail", ""]
    for run in report_json["per_run"]:
        lines.append(f"### {run['manifest_id']}  ({run['run_dir']})")
        lines.append("")
        lines.append("| category | n | ok | correctness | p50 ms | p95 ms | "
                     "measured | simulated | failures |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for cat, st in sorted(run["categories"].items()):
            lines.append(
                f"| {cat} | {st['n']} | {st['ok']} | {_fmt(st['correctness_mean'])} | "
                f"{_fmt(st['latency_p50_ms'])} | {_fmt(st['latency_p95_ms'])} | "
                f"{st['measured']} | {st['simulated']} | {st['failures']} |")
        lines.append("")
    v = report_json["variance"]
    lines += [
        "## Variance",
        "",
        f"- Overall correctness mean across runs: "
        f"{_fmt(v['overall_correctness_mean_across_runs'])}",
        f"- Overall correctness std across runs: "
        f"{_fmt(v['overall_correctness_std_across_runs'])}",
        f"- {v['note']}",
        "",
        "## Limitations",
        "",
    ]
    for lim in report_json["limitations"]:
        lines.append(f"- {lim}")
    lines.append("")
    if report_json["issues"]:
        lines += ["## Load/Validation Issues", ""]
        for issue in report_json["issues"]:
            lines.append(f"- {issue}")
        lines.append("")
    return "\n".join(lines)


def generate_measured_report(run_dirs, schema_dir=None):
    """Category-first measured baseline report over N isolated runs.

    Returns {"report_md": str, "report_json": dict}; the JSON is canonical,
    the markdown a human-readable rendering.
    """
    report_json = aggregate_runs(run_dirs, schema_dir)
    return {"report_md": _render_markdown(report_json), "report_json": report_json}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="hmem-measured-report",
        description="Aggregate N isolated measured lexical baseline runs into "
                    "a category-first baseline report with cross-run variance.",
    )
    parser.add_argument("--runs", required=True,
                        help="comma-separated run dirs, or a parent directory "
                             "whose immediate children are run dirs")
    parser.add_argument("--out", default="pilot-out/measured",
                        help="output directory for report.md/report.json")
    parser.add_argument("--schema-dir", default=v.DEFAULT_SCHEMA_DIR,
                        help="directory with versioned *.schema.json documents")
    args = parser.parse_args(argv)

    run_dirs = discover_runs([p.strip() for p in args.runs.split(",") if p.strip()])
    if not run_dirs:
        print(f"no run directories found under {args.runs!r}", file=__import__("sys").stderr)
        return 1
    report = generate_measured_report(run_dirs, args.schema_dir)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report["report_md"])
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report["report_json"], fh, indent=2)
    rj = report["report_json"]
    print(f"measured baseline report: {args.out}/report.md")
    print(f"runs: {rj['totals']['runs']}  results: {rj['totals']['results']}  "
          f"measured: {rj['totals']['measured']}  simulated: "
          f"{rj['totals']['simulated']}")
    if rj["issues"]:
        print(f"{len(rj['issues'])} load/validation issue(s):")
        for issue in rj["issues"]:
            print(f"  {issue}")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
