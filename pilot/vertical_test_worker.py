"""In-container worker for the vertical isolation integration test.

This script runs INSIDE a Docker container (the hermes-benchmark image).
It uses the real MeasuredHermesMemoryAdapter to write, recall, or prove
isolation of an invented fact, writing/reading MEMORY.md from a
bind-mounted persistence volume.

Three modes:

  write    — ingest an invented fact, persist to MEMORY.md, then recall
             to confirm the write path works. Output JSON to stdout.
  recall   — recover() from existing MEMORY.md (no ingest), then recall
             the fact. Proves the fact survived the container restart.
  isolation— start with a fresh (empty) work_dir, recover() finds no
             MEMORY.md, recall abstains. Proves a fresh container
             cannot see facts from a different volume.

Usage (inside container)::

    python3 /opt/hmem/pilot/vertical_test_worker.py write /persistence
    python3 /opt/hmem/pilot/vertical_test_worker.py recall /persistence
    python3 /opt/hmem/pilot/vertical_test_worker.py isolation /persistence

Output: a single JSON object on stdout with keys:
    mode, fact_text, query, recalled_text, abstained, evidence_turns,
    memory_file_exists, memory_file_content_len, hermes_home, ok
"""
import json
import os
import sys
import traceback

# The pilot package is at /opt/hmem inside the benchmark image.
# When running from the host (for import/testing), it's on sys.path already.
HMEM_DIR = os.environ.get("HMEM_DIR", "/opt/hmem")
if HMEM_DIR not in sys.path:
    sys.path.insert(0, HMEM_DIR)

from pilot.adapters import AdapterContext  # noqa: E402
from pilot.hermes_memory import MeasuredHermesMemoryAdapter  # noqa: E402


# The invented fact — completely synthetic, never real data.
INVENTED_FACT = (
    "The Zephyr project deployment window is October 15th at 3am UTC."
)
INVENTED_QUERY = "When is the Zephyr project deployment window?"
EXPECTED_ANSWER_FRAGMENT = "October 15th"


def run_write(persistence_dir):
    """Write the invented fact to MEMORY.md and verify recall in-process."""
    os.makedirs(persistence_dir, exist_ok=True)
    ctx = AdapterContext(
        work_dir=persistence_dir,
        seed=42,
        scenario={"scenario_id": "vertical-write"},
        budgets={"recall_tokens": 4096},
        profile="default",
    )
    adapter = MeasuredHermesMemoryAdapter(ctx)
    adapter.setup()

    # Ingest the invented fact as a user turn.
    history = [
        {"role": "user", "content": INVENTED_FACT, "session": "s1"},
        {"role": "assistant", "content": "Noted.", "session": "s1"},
    ]
    stats = adapter.ingest(history)

    # Recall to confirm the write path works.
    out = adapter.recall(INVENTED_QUERY)

    # Teardown writes MEMORY.md to disk.
    adapter.teardown()

    mem_file = adapter.memory_file
    mem_exists = os.path.exists(mem_file)
    mem_content_len = 0
    if mem_exists:
        with open(mem_file, "r") as fh:
            mem_content_len = len(fh.read())

    return {
        "mode": "write",
        "fact_text": INVENTED_FACT,
        "query": INVENTED_QUERY,
        "recalled_text": out.get("text"),
        "abstained": bool(out.get("abstained")),
        "evidence_turns": list(out.get("evidence_turns") or []),
        "memory_file": mem_file,
        "memory_file_exists": mem_exists,
        "memory_file_content_len": mem_content_len,
        "hermes_home": adapter.hermes_home,
        "ingest_stats": stats,
        "ok": (
            mem_exists
            and mem_content_len > 0
            and not out.get("abstained")
            and EXPECTED_ANSWER_FRAGMENT.lower() in (out.get("text") or "").lower()
        ),
    }


def run_recall(persistence_dir):
    """Recover from existing MEMORY.md and recall the fact.

    This is the critical step: a FRESH container process reads MEMORY.md
    from the shared volume — proving the fact survived the container
    restart. We do NOT call ingest (which would overwrite); we call
    recover() to reload from the file.
    """
    ctx = AdapterContext(
        work_dir=persistence_dir,
        seed=42,
        scenario={"scenario_id": "vertical-recall"},
        budgets={"recall_tokens": 4096},
        profile="default",
    )
    adapter = MeasuredHermesMemoryAdapter(ctx)
    adapter.setup()

    # CRITICAL: recover() reads MEMORY.md from the persistence volume.
    # This is the real restart-recovery path — a fresh process loading
    # state that a previous container wrote to disk.
    recovery = adapter.recover()

    # Now recall without any ingest — the store was populated by recover().
    out = adapter.recall(INVENTED_QUERY)

    adapter.teardown()

    mem_file = adapter.memory_file
    mem_exists = os.path.exists(mem_file)
    mem_content_len = 0
    if mem_exists:
        with open(mem_file, "r") as fh:
            mem_content_len = len(fh.read())

    return {
        "mode": "recall",
        "fact_text": INVENTED_FACT,
        "query": INVENTED_QUERY,
        "recalled_text": out.get("text"),
        "abstained": bool(out.get("abstained")),
        "evidence_turns": list(out.get("evidence_turns") or []),
        "memory_file": mem_file,
        "memory_file_exists": mem_exists,
        "memory_file_content_len": mem_content_len,
        "hermes_home": adapter.hermes_home,
        "recovery": recovery,
        "ok": (
            mem_exists
            and not out.get("abstained")
            and EXPECTED_ANSWER_FRAGMENT.lower() in (out.get("text") or "").lower()
        ),
    }


def run_isolation(persistence_dir):
    """Prove a fresh container with a fresh volume cannot see the fact.

    Uses a fresh work_dir (empty — no MEMORY.md). recover() finds no file,
    recall() abstains. This proves container isolation: facts do not
    leak across volumes.
    """
    # The persistence_dir here is a FRESH empty directory — no MEMORY.md.
    os.makedirs(persistence_dir, exist_ok=True)

    ctx = AdapterContext(
        work_dir=persistence_dir,
        seed=42,
        scenario={"scenario_id": "vertical-isolation"},
        budgets={"recall_tokens": 4096},
        profile="default",
    )
    adapter = MeasuredHermesMemoryAdapter(ctx)
    adapter.setup()

    # recover() will find no MEMORY.md (fresh volume) — creates an empty one.
    recovery = adapter.recover()

    # recall() with an empty store — must abstain.
    out = adapter.recall(INVENTED_QUERY)

    adapter.teardown()

    mem_file = adapter.memory_file
    mem_exists = os.path.exists(mem_file)
    mem_content_len = 0
    if mem_exists:
        with open(mem_file, "r") as fh:
            mem_content_len = len(fh.read())

    return {
        "mode": "isolation",
        "fact_text": INVENTED_FACT,
        "query": INVENTED_QUERY,
        "recalled_text": out.get("text"),
        "abstained": bool(out.get("abstained")),
        "evidence_turns": list(out.get("evidence_turns") or []),
        "memory_file": mem_file,
        "memory_file_exists": mem_exists,
        "memory_file_content_len": mem_content_len,
        "hermes_home": adapter.hermes_home,
        "recovery": recovery,
        "ok": bool(out.get("abstained")) and (out.get("text") is None),
    }


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "error": "usage: vertical_test_worker.py <mode> <persistence_dir>",
        }))
        sys.exit(2)

    mode = sys.argv[1]
    persistence_dir = sys.argv[2]

    try:
        if mode == "write":
            result = run_write(persistence_dir)
        elif mode == "recall":
            result = run_recall(persistence_dir)
        elif mode == "isolation":
            result = run_isolation(persistence_dir)
        else:
            print(json.dumps({"error": f"unknown mode: {mode}"}))
            sys.exit(2)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["ok"] else 1)
    except Exception as exc:
        print(json.dumps({
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }))
        sys.exit(3)


if __name__ == "__main__":
    main()
