"""CLI entrypoint for the hmem pilot.

Runs a deterministic dry-run against provider adapter stubs, writes
manifest/results/report, and prints a summary. Use --validate-only to just
validate schemas and scenario fixtures (the automated validation command).

Examples:
    python -m pilot.cli --validate-only
    python -m pilot.cli --out-dir /tmp/hmem-pilot --repetitions 3 --seed 7
    python -m pilot.cli --providers hermes_memory,lexical_baseline
    python -m pilot.cli --unavailable hindsight,mnemosyne
"""
import argparse
import json
import os
import sys

from . import PROVIDER_IDS
from . import report as rp
from . import runner as rn
from . import validate as v


def _print_validation(schema_errors, validated):
    print("schema documents:",
          "OK" if not schema_errors else f"{len(schema_errors)} error(s)")
    for doc, errs in schema_errors.items():
        print(f"  {doc}: {errs}")
    print(f"scenarios: {len(validated['valid'])} valid, "
          f"{len(validated['invalid'])} invalid")
    for path, errs in validated["invalid"].items():
        print(f"  {path}: {errs}")
    return not schema_errors and not validated["invalid"]


def _print_summary(summary, report):
    totals = report["report_json"]["totals"]
    print(f"manifest:      {summary['manifest']['manifest_id']}")
    print(f"mode:          {summary['manifest']['mode']}")
    print(f"scenarios:     {totals['scenarios']}")
    print(f"results:       {totals['results']}")
    print(f"outcomes:      {totals['ok']} ok, {totals['failure']} failure, "
          f"{totals['unsupported']} unsupported, "
          f"{totals['setup_failed']} setup_failed")
    print(f"simulated:     {report['report_json']['provenance_counts']['simulated']} "
          f"(all stub results are simulated, provenance=inferred)")
    if summary["result_validation_errors"]:
        print("result schema validation errors: "
              f"{len(summary['result_validation_errors'])}")
    print("wrote: manifest.json, results/*.json, validation_errors.json, "
          "report.md, report.json")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="hmem-pilot",
        description="Reproducible clean-machine-oriented memory-provider pilot. "
                    "Dry-run safe: deterministic provider adapter stubs, no real "
                    "providers, network, or secrets required.",
    )
    parser.add_argument("--out-dir", default="pilot-out",
                        help="output directory (default: pilot-out)")
    parser.add_argument("--schema-dir", default=v.DEFAULT_SCHEMA_DIR,
                        help="directory with versioned *.schema.json documents")
    parser.add_argument("--scenarios-dir", default=v.DEFAULT_SCENARIOS_DIR,
                        help="directory with scenario fixture JSON files")
    parser.add_argument("--providers", default=",".join(PROVIDER_IDS),
                        help="comma-separated provider ids to run")
    parser.add_argument("--unavailable", default="",
                        help="comma-separated provider ids to report as unsupported")
    parser.add_argument("--repetitions", type=int, default=3,
                        help="ingest+recall repetitions per scenario (default: 3)")
    parser.add_argument("--seed", type=int, default=7,
                        help="deterministic seed (default: 7)")
    parser.add_argument("--mode", choices=["dry_run", "live"], default="dry_run",
                        help="run mode (default: dry_run)")
    parser.add_argument("--validate-only", action="store_true",
                        help="validate schemas and scenario fixtures, then exit")
    args = parser.parse_args(argv)

    schema_errors = v.schema_errors_for_dir(args.schema_dir)
    validated = v.validate_all_scenarios(args.scenarios_dir, args.schema_dir)
    if args.validate_only:
        ok = _print_validation(schema_errors, validated)
        return 0 if ok else 1

    if schema_errors or validated["invalid"]:
        _print_validation(schema_errors, validated)
        print("errors above; run with --validate-only for a clean check, or fix "
              "fixtures before running.", file=sys.stderr)

    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    unavailable = {p.strip() for p in args.unavailable.split(",") if p.strip()}
    config = rn.RunConfig(
        schema_dir=args.schema_dir,
        scenarios_dir=args.scenarios_dir,
        out_dir=args.out_dir,
        providers=providers,
        unavailable=unavailable,
        repetitions=args.repetitions,
        seed=args.seed,
        mode=args.mode,
    )
    summary = rn.run_dry_run(config)
    paths = rn.write_outputs(args.out_dir, summary)
    report = rp.generate_report(summary["manifest"], summary["results"],
                                summary["validation_errors"],
                                summary["schema_errors"])
    with open(os.path.join(args.out_dir, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report["report_md"])
    with open(os.path.join(args.out_dir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report["report_json"], fh, indent=2)

    _print_summary(summary, report)
    print(f"report:        {os.path.join(args.out_dir, 'report.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
