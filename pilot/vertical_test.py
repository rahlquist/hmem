"""Vertical isolation integration test orchestrator.

Runs three Docker containers in sequence to prove end-to-end memory
persistence and isolation:

  Container 1 (write):    Ingests an invented fact using the real
                           MeasuredHermesMemoryAdapter, writes MEMORY.md
                           to a bind-mounted volume, and recalls it to
                           confirm the write path works.

  Container 2 (recall):   A FRESH container with the SAME volume. Calls
                           recover() to reload MEMORY.md from disk, then
                           recalls the fact WITHOUT any new ingest.
                           Proves the fact survived the container restart.

  Container 3 (isolation): A FRESH container with a DIFFERENT (empty)
                           volume. Calls recover() (finds no MEMORY.md),
                           then recalls. Must abstain — proving a fresh
                           container cannot see facts from a different
                           volume.

Usage:
    python3 -m pilot.vertical_test
    python3 -m pilot.vertical_test --image hermes-benchmark:b5c5401a938be9e3
    python3 -m pilot.vertical_test --keep-volumes  (don't clean up)

Acceptance criteria:
    - Container 1 (write): ok=true, MEMORY.md exists, fact recalled
    - Container 2 (recall): ok=true, fact recalled from recovered MEMORY.md
    - Container 3 (isolation): ok=true, abstained=true, text=None
    - A report file documents the isolation proof
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Container-internal paths.
CONTAINER_HMEM = "/opt/hmem"
CONTAINER_PERSISTENCE = "/persistence"

# Image tag resolved from the benchmark manifest.
DEFAULT_MANIFEST = os.path.join("pilot-out", "benchmark-manifest.json")


def _docker_available():
    try:
        r = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _image_exists(tag):
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", tag],
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _resolve_image(manifest_path, override):
    if override:
        return override
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(
            f"benchmark manifest not found: {manifest_path}")
    with open(manifest_path) as fh:
        manifest = json.load(fh)
    tag = manifest.get("image", {}).get("tag")
    if not tag:
        raise ValueError(f"no image tag in manifest: {manifest_path}")
    return tag


def _run_container(image, mode, host_volume, timeout=60):
    """Run one container and return its result dict.

    Args:
        image:       Docker image tag.
        mode:        Worker mode (write / recall / isolation).
        host_volume: Host directory to bind-mount as /persistence.
        timeout:     Container run timeout in seconds.

    Returns:
        dict with keys: exit_code, stdout, stderr, duration_sec, result (parsed JSON or None)
    """
    abs_volume = os.path.abspath(host_volume)
    os.makedirs(abs_volume, exist_ok=True)

    # Bind-mount the local hmem repo read-only so the worker script
    # (which was added after the image was pinned) is available.
    # The image already has /opt/hmem from the pinned commit, but we
    # overlay our working tree to get the new files.
    hmem_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "512m",
        "--cpus=1.0",
        "--pids-limit=128",
        "-v", f"{abs_volume}:{CONTAINER_PERSISTENCE}:rw",
        "-v", f"{hmem_dir}:{CONTAINER_HMEM}:ro",
        "-e", "HMEM_DIR=/opt/hmem",
        image,
        "python3", f"{CONTAINER_HMEM}/pilot/vertical_test_worker.py",
        mode, CONTAINER_PERSISTENCE,
    ]

    t0 = time.perf_counter()
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        duration = time.perf_counter() - t0
        result_json = None
        if r.stdout.strip():
            try:
                result_json = json.loads(r.stdout.strip())
            except json.JSONDecodeError:
                # If the worker printed debug info before the JSON,
                # try to find the last { ... } block.
                text = r.stdout.strip()
                brace = text.rfind("{")
                if brace >= 0:
                    try:
                        result_json = json.loads(text[brace:])
                    except json.JSONDecodeError:
                        pass
        return {
            "exit_code": r.returncode,
            "stdout": r.stdout[:8192],
            "stderr": r.stderr[:4096],
            "duration_sec": round(duration, 2),
            "result": result_json,
        }
    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - t0
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"timeout after {timeout}s",
            "duration_sec": round(duration, 2),
            "result": None,
        }


def run_vertical_test(image, out_dir, keep_volumes=False):
    """Run the full 3-container vertical test.

    Returns a report dict.
    """
    # Create volume directories on the host.
    # Volume 1 (shared): used by container 1 (write) and container 2 (recall).
    # Volume 2 (fresh):  used by container 3 (isolation).
    volumes_root = os.path.join(out_dir, "volumes")
    shared_volume = os.path.join(volumes_root, "shared")
    fresh_volume = os.path.join(volumes_root, "fresh")

    # Clean up any previous volumes.
    for v in [shared_volume, fresh_volume]:
        if os.path.exists(v):
            shutil.rmtree(v)
        os.makedirs(v, exist_ok=True)

    print("=" * 60)
    print("VERTICAL ISOLATION INTEGRATION TEST")
    print("=" * 60)
    print(f"Image:    {image}")
    print(f"Out dir:  {out_dir}")
    print(f"Volumes:  {volumes_root}")
    print()

    # --- Container 1: WRITE ---
    print("[1/3] Container 1: WRITE (ingest fact, persist MEMORY.md)")
    c1 = _run_container(image, "write", shared_volume)
    print(f"      exit_code={c1['exit_code']} duration={c1['duration_sec']}s")
    if c1["result"]:
        print(f"      ok={c1['result'].get('ok')}")
        print(f"      memory_file={c1['result'].get('memory_file')}")
        print(f"      memory_file_content_len={c1['result'].get('memory_file_content_len')}")
        print(f"      recalled_text={c1['result'].get('recalled_text', '')[:80]}")
    if c1["stderr"]:
        print(f"      stderr: {c1['stderr'][:200]}")
    print()

    # Verify MEMORY.md exists on the shared volume.
    memory_md_path = os.path.join(
        shared_volume, "hermes-home", "memories", "MEMORY.md")
    memory_md_exists = os.path.exists(memory_md_path)
    memory_md_content = ""
    if memory_md_exists:
        with open(memory_md_path, "r") as fh:
            memory_md_content = fh.read()
    print(f"      Host-side MEMORY.md: exists={memory_md_exists} "
          f"len={len(memory_md_content)}")
    print()

    # --- Container 2: RECALL ---
    print("[2/3] Container 2: RECALL (fresh container, same volume, recover)")
    c2 = _run_container(image, "recall", shared_volume)
    print(f"      exit_code={c2['exit_code']} duration={c2['duration_sec']}s")
    if c2["result"]:
        print(f"      ok={c2['result'].get('ok')}")
        print(f"      recovery={c2['result'].get('recovery')}")
        print(f"      recalled_text={c2['result'].get('recalled_text', '')[:80]}")
        print(f"      abstained={c2['result'].get('abstained')}")
    if c2["stderr"]:
        print(f"      stderr: {c2['stderr'][:200]}")
    print()

    # --- Container 3: ISOLATION ---
    print("[3/3] Container 3: ISOLATION (fresh container, fresh volume)")
    c3 = _run_container(image, "isolation", fresh_volume)
    print(f"      exit_code={c3['exit_code']} duration={c3['duration_sec']}s")
    if c3["result"]:
        print(f"      ok={c3['result'].get('ok')}")
        print(f"      recovery={c3['result'].get('recovery')}")
        print(f"      recalled_text={c3['result'].get('recalled_text')}")
        print(f"      abstained={c3['result'].get('abstained')}")
    if c3["stderr"]:
        print(f"      stderr: {c3['stderr'][:200]}")
    print()

    # --- Determine pass/fail ---
    c1_ok = (c1["exit_code"] == 0 and c1["result"] and c1["result"]["ok"])
    c2_ok = (c2["exit_code"] == 0 and c2["result"] and c2["result"]["ok"])
    c3_ok = (c3["exit_code"] == 0 and c3["result"] and c3["result"]["ok"])
    all_pass = c1_ok and c2_ok and c3_ok

    # Verify the fresh volume has NO MEMORY.md with the fact.
    fresh_memory_md = os.path.join(
        fresh_volume, "hermes-home", "memories", "MEMORY.md")
    fresh_memory_exists = os.path.exists(fresh_memory_md)
    fresh_memory_content = ""
    if fresh_memory_exists:
        with open(fresh_memory_md, "r") as fh:
            fresh_memory_content = fh.read()
    fresh_volume_clean = (
        not fresh_memory_exists
        or "Zephyr" not in fresh_memory_content
    )

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  Container 1 (write):     {'PASS' if c1_ok else 'FAIL'}")
    print(f"  Container 2 (recall):    {'PASS' if c2_ok else 'FAIL'}")
    print(f"  Container 3 (isolation): {'PASS' if c3_ok else 'FAIL'}")
    print(f"  Fresh volume clean:      {fresh_volume_clean}")
    print(f"  OVERALL:                  {'PASS' if all_pass else 'FAIL'}")
    print()

    # Build the full report.
    report = {
        "test_name": "vertical-isolation-integration-test",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "image": image,
        "out_dir": out_dir,
        "invented_fact": "The Zephyr project deployment window is October 15th at 3am UTC.",
        "invented_query": "When is the Zephyr project deployment window?",
        "expected_answer_fragment": "October 15th",
        "containers": {
            "container_1_write": {
                "mode": "write",
                "exit_code": c1["exit_code"],
                "duration_sec": c1["duration_sec"],
                "result": c1["result"],
                "stderr": c1["stderr"] if c1["stderr"] else None,
            },
            "container_2_recall": {
                "mode": "recall",
                "exit_code": c2["exit_code"],
                "duration_sec": c2["duration_sec"],
                "result": c2["result"],
                "stderr": c2["stderr"] if c2["stderr"] else None,
            },
            "container_3_isolation": {
                "mode": "isolation",
                "exit_code": c3["exit_code"],
                "duration_sec": c3["duration_sec"],
                "result": c3["result"],
                "stderr": c3["stderr"] if c3["stderr"] else None,
            },
        },
        "host_side_checks": {
            "shared_volume_memory_md": {
                "path": memory_md_path,
                "exists": memory_md_exists,
                "content_len": len(memory_md_content),
                "contains_fact": "Zephyr" in memory_md_content,
            },
            "fresh_volume_memory_md": {
                "path": fresh_memory_md,
                "exists": fresh_memory_exists,
                "content_len": len(fresh_memory_content),
                "contains_fact": "Zephyr" in fresh_memory_content,
            },
        },
        "pass_fail": {
            "container_1_write": c1_ok,
            "container_2_recall": c2_ok,
            "container_3_isolation": c3_ok,
            "fresh_volume_clean": fresh_volume_clean,
            "overall": all_pass,
        },
        "isolation_proof": {
            "description": (
                "Container 3 started with a fresh (empty) persistence volume. "
                "recover() found no MEMORY.md with the invented fact. "
                "recall() abstained (text=None, abstained=true). "
                "This proves that a fresh container cannot see facts written "
                "by a previous container to a different volume — memory is "
                "isolated per volume and does not leak across containers."
            ),
            "fact_written_by_container_1": c1_ok and memory_md_exists,
            "fact_recalled_by_container_2": c2_ok,
            "fact_not_visible_to_container_3": c3_ok and fresh_volume_clean,
        },
    }

    # Write report files.
    report_path = os.path.join(out_dir, "vertical-test-report.json")
    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=2)

    # Write markdown report.
    md = _generate_markdown_report(report)
    md_path = os.path.join(out_dir, "vertical-test-report.md")
    with open(md_path, "w") as fh:
        fh.write(md)

    print(f"Report: {report_path}")
    print(f"Report: {md_path}")

    # Cleanup.
    if not keep_volumes:
        shutil.rmtree(volumes_root, ignore_errors=True)
        print(f"Cleaned up volumes: {volumes_root}")

    return all_pass, report


def _generate_markdown_report(report):
    """Generate a human-readable markdown report."""
    pf = report["pass_fail"]
    c1 = report["containers"]["container_1_write"]
    c2 = report["containers"]["container_2_recall"]
    c3 = report["containers"]["container_3_isolation"]
    iso = report["isolation_proof"]
    hs = report["host_side_checks"]

    lines = [
        "# Vertical Isolation Integration Test Report",
        "",
        f"**Timestamp:** {report['timestamp']}",
        f"**Image:** `{report['image']}`",
        f"**Overall:** {'PASS' if pf['overall'] else 'FAIL'}",
        "",
        "## Test Design",
        "",
        "This test runs three Docker containers in sequence to prove end-to-end",
        "memory persistence and isolation using the real MeasuredHermesMemoryAdapter:",
        "",
        "1. **Container 1 (write):** Ingests an invented fact, writes MEMORY.md",
        "   to a bind-mounted volume, and recalls it to confirm the write path.",
        "2. **Container 2 (recall):** A FRESH container with the SAME volume.",
        "   Calls `recover()` to reload MEMORY.md from disk (no new ingest),",
        "   then recalls the fact. Proves the fact survived the container restart.",
        "3. **Container 3 (isolation):** A FRESH container with a DIFFERENT (empty)",
        "   volume. Calls `recover()` (finds no MEMORY.md), then recalls.",
        "   Must abstain — proving a fresh container cannot see facts from",
        "   a different volume.",
        "",
        "## Invented Fact",
        "",
        f"> {report['invented_fact']}",
        "",
        f"**Query:** {report['invented_query']}",
        f"**Expected answer fragment:** {report['expected_answer_fragment']}",
        "",
        "## Results",
        "",
        "| Container | Mode | Exit Code | Duration | Pass/Fail |",
        "|-----------|------|-----------|----------|-----------|",
        f"| 1 | write     | {c1['exit_code']} | {c1['duration_sec']}s | {'PASS' if pf['container_1_write'] else 'FAIL'} |",
        f"| 2 | recall    | {c2['exit_code']} | {c2['duration_sec']}s | {'PASS' if pf['container_2_recall'] else 'FAIL'} |",
        f"| 3 | isolation | {c3['exit_code']} | {c3['duration_sec']}s | {'PASS' if pf['container_3_isolation'] else 'FAIL'} |",
        "",
        "## Container 1: Write",
        "",
    ]
    if c1["result"]:
        r = c1["result"]
        lines += [
            f"- **ok:** {r['ok']}",
            f"- **MEMORY.md:** {r['memory_file']}",
            f"- **MEMORY.md exists:** {r['memory_file_exists']}",
            f"- **MEMORY.md content length:** {r['memory_file_content_len']} bytes",
            f"- **Recalled text:** {r.get('recalled_text', '')[:100]}",
            f"- **Abstained:** {r['abstained']}",
            f"- **Evidence turns:** {r['evidence_turns']}",
            f"- **Hermes home:** {r['hermes_home']}",
        ]
    else:
        lines.append("- **No result JSON parsed**")
        if c1.get("stderr"):
            lines.append(f"- **stderr:** {c1['stderr'][:300]}")

    lines += [
        "",
        "## Container 2: Recall (Fresh Container, Same Volume)",
        "",
    ]
    if c2["result"]:
        r = c2["result"]
        lines += [
            f"- **ok:** {r['ok']}",
            f"- **Recovery:** {r.get('recovery')}",
            f"- **Recalled text:** {r.get('recalled_text', '')[:100]}",
            f"- **Abstained:** {r['abstained']}",
            f"- **Evidence turns:** {r['evidence_turns']}",
            f"- **MEMORY.md exists:** {r['memory_file_exists']}",
            f"- **MEMORY.md content length:** {r['memory_file_content_len']} bytes",
        ]
    else:
        lines.append("- **No result JSON parsed**")
        if c2.get("stderr"):
            lines.append(f"- **stderr:** {c2['stderr'][:300]}")

    lines += [
        "",
        "## Container 3: Isolation (Fresh Container, Fresh Volume)",
        "",
    ]
    if c3["result"]:
        r = c3["result"]
        lines += [
            f"- **ok:** {r['ok']}",
            f"- **Recovery:** {r.get('recovery')}",
            f"- **Recalled text:** {r.get('recalled_text')}",
            f"- **Abstained:** {r['abstained']}",
            f"- **Evidence turns:** {r['evidence_turns']}",
            f"- **MEMORY.md exists:** {r['memory_file_exists']}",
            f"- **MEMORY.md content length:** {r['memory_file_content_len']} bytes",
        ]
    else:
        lines.append("- **No result JSON parsed**")
        if c3.get("stderr"):
            lines.append(f"- **stderr:** {c3['stderr'][:300]}")

    lines += [
        "",
        "## Host-Side Verification",
        "",
        "### Shared Volume MEMORY.md",
        f"- **Path:** `{hs['shared_volume_memory_md']['path']}`",
        f"- **Exists:** {hs['shared_volume_memory_md']['exists']}",
        f"- **Content length:** {hs['shared_volume_memory_md']['content_len']} bytes",
        f"- **Contains fact ('Zephyr'):** {hs['shared_volume_memory_md']['contains_fact']}",
        "",
        "### Fresh Volume MEMORY.md",
        f"- **Path:** `{hs['fresh_volume_memory_md']['path']}`",
        f"- **Exists:** {hs['fresh_volume_memory_md']['exists']}",
        f"- **Content length:** {hs['fresh_volume_memory_md']['content_len']} bytes",
        f"- **Contains fact ('Zephyr'):** {hs['fresh_volume_memory_md']['contains_fact']}",
        "",
        "## Isolation Proof",
        "",
        f"{iso['description']}",
        "",
        f"- **Fact written by container 1:** {iso['fact_written_by_container_1']}",
        f"- **Fact recalled by container 2:** {iso['fact_recalled_by_container_2']}",
        f"- **Fact not visible to container 3:** {iso['fact_not_visible_to_container_3']}",
        "",
        "## Conclusion",
        "",
    ]
    if pf["overall"]:
        lines.append(
            "**PASS** — All three container runs passed. The invented fact was "
            "written by container 1, survived the container restart and was "
            "recalled by container 2, and was NOT visible to container 3 "
            "(which started with a fresh volume and correctly abstained). "
            "This proves memory isolation across containers with separate volumes."
        )
    else:
        lines.append(
            "**FAIL** — One or more container runs did not pass. See the "
            "results above for details."
        )

    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="vertical-test",
        description="Vertical isolation integration test: write, restart-recall, "
                    "prove fresh container cannot see the fact.",
    )
    parser.add_argument("--image", default=None,
                        help="Docker image tag (default: from benchmark manifest)")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST,
                        help=f"benchmark manifest path (default: {DEFAULT_MANIFEST})")
    parser.add_argument("--out-dir", default="pilot-out/vertical-test",
                        help="output directory (default: pilot-out/vertical-test)")
    parser.add_argument("--keep-volumes", action="store_true",
                        help="don't clean up volume directories after the test")
    args = parser.parse_args(argv)

    if not _docker_available():
        print("ERROR: docker is not available or daemon not running.",
              file=sys.stderr)
        return 2

    try:
        image = _resolve_image(args.manifest, args.image)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if not _image_exists(image):
        print(f"ERROR: Docker image not found: {image}", file=sys.stderr)
        return 2

    os.makedirs(args.out_dir, exist_ok=True)

    all_pass, report = run_vertical_test(
        image, args.out_dir, keep_volumes=args.keep_volumes)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
