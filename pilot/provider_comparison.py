"""Measured provider comparison reporting for the hmem pilot."""

import argparse
import datetime
import json
import os
import statistics

from . import PILOT_VERSION, PROVIDER_IDS
from . import measured_report as mr
from . import validate as v


MEASURED_PROVIDER_LABELS = {
    "lexical_baseline": "BM25 lexical baseline",
    "hermes_memory": "Hermes built-in memory",
}


def _mean(values):
    values = [value for value in values if value is not None]
    return round(statistics.fmean(values), 4) if values else None


def _std(values):
    values = [value for value in values if value is not None]
    return round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0


def _fmt(value, digits=3):
    return "n/a" if value is None else f"{value:.{digits}f}"


def _run_stats(results):
    ok = [result for result in results if result["outcome"] == "ok"]
    return {
        "n": len(results),
        "ok": len(ok),
        "failures": sum(result["outcome"] == "failure" for result in results),
        "unsupported": sum(result["outcome"] == "unsupported" for result in results),
        "correctness": _mean([result["scores"]["correctness"] for result in ok]),
        "latency_p50_ms": _mean(
            [result["measurements"]["latency_ms"]["p50"] for result in ok]
        ),
        "latency_p95_ms": _mean(
            [result["measurements"]["latency_ms"]["p95"] for result in ok]
        ),
        "tokens_retrieved": _mean(
            [result["measurements"]["tokens"]["retrieved"] for result in ok]
        ),
    }


def aggregate_comparison(run_dirs, schema_dir=None):
    """Aggregate measured runs by provider and category.

    Every included result must be genuinely measured. Simulated results are
    reported as validation issues and are excluded from provider scores.
    """
    loaded = [mr.load_run(run_dir, schema_dir) for run_dir in run_dirs]
    issues = [issue for run in loaded for issue in run["issues"]]
    by_provider = {}
    run_summaries = []

    for run in loaded:
        manifest = run["manifest"] or {}
        measured_declared = set(manifest.get("run", {}).get("measured_providers", []))
        grouped = {}
        for result in run["results"]:
            provider = result["provider_id"]
            if (
                result["measurement_kind"] != "measured"
                or result["provenance"] != "hmem-measured"
                or provider not in measured_declared
            ):
                issues.append(
                    f"{run['run_dir']}: excluded non-measured result "
                    f"{result['result_id']}"
                )
                continue
            grouped.setdefault(provider, {}).setdefault(result["category"], []).append(result)

        run_summary = {
            "run_dir": run["run_dir"],
            "manifest_id": manifest.get("manifest_id"),
            "providers": {},
        }
        for provider, categories in sorted(grouped.items()):
            run_summary["providers"][provider] = {}
            for category, results in sorted(categories.items()):
                stats = _run_stats(results)
                run_summary["providers"][provider][category] = stats
                by_provider.setdefault(provider, {}).setdefault(category, []).append(stats)
        run_summaries.append(run_summary)

    providers = {}
    for provider, categories in sorted(by_provider.items()):
        category_summary = {}
        total_results = 0
        total_failures = 0
        run_overall = []
        for category, stats in sorted(categories.items()):
            correctness = [entry["correctness"] for entry in stats]
            latency_p50 = [entry["latency_p50_ms"] for entry in stats]
            latency_p95 = [entry["latency_p95_ms"] for entry in stats]
            category_summary[category] = {
                "runs": len(stats),
                "n_total": sum(entry["n"] for entry in stats),
                "failures_total": sum(entry["failures"] for entry in stats),
                "correctness_mean": _mean(correctness),
                "correctness_std": _std(correctness),
                "latency_p50_ms_mean": _mean(latency_p50),
                "latency_p50_ms_std": _std(latency_p50),
                "latency_p95_ms_mean": _mean(latency_p95),
                "tokens_retrieved_mean": _mean(
                    [entry["tokens_retrieved"] for entry in stats]
                ),
            }
            total_results += category_summary[category]["n_total"]
            total_failures += category_summary[category]["failures_total"]
        for run in run_summaries:
            run_categories = run["providers"].get(provider, {})
            value = _mean([entry["correctness"] for entry in run_categories.values()])
            if value is not None:
                run_overall.append(value)
        providers[provider] = {
            "label": MEASURED_PROVIDER_LABELS.get(provider, provider),
            "runs": len(run_overall),
            "results": total_results,
            "failures": total_failures,
            "overall_correctness_mean": _mean(run_overall),
            "overall_correctness_std": _std(run_overall),
            "categories": category_summary,
        }

    unavailable = [
        {
            "provider_id": provider,
            "status": "not_measured",
            "reason": "no real measured adapter is registered in hmem",
        }
        for provider in PROVIDER_IDS
        if provider not in providers
    ]

    return {
        "report_version": PILOT_VERSION,
        "generated_iso": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "comparison": "measured-provider-comparison",
        "runs": run_summaries,
        "providers": providers,
        "not_measured": unavailable,
        "totals": {
            "runs": len(loaded),
            "providers_measured": len(providers),
            "results": sum(provider["results"] for provider in providers.values()),
            "failures": sum(provider["failures"] for provider in providers.values()),
        },
        "issues": issues,
        "limitations": [
            "Only providers with real measured adapters are scored. Simulated stubs are excluded.",
            "Hermes memory here is the deterministic bundled MEMORY.md adapter, not an LLM-assisted agent session.",
            "Correctness is deterministic for fixed scenarios; latency varies with runner load.",
            "Hindsight and Mnemosyne are not compared until real measured adapters are implemented.",
        ],
    }


def render_markdown(report):
    totals = report["totals"]
    lines = [
        "# hmem Measured Provider Comparison",
        "",
        f"- Generated: {report['generated_iso']}",
        f"- Isolated runs: {totals['runs']}",
        f"- Measured providers: {totals['providers_measured']}",
        f"- Measured result documents: {totals['results']}",
        f"- Failures: {totals['failures']}",
        "",
        "## Overall Comparison",
        "",
        "| provider | runs | results | correctness mean | correctness std | failures |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for provider, data in sorted(report["providers"].items()):
        lines.append(
            f"| {data['label']} (`{provider}`) | {data['runs']} | {data['results']} | "
            f"{_fmt(data['overall_correctness_mean'])} | "
            f"{_fmt(data['overall_correctness_std'])} | {data['failures']} |"
        )

    categories = sorted(
        {category for data in report["providers"].values() for category in data["categories"]}
    )
    lines += ["", "## Category Comparison", ""]
    for category in categories:
        lines += [
            f"### {category}",
            "",
            "| provider | correctness | p50 ms | p95 ms | retrieved tokens | n |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for provider, data in sorted(report["providers"].items()):
            stats = data["categories"].get(category)
            if not stats:
                continue
            lines.append(
                f"| {data['label']} | {_fmt(stats['correctness_mean'])} | "
                f"{_fmt(stats['latency_p50_ms_mean'])} | "
                f"{_fmt(stats['latency_p95_ms_mean'])} | "
                f"{_fmt(stats['tokens_retrieved_mean'])} | {stats['n_total']} |"
            )
        lines.append("")

    lines += ["## Providers Not Measured", ""]
    for entry in report["not_measured"]:
        lines.append(f"- `{entry['provider_id']}`: {entry['reason']}")
    lines += ["", "## Limitations", ""]
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    if report["issues"]:
        lines += ["", "## Validation Issues", ""]
        lines.extend(f"- {issue}" for issue in report["issues"])
    lines.append("")
    return "\n".join(lines)


def generate_comparison(run_dirs, schema_dir=None):
    report = aggregate_comparison(run_dirs, schema_dir)
    return {"report_json": report, "report_md": render_markdown(report)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hmem-provider-comparison")
    parser.add_argument("--runs", required=True)
    parser.add_argument("--out", default="pilot-out/provider-comparison")
    parser.add_argument("--schema-dir", default=v.DEFAULT_SCHEMA_DIR)
    args = parser.parse_args(argv)

    run_dirs = mr.discover_runs(
        [path.strip() for path in args.runs.split(",") if path.strip()]
    )
    if not run_dirs:
        parser.error("no run directories found")
    generated = generate_comparison(run_dirs, args.schema_dir)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as handle:
        json.dump(generated["report_json"], handle, indent=2)
        handle.write("\n")
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as handle:
        handle.write(generated["report_md"])
    totals = generated["report_json"]["totals"]
    print(
        f"provider comparison: {totals['providers_measured']} providers, "
        f"{totals['runs']} runs, {totals['results']} results"
    )
    return 1 if generated["report_json"]["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
