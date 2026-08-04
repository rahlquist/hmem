"""Convert the evaluation corpus (rich scenario schema, evaluation/fixtures/
scenarios) into the pilot's minimal scenario schema so the full ~30-case
reviewed corpus can be run through the pilot harness.

The pilot README documents this integration path: "the sibling evaluation/
specification defines a richer corpus schema; the pilot uses a minimal
compatible structure so scenarios can be adapted by writing a thin converter."

Mapping rules (deterministic, documented):
  - scenario_id: lowercased (eval "ABST-01" -> pilot "abst-01") because the
    pilot schema id pattern is ^[a-z0-9][a-z0-9-]*$; the original id is kept
    in provenance.notes for traceability.
  - category: eval kebab-case -> pilot snake_case enum (CATEGORY_MAP).
  - split: "dev" -> "dev", "held-out" -> "held_out".
  - history: one turn per setup event. role from speaker
    (user/assistant/system; tool and provider -> system). session_id ->
    session, timestamp -> ts_iso, role_in_case == "untrusted" -> untrusted.
  - query: probe.text. context: omitted (eval fixtures express boundaries in
    natural-language probe notes; the minimal schema carries profile/host/
    project, which are not machine-readable in the eval corpus — recorded as
    a limitation in the report and verification note).
  - expected.answer: expected.correct (string) or null for abstain /
    premise-rejection cases. evidence_turns: must_use_evidence event ids
    mapped to history indices via the setup event order. abstain /
    premise_invalid: mapped from expected.abstain / expected.reject_premise.
  - expected.superseded: full content of the event with role_in_case
    "superseded" (a statement, kept whole so stale-reuse detection matches a
    recalled old fact). expected.deleted: content of the event with
    role_in_case "deleted", with the directive wrapper stripped
    ("Please delete the fact that X" -> "X") so the stale *value* is what
    scoring checks.
  - provenance: source/license from origin; author "hmem evaluation corpus";
    created_iso from probe.timestamp (synthetic corpus dates); reviewed True
    (the corpus is the reviewed synthetic set from the spec task); notes keep
    the original scenario_id, origin notes, and probe notes.
  - privacy: synthetic True, contains_real_data False (eval corpus is fully
    synthetic; even fixtures whose text includes invented credentials are
    marked contains_real_data=False).

Known limitation (recorded, never hidden): isolation boundary metadata
(profile/host/project) lives only in eval probe.notes prose, so converted ISO
scenarios carry no machine-readable boundary. The deterministic stubs then
treat all facts as in-scope and will answer; ISO results measure leakage and
the report limitations section explains why.
"""
import argparse
import json
import os
import re

from . import validate as v

# Evaluation category (kebab-case) -> pilot category (snake_case enum).
CATEGORY_MAP = {
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

SPEAKER_ROLE = {
    "user": "user",
    "assistant": "assistant",
    "system": "system",
    "tool": "system",
    "provider": "system",
}

# "Please delete the fact that X" / "Delete the fact that X" -> "X"
_DIRECTIVE_RE = re.compile(
    r"^(please\s+)?(delete|forget|remove)\s+"
    r"(the\s+)?(fact\s+)?(that\s+|the\s+fact\s+that\s+)?",
    re.IGNORECASE,
)

SCHEMA_VERSION = "scenario@1.0.0"
DEFAULT_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "evaluation", "fixtures", "scenarios",
)


def _strip_directive(content):
    """Strip a deletion-directive wrapper, returning the stale value.

    "Please delete the fact that the workshop VM accepts SSH on port 4422."
      -> "the workshop VM accepts SSH on port 4422."
    Falls back to the original content when no directive pattern matches.
    """
    if not content:
        return content
    match = _DIRECTIVE_RE.match(content)
    if match:
        return content[match.end():].strip()
    return content


def convert_scenario(doc):
    """Convert one evaluation-format scenario into pilot scenario format."""
    event_id_to_index = {e["event_id"]: i for i, e in enumerate(doc["setup"])}

    history = []
    for event in doc["setup"]:
        turn = {
            "role": SPEAKER_ROLE.get(event.get("speaker"), "system"),
            "content": event.get("content", ""),
        }
        if event.get("session_id"):
            turn["session"] = event["session_id"]
        if event.get("timestamp"):
            turn["ts_iso"] = event["timestamp"]
        if event.get("role_in_case") == "untrusted":
            turn["untrusted"] = True
        history.append(turn)

    exp = doc.get("expected", {})
    answer = exp.get("correct")
    expected = {
        "answer": answer if isinstance(answer, str) else None,
        "evidence_turns": [
            event_id_to_index[eid]
            for eid in exp.get("must_use_evidence", [])
            if eid in event_id_to_index
        ],
        "abstain": bool(exp.get("abstain", False)),
        "premise_invalid": bool(exp.get("reject_premise", False)),
    }

    superseded = next((e for e in doc["setup"]
                       if e.get("role_in_case") == "superseded"), None)
    deleted = next((e for e in doc["setup"]
                    if e.get("role_in_case") == "deleted"), None)
    if superseded:
        expected["superseded"] = superseded.get("content", "")
    if deleted:
        expected["deleted"] = _strip_directive(deleted.get("content", ""))

    origin = doc.get("origin", {})
    probe = doc.get("probe", {})
    notes = (
        f"converted from evaluation fixture {doc.get('scenario_id')}; "
        f"origin: {origin.get('notes') or 'no origin notes'}; "
        f"probe: {probe.get('notes') or 'no probe notes'}"
    )

    description = doc.get("world", {}).get("description", "")
    rationale = exp.get("rationale")
    if rationale:
        description = f"{description} {rationale}".strip()

    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": doc["scenario_id"].lower(),
        "category": CATEGORY_MAP[doc["category"]],
        "split": "held_out" if doc.get("split") == "held-out" else "dev",
        "name": doc.get("title", doc.get("scenario_id", "")),
        "description": description,
        "history": history,
        "query": probe.get("text", ""),
        "expected": expected,
        "provenance": {
            "source": (origin.get("source_ref")
                       or f"evaluation corpus fixture {doc.get('scenario_id')} "
                          "(synthetic, converted)"),
            "license": origin.get("license", "CC0-1.0"),
            "author": "hmem evaluation corpus",
            "created_iso": probe.get("timestamp", "2026-07-01T00:00:00Z"),
            "reviewed": True,
            "notes": notes,
        },
        "privacy": {"synthetic": True, "contains_real_data": False},
    }


def convert_corpus(src_dir=DEFAULT_SRC):
    """Convert every scenario fixture in `src_dir`.

    Returns {"converted": [pilot scenario docs], "errors": {path: err}}.
    """
    converted, errors = [], {}
    if not os.path.isdir(src_dir):
        return {"converted": [], "errors": {src_dir: "directory not found"}}
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(src_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            converted.append(convert_scenario(doc))
        except Exception as exc:  # never drop a fixture silently
            errors[path] = f"{type(exc).__name__}: {exc}"
    return {"converted": converted, "errors": errors}


def write_corpus(src_dir=DEFAULT_SRC, out_dir="pilot-out/scenarios-eval"):
    """Convert the corpus and write pilot-format scenario files.

    Returns the list of written absolute paths.
    """
    result = convert_corpus(src_dir)
    if result["errors"]:
        raise RuntimeError(f"conversion errors: {result['errors']}")
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for doc in result["converted"]:
        path = os.path.join(out_dir, f"{doc['scenario_id']}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
        written.append(path)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="hmem-pilot-convert-eval",
        description="Convert evaluation corpus scenarios into pilot scenario "
                    "format and validate them against the pilot scenario schema.",
    )
    ap.add_argument("--src", default=DEFAULT_SRC,
                    help="evaluation fixtures/scenarios dir (default: %(default)s)")
    ap.add_argument("--out", default="pilot-out/scenarios-eval",
                    help="output dir for converted scenarios (default: %(default)s)")
    ap.add_argument("--validate-only", action="store_true",
                    help="convert in memory and validate; do not write files")
    args = ap.parse_args(argv)

    if args.validate_only:
        result = convert_corpus(args.src)
        for path, err in result["errors"].items():
            print(f"ERROR {path}: {err}")
        valid = invalid = 0
        schema_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "schemas")
        for doc in result["converted"]:
            errors = v.validate_payload(doc, "scenario", schema_dir)
            if errors:
                invalid += 1
                print(f"INVALID {doc['scenario_id']}: {errors}")
            else:
                valid += 1
        print(f"converted: {len(result['converted'])} total, "
              f"{valid} valid, {invalid} invalid, "
              f"{len(result['errors'])} conversion error(s)")
        return 0 if valid and not invalid and not result["errors"] else 1

    written = write_corpus(args.src, args.out)
    print(f"wrote {len(written)} converted scenarios to {args.out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
