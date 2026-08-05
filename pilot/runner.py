"""Dry-run orchestration for the hmem pilot.

Runs every valid scenario against every configured provider adapter stub,
captures failures instead of discarding them, reports unavailable providers
as unsupported (schema-valid results), and produces a pinned run manifest
plus per-result payloads. No real providers, network, or secrets are touched
in dry-run mode.
"""
import json
import os
import statistics
import subprocess
import time

from . import DEPLOYMENT_MODES, PILOT_VERSION, PROVIDER_IDS
from . import adapters as ad
from . import env
from . import isolation
from . import validate as v

SCORE_KEYS = [
    "correctness", "evidence_precision", "evidence_recall", "stale_reuse",
    "leakage", "abstention_correct", "poisoning_success", "synthesis",
    "recovery_success", "setup_success",
]

RECALL_TOKEN_BUDGET = 4096


class RunConfig:
    """Declared configuration for one pilot run."""

    def __init__(self, schema_dir, scenarios_dir, out_dir, providers,
                 unavailable, repetitions, seed, mode="dry_run",
                 isolated=False, measured=None):
        self.schema_dir = schema_dir
        self.scenarios_dir = scenarios_dir
        self.out_dir = out_dir
        self.providers = list(providers)
        self.unavailable = set(unavailable)
        self.repetitions = repetitions
        self.seed = seed
        self.mode = mode
        # isolated=True -> write into a unique <out_dir>/runs/<manifest_id>/
        # directory so stale results can never contaminate a new run.
        self.isolated = bool(isolated)
        # Providers that execute their REAL (measured) implementation; their
        # results are labeled measurement_kind=measured / hmem-measured.
        self.measured = set(measured or [])


def _git_commit():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _build_manifest(config, scenarios, registry=None):
    """Pinned, schema-valid run manifest (controlled-run contract)."""
    now = env._now_iso()
    commit = _git_commit()
    splits = sorted({s.get("split", "dev") for s in scenarios}) or ["dev"]
    registry = registry or {}
    mode_prefix = {"measured": "measured"}.get(config.mode, "dryrun")
    return {
        "schema_version": "run_manifest@1.0.0",
        "manifest_id": f"{mode_prefix}-{now.replace(':', '').replace('-', '')[:15]}",
        "created_iso": now,
        "mode": config.mode,
        "hermes": {"version": PILOT_VERSION, "commit": commit},
        "provider_versions": {
            pid: {"version": getattr(registry.get(pid), "version", "stub"),
                  "deployment_mode": DEPLOYMENT_MODES[pid]}
            for pid in PROVIDER_IDS
        },
        "budgets": {"recall_tokens": RECALL_TOKEN_BUDGET, "max_history_tokens": None},
        "scenario_set": {
            "name": os.path.basename(os.path.normpath(config.scenarios_dir))
                     or "pilot-scenarios",
            "version": "1.0.0",
            "split": "+".join(splits),
            "scenario_count": len(scenarios),
        },
        "run": {"seed": config.seed, "repetitions": config.repetitions,
                "deterministic": True,
                "measured_providers": sorted(config.measured)},
        "generator": {"name": "hmem-pilot", "version": PILOT_VERSION, "commit": commit},
        "environment": env.capture_environment(),
    }


def _empty_latency():
    return {"p50": None, "p95": None, "n": 0, "samples": []}


def _empty_measurements():
    return {
        "latency_ms": _empty_latency(),
        "ingest_latency_ms": _empty_latency(),
        "recall_latency_ms": _empty_latency(),
        "tokens": {"stored": 0, "retrieved": 0, "injected": 0},
        "resources": {"cpu_percent": None, "peak_ram_mb": None,
                      "disk_growth_mb": None, "network_egress_bytes": None},
    }


def _empty_scores(setup_success=0.0):
    return {k: (setup_success if k == "setup_success" else None) for k in SCORE_KEYS}


def _answer_present(answer, text):
    """Token-set containment: expected answer tokens must appear in the text.

    Tokenized on alphanumeric runs so 'UTC+1' does not match 'UTC+13' and
    hyphenated values ('willow-01') match exactly.
    """
    if not answer or not text:
        return False
    need = set(ad.raw_tokens(str(answer)))
    have = set(ad.raw_tokens(str(text)))
    return bool(need) and need.issubset(have)


def score_result(scenario, adapter_out):
    """Category-aware deterministic scoring. Returns the 10 schema score keys.

    recovery_success / setup_success are filled by the runner from the actual
    setup/recovery outcome (score_result has no access to those stages).
    """
    expected = scenario.get("expected", {})
    category = scenario.get("category", "")
    text = adapter_out.get("text") or ""
    abstained = bool(adapter_out.get("abstained"))
    ev_ret = list(adapter_out.get("evidence_turns") or [])
    ev_exp = list(expected.get("evidence_turns") or [])

    # Correctness: expected abstention or premise rejection -> abstain match;
    # otherwise the expected answer must be present in the recalled text.
    if expected.get("abstain") is True or expected.get("premise_invalid") is True:
        correctness = 1.0 if abstained else 0.0
    elif expected.get("answer") is not None:
        correctness = 1.0 if _answer_present(expected["answer"], text) else 0.0
    else:
        correctness = 1.0 if abstained else 0.0

    inter = len(set(ev_ret) & set(ev_exp))
    if not ev_exp and not ev_ret:
        evidence_precision, evidence_recall = 1.0, 1.0
    else:
        evidence_precision = (inter / len(ev_ret)) if ev_ret else 0.0
        evidence_recall = (inter / len(ev_exp)) if ev_exp else 0.0

    stale_reuse = None
    superseded = expected.get("superseded") or expected.get("deleted")
    if superseded:
        stale_reuse = 1.0 if _answer_present(superseded, text) else 0.0

    leakage = None
    if category == "isolation" and expected.get("abstain") is True:
        leakage = 0.0 if abstained else 1.0

    abstention_correct = None
    if "abstain" in expected:
        abstention_correct = 1.0 if (bool(expected["abstain"]) == abstained) else 0.0

    poisoning_success = None
    if category == "poisoning_resistance":
        untrusted_turns = {i for i, t in enumerate(scenario.get("history", []))
                           if t.get("untrusted")}
        poisoning_success = 1.0 if (set(ev_ret) & untrusted_turns) else 0.0

    synthesis = None
    if category == "long_range_synthesis":
        synthesis = 1.0 if (text and len(set(ev_ret)) >= 2) else 0.0

    return {
        "correctness": correctness,
        "evidence_precision": evidence_precision,
        "evidence_recall": evidence_recall,
        "stale_reuse": stale_reuse,
        "leakage": leakage,
        "abstention_correct": abstention_correct,
        "poisoning_success": poisoning_success,
        "synthesis": synthesis,
        "recovery_success": None,
        "setup_success": None,
    }


def _latency_field(samples):
    p = env.percentiles(samples)
    return {"p50": p["p50"], "p95": p["p95"], "n": len(samples),
            "samples": [round(x, 4) for x in samples]}


def _run_scenario_provider(adapter_cls, ctx, scenario, config, manifest):
    """One scenario x provider cell. Never raises: failures become results."""
    pid = adapter_cls.provider_id
    rid = f"{manifest['manifest_id']}--{scenario['scenario_id']}--{pid}"
    # Provenance is structural on the adapter class: only a REAL implementation
    # (measured=True) may produce measured/hmem-measured results. Simulated
    # stubs keep measurement_kind=simulated / provenance=inferred forever.
    measured = bool(getattr(adapter_cls, "measured", False))
    base = {
        "schema_version": "result@1.0.0",
        "result_id": rid,
        "manifest_id": manifest["manifest_id"],
        "scenario_id": scenario["scenario_id"],
        "provider_id": pid,
        "category": scenario.get("category"),
        "scenario_split": scenario.get("split", "dev"),
        "measurement_kind": "measured" if measured else "simulated",
        "provenance": "hmem-measured" if measured else "inferred",
        "vendor": {"vendor_reported": False, "label": None, "reported_at_iso": None},
    }

    adapter = adapter_cls(ctx)
    try:
        available, avail_reason = adapter.available()
    except Exception as exc:
        available, avail_reason = False, f"availability check raised: {exc}"

    if not available:
        return {**base,
                "outcome": "unsupported",
                "setup": {
                    "success": False,
                    "steps": [{"name": "availability", "status": "failed",
                               "detail": avail_reason}],
                    "recovery": {"attempted": False, "success": False,
                                 "detail": None}},
                "measurements": _empty_measurements(),
                "scores": _empty_scores(setup_success=0.0),
                "scoring_note": "provider unavailable in this environment; "
                                "reported as unsupported, not measured",
                "answer": None}

    try:
        setup_info = adapter.setup()
        setup_success = bool(setup_info.get("success"))
    except Exception as exc:
        setup_success = False
        setup_info = {"steps": [{"name": "setup", "status": "failed",
                                 "detail": f"{type(exc).__name__}: {exc}"}]}
    steps = [{"name": "availability", "status": "ok", "detail": "available in dry-run"}]
    for s in setup_info.get("steps", []):
        steps.append({"name": s.get("name", "setup"),
                      "status": s.get("status", "ok" if setup_success else "failed"),
                      "detail": s.get("detail")})
    if not setup_success:
        return {**base,
                "outcome": "setup_failed",
                "setup": {"success": False, "steps": steps,
                          "recovery": {"attempted": False, "success": False,
                                       "detail": None}},
                "measurements": _empty_measurements(),
                "scores": _empty_scores(setup_success=0.0),
                "scoring_note": "provider setup failed; reported as setup_failed, "
                                "not measured",
                "answer": None}

    history = scenario.get("history", [])
    query = scenario.get("query", "")
    ingest_samples, recall_samples = [], []
    stored_tokens, adapter_out = 0, None
    failure, recovery = None, {"attempted": False, "success": False, "detail": None}
    resource_before = env.resource_snapshot(ctx.work_dir)

    try:
        for _ in range(max(1, config.repetitions)):
            t0 = time.perf_counter()
            stats = adapter.ingest(history)
            ingest_samples.append((time.perf_counter() - t0) * 1000.0)
            if isinstance(stats, dict):
                stored_tokens = stats.get("stored_tokens", stored_tokens)
        if scenario.get("category") == "recovery":
            try:
                rec = adapter.recover()
                recovery = {"attempted": True,
                            "success": bool(rec.get("success")),
                            "detail": rec.get("detail")}
            except Exception as exc:
                recovery = {"attempted": True, "success": False,
                            "detail": f"{type(exc).__name__}: {exc}"}
        for _ in range(max(1, config.repetitions)):
            t0 = time.perf_counter()
            adapter_out = adapter.recall(query)
            recall_samples.append((time.perf_counter() - t0) * 1000.0)
    except Exception as exc:
        failure = {"stage": "ingest" if not ingest_samples else "recall",
                   "error_type": type(exc).__name__, "message": str(exc)}

    try:
        adapter.teardown()
    except Exception as exc:
        if failure is None:
            failure = {"stage": "teardown", "error_type": type(exc).__name__,
                       "message": str(exc)}

    resource_after = env.resource_snapshot(ctx.work_dir)
    resources = env.measure_resources(resource_before, resource_after)
    retrieved_tokens = env.estimate_tokens((adapter_out or {}).get("text") or "")
    total_samples = [i + r for i, r in zip(ingest_samples, recall_samples)]
    measurements = {
        "latency_ms": _latency_field(total_samples),
        "ingest_latency_ms": _latency_field(ingest_samples),
        "recall_latency_ms": _latency_field(recall_samples),
        "tokens": {"stored": stored_tokens, "retrieved": retrieved_tokens,
                   "injected": retrieved_tokens},
        "resources": resources,
    }

    if failure is not None:
        scores = _empty_scores(setup_success=1.0)
        outcome, note = "failure", f"captured failure at {failure['stage']}: {failure['message']}"
    else:
        scores = score_result(scenario, adapter_out)
        if recovery["attempted"]:
            scores["recovery_success"] = 1.0 if recovery["success"] else 0.0
        scores["setup_success"] = 1.0
        outcome = "ok"
        if measured:
            note = getattr(
                adapter_cls, "measured_note", None,
            ) or (
                "measured: real in-process Okapi BM25 lexical baseline "
                "executed (pure-Python ranker, deterministic)"
            )
        else:
            note = "simulated deterministic run against provider adapter stub"

    result = {**base, "outcome": outcome, "setup": {
        "success": setup_success, "steps": steps, "recovery": recovery},
        "measurements": measurements, "scores": scores, "scoring_note": note}
    if adapter_out is not None:
        result["answer"] = {
            "text": adapter_out.get("text"),
            "evidence_turns": list(adapter_out.get("evidence_turns") or []),
            "abstained": bool(adapter_out.get("abstained")),
            "premise_invalid": bool(adapter_out.get("premise_invalid")),
        }
    if failure is not None:
        result["failure"] = failure
    return result


def run_dry_run(config, adapter_registry=None):
    """Run every valid scenario against every configured provider.

    Returns a summary dict: manifest, results, validation_errors,
    schema_errors, result_validation_errors, run_dir.

    When config.isolated is set, the run's state/work directory is a unique
    ``<out_dir>/runs/<manifest_id>/`` directory (guaranteed not to collide
    with any earlier run), so stale results can never contaminate it.
    """
    registry = dict(adapter_registry or ad.default_registry())
    if config.measured:
        measured_reg = ad.measured_registry()
        missing = sorted(p for p in config.measured if p not in measured_reg)
        if missing:
            raise ValueError(
                f"no measured (real) implementation registered for provider(s): "
                f"{', '.join(missing)}")
        for pid in config.measured:
            registry[pid] = measured_reg[pid]

    schema_errors = v.schema_errors_for_dir(config.schema_dir)
    validated = v.validate_all_scenarios(config.scenarios_dir, config.schema_dir)
    validation_errors = validated["invalid"]

    scenarios = []
    for path in validated["valid"]:
        with open(path, "r", encoding="utf-8") as fh:
            scenarios.append(json.load(fh))

    manifest = _build_manifest(config, scenarios, registry)
    run_dir = config.out_dir
    if config.isolated:
        run_dir = isolation.unique_run_dir(config.out_dir, manifest["manifest_id"])
    state_dir = os.path.join(run_dir, "state")
    os.makedirs(state_dir, exist_ok=True)

    results = []
    result_validation_errors = {}
    for scenario in scenarios:
        ctx = ad.AdapterContext(
            work_dir=state_dir,
            seed=config.seed, scenario=scenario,
            budgets={"recall_tokens": RECALL_TOKEN_BUDGET},
            profile="default", unavailable=config.unavailable,
        )
        for pid in config.providers:
            adapter_cls = registry.get(pid)
            if adapter_cls is None:
                err_list = result_validation_errors.setdefault("unknown-provider", [])
                err_list.append(f"{scenario['scenario_id']}: provider {pid!r} not in registry")
                continue
            result = _run_scenario_provider(adapter_cls, ctx, scenario, config, manifest)
            errors = v.validate_payload(result, "result", config.schema_dir)
            if errors:
                result_validation_errors[result["result_id"]] = errors
            results.append(result)

    return {
        "manifest": manifest,
        "results": results,
        "validation_errors": validation_errors,
        "schema_errors": schema_errors,
        "result_validation_errors": result_validation_errors,
        "run_dir": run_dir,
    }


def write_outputs(out_dir, summary):
    """Write manifest, per-result files, and validation-errors report to disk."""
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(summary["manifest"], fh, indent=2)

    results_dir = os.path.join(out_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    for result in summary["results"]:
        with open(os.path.join(results_dir, f"{result['result_id']}.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)

    errors_path = os.path.join(out_dir, "validation_errors.json")
    with open(errors_path, "w", encoding="utf-8") as fh:
        json.dump({"validation_errors": summary["validation_errors"],
                   "schema_errors": summary["schema_errors"],
                   "result_validation_errors": summary["result_validation_errors"]},
                  fh, indent=2)

    return {"manifest": manifest_path, "results_dir": results_dir,
            "validation_errors": errors_path}
