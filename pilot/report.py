"""Category-first aggregate reporting for the hmem pilot.

Aggregates raw result payloads per capability category (never collapsing to a
single ranking scale), separates claim provenance / measurement kind from
provider outcomes, surfaces unavailable providers, and reports repeated-run
variance and explicit limitations. Emits both a human-readable markdown report
and a machine-readable JSON report.
"""
import datetime
import statistics

from . import PILOT_VERSION

OUTCOMES = ("ok", "failure", "unsupported", "setup_failed", "skipped")


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _non_none(values):
    return [v for v in values if v is not None]


def _mean(values):
    vals = _non_none(values)
    return round(statistics.fmean(vals), 4) if vals else None


def _std(values):
    vals = _non_none(values)
    if len(vals) < 2:
        return 0.0
    return round(statistics.pstdev(vals), 4)


def _rate(values):
    """Mean of binary (0/1) values with no-None-safe denominator; None if none."""
    vals = _non_none(values)
    return round(sum(vals) / len(vals), 4) if vals else None


def _fmt(value, ndigits=3):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{ndigits}f}"
    return str(value)


def _provider_stats(results):
    """Per-provider aggregate stats over a list of results (one category)."""
    stats = {"n": len(results)}
    ok = [r for r in results if r["outcome"] == "ok"]
    stats["failures"] = sum(1 for r in results if r["outcome"] == "failure")
    stats["unsupported"] = sum(1 for r in results if r["outcome"] == "unsupported")
    stats["setup_failed"] = sum(1 for r in results if r["outcome"] == "setup_failed")

    correctness = [r["scores"]["correctness"] for r in ok]
    stats["correctness_mean"] = _mean(correctness)
    stats["correctness_std"] = _std(correctness)
    stats["evidence_precision_mean"] = _mean(
        [r["scores"]["evidence_precision"] for r in ok])
    stats["evidence_recall_mean"] = _mean(
        [r["scores"]["evidence_recall"] for r in ok])
    stats["stale_reuse_rate"] = _rate([r["scores"]["stale_reuse"] for r in ok])
    stats["leakage_rate"] = _rate([r["scores"]["leakage"] for r in ok])
    stats["abstention_correct_rate"] = _rate(
        [r["scores"]["abstention_correct"] for r in ok])
    stats["poisoning_success_rate"] = _rate(
        [r["scores"]["poisoning_success"] for r in ok])
    stats["synthesis_rate"] = _rate([r["scores"]["synthesis"] for r in ok])
    stats["recovery_success_rate"] = _rate(
        [r["scores"]["recovery_success"] for r in ok])
    stats["setup_success_rate"] = _rate([r["scores"]["setup_success"] for r in ok])

    lat = _non_none([r["measurements"]["latency_ms"]["p50"] for r in ok])
    stats["latency_p50_ms"] = _mean(lat)
    stats["latency_p95_ms"] = _mean(
        _non_none([r["measurements"]["latency_ms"]["p95"] for r in ok]))
    return stats


def _build_json(manifest, results, validation_errors, schema_errors):
    totals = {o: sum(1 for r in results if r["outcome"] == o) for o in OUTCOMES}
    totals["scenarios"] = manifest["scenario_set"]["scenario_count"]
    totals["results"] = len(results)
    totals["providers"] = len({r["provider_id"] for r in results})

    provenance_counts = {"simulated": 0, "measured": 0, "vendor_reported": 0}
    for r in results:
        kind = r["measurement_kind"]
        if kind == "simulated":
            provenance_counts["simulated"] += 1
        elif kind == "measured":
            provenance_counts["measured"] += 1
        if r["vendor"]["vendor_reported"]:
            provenance_counts["vendor_reported"] += 1

    categories = {}
    for r in results:
        cat = r["category"]
        categories.setdefault(cat, {}).setdefault("_results", []).append(r)
    for cat, bucket in categories.items():
        res = bucket.pop("_results")
        providers = {}
        for pid in sorted({r["provider_id"] for r in res}):
            providers[pid] = _provider_stats([r for r in res if r["provider_id"] == pid])
        categories[cat] = {
            "n": len(res),
            "providers": providers,
            "correctness_mean": _mean([r["scores"]["correctness"]
                                       for r in res if r["outcome"] == "ok"]),
        }

    all_ok = [r["scores"]["correctness"] for r in results if r["outcome"] == "ok"]
    variance = {
        "overall_correctness_std": _std(all_ok),
        "per_provider": {
            pid: _std([r["scores"]["correctness"] for r in results
                       if r["provider_id"] == pid and r["outcome"] == "ok"])
            for pid in sorted({r["provider_id"] for r in results})
        },
        "note": "Population std of correctness over repeated deterministic runs; "
                "stubs are deterministic so variance should be ~0.",
    }

    limitations = [
        "Dry-run mode: every result is produced by a deterministic provider "
        "adapter STUB (measurement_kind=simulated, provenance=inferred). No real "
        "provider was invoked and no secrets were required.",
        "Adapter stubs model documented provider policies (newest-wins, "
        "forgetting, synthesis, premise rejection, boundaries, trust filtering, "
        "persistence); they are simulations, not measurements of the real "
        "providers, and must not be promoted to hmem-measured evidence.",
        "Latency samples are in-process stub timings (milliseconds); they do not "
        "include network or real-storage effects and are not comparable across "
        "machines.",
        "Token counts are whitespace estimates (env.estimate_tokens), not "
        "provider tokenizer output.",
        "Resource snapshots are process-wide best-effort; system-wide counters "
        "may be unavailable (None) on machines without psutil.",
        "Scoring is deterministic lexical/token matching against the answer key; "
        "it does not use an LLM judge, so free-form paraphrase beyond token "
        "overlap is not rewarded.",
        "Scenario coverage: all fixtures are synthetic, reviewed, and dev/held-out "
        "splits are declared; held-out cases are excluded from the development "
        "loop but published because they are synthetic (PRIV-08).",
    ]
    if totals["unsupported"] or totals["setup_failed"]:
        limitations.append(
            f"{totals['unsupported']} result(s) reported unsupported and "
            f"{totals['setup_failed']} setup-failed: unavailable providers are "
            "recorded, never fabricated or discarded.")
    if schema_errors:
        limitations.append(
            f"Schema validation reported errors in {len(schema_errors)} "
            "schema document(s); results are validated against whatever "
            "documents were loadable.")

    return {
        "report_version": PILOT_VERSION,
        "manifest_id": manifest["manifest_id"],
        "generated_iso": _now_iso(),
        "mode": manifest["mode"],
        "totals": totals,
        "provenance_counts": provenance_counts,
        "unavailable": totals["unsupported"] + totals["setup_failed"],
        "categories": categories,
        "variance": variance,
        "limitations": limitations,
        "validation_errors": validation_errors,
        "schema_errors": schema_errors,
    }


def _render_markdown(manifest, report_json):
    t = report_json["totals"]
    lines = [
        "# hmem Pilot Report",
        "",
        f"- **Manifest:** `{report_json['manifest_id']}`",
        f"- **Mode:** {report_json['mode']} (no real providers or secrets)",
        f"- **Generated:** {report_json['generated_iso']}",
        f"- **Scenarios:** {t['scenarios']}  |  **Results:** {t['results']}  |  "
        f"**Providers:** {t['providers']}",
        f"- **Outcomes:** {t['ok']} ok, {t['failure']} failure, "
        f"{t['unsupported']} unsupported, {t['setup_failed']} setup_failed",
        "",
        "## Provenance",
        "",
        f"- Simulated (stub) results: {report_json['provenance_counts']['simulated']}",
        f"- Measured (real provider) results: {report_json['provenance_counts']['measured']}",
        f"- Vendor-reported labels: {report_json['provenance_counts']['vendor_reported']}",
        "",
        "Simulated stub results carry provenance=inferred and must never be "
        "promoted to hmem-measured evidence.",
        "",
        "## Category Results",
        "",
    ]
    if not report_json["categories"]:
        lines.append("No results produced.")
    for cat, bucket in sorted(report_json["categories"].items()):
        lines.append(f"### {cat}  (n={bucket['n']}, correctness mean="
                     f"{_fmt(bucket['correctness_mean'])})")
        lines.append("")
        lines.append("| provider | n | correctness | std | ev-precision | "
                     "ev-recall | p50 ms | p95 ms | failures | unsupported |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for pid, st in sorted(bucket["providers"].items()):
            lines.append(
                f"| {pid} | {st['n']} | {_fmt(st['correctness_mean'])} | "
                f"{_fmt(st['correctness_std'])} | "
                f"{_fmt(st['evidence_precision_mean'])} | "
                f"{_fmt(st['evidence_recall_mean'])} | "
                f"{_fmt(st['latency_p50_ms'])} | {_fmt(st['latency_p95_ms'])} | "
                f"{st['failures']} | {st['unsupported']} |")
        lines.append("")

    per_provider = ", ".join(
        f"{k}={_fmt(v)}" for k, v in sorted(report_json["variance"]["per_provider"].items()))
    lines += [
        "## Variance",
        "",
        f"- Overall correctness std (population): "
        f"{_fmt(report_json['variance']['overall_correctness_std'])}",
        f"- Per provider: {per_provider}",
        f"- {report_json['variance']['note']}",
        "",
        "## Limitations",
        "",
    ]
    for lim in report_json["limitations"]:
        lines.append(f"- {lim}")
    lines.append("")

    if report_json["schema_errors"]:
        lines += ["## Schema Errors", ""]
        for doc, errs in report_json["schema_errors"].items():
            lines.append(f"- {doc}: {errs}")
        lines.append("")
    if report_json["validation_errors"]:
        lines += ["## Validation Errors", ""]
        for path, errs in report_json["validation_errors"].items():
            lines.append(f"- `{path}`: {errs}")
        lines.append("")
    return "\n".join(lines)


def generate_report(manifest, results, validation_errors=None,
                    schema_errors=None):
    """Category-first aggregate report.

    Returns {"report_md": str, "report_json": dict}. The JSON is the canonical
    machine-readable artifact; the markdown is a human-readable rendering that
    never merges categories into one ranking scale.
    """
    report_json = _build_json(manifest, results,
                              validation_errors or {}, schema_errors or {})
    report_md = _render_markdown(manifest, report_json)
    return {"report_md": report_md, "report_json": report_json}
