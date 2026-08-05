# hmem Containerized Benchmark Phase — Verification Note

Date (UTC): 2026-08-05T03:33:00Z
Phase: Containerized benchmark — Docker-isolated execution, real Hermes memory adapter, vertical isolation proof

## Scope

This verification note documents the containerized benchmark phase of the hmem
pilot. The phase delivers three components:

1. **pilot/container_runner.py** — Docker container lifecycle runner that
   creates a fresh container per scenario using a pinned benchmark image,
   mounts tmpfs for HERMES_HOME, bind-mounts scenario input (read-only) and
   result output (read-write), sets `--network none` for baseline isolation,
   applies resource limits (memory, CPU, PID), and tears down containers after
   each run.

2. **pilot/hermes_memory.py** — Real Hermes built-in memory adapter
   (`MeasuredHermesMemoryAdapter`) that writes to a disposable HERMES_HOME
   (a temp directory under the adapter's work_dir), exercises actual
   MEMORY.md file I/O using the §-delimited Hermes memory format, and
   implements the same policy surface as the stub `HermesMemoryAdapter`:
   append-only facts, newest-wins per fact key, explicit deletion,
   profile/host boundaries, trust filtering, and persistence via real file
   writes.

3. **pilot/vertical_test.py + pilot/vertical_test_worker.py** — A vertical
   integration test that runs three Docker containers in sequence to prove
   end-to-end memory persistence and isolation:
   - Container 1 writes a fact to MEMORY.md and recalls it.
   - Container 2 (fresh, same volume) calls recover() and recalls the fact.
   - Container 3 (fresh, empty volume) calls recover() and must abstain.

## Pinned Docker Image

The benchmark image is pinned for reproducibility:

- Image tag: `hermes-benchmark:6f8c0317eb7e13da`
- hermes-agent pinned at: f5be9236
- hmem pinned at: 37a2581
- Image digest: sha256:e2de8f21299f38fa5a4a415f23b1...
- Build script: `docker/benchmark/build.sh`

The manifest at `pilot-out/benchmark-manifest.json` records the image tag,
git commits, and build timestamp.

## Container Configuration

Each container runs with:

- `--network none` — no network access (baseline isolation)
- `--memory 512m` — memory limit
- `--cpus=1.0` — CPU quota
- `--pids-limit=128` — PID limit
- `--tmpfs /tmp/hermes-home:rw,size=64m,mode=1777` — ephemeral HERMES_HOME
- `-v <scenarios>:/scenarios:ro` — scenario input (read-only)
- `-v <results>:/results:rw` — result output (read-write)
- `-e HERMES_HOME=/tmp/hermes-home` — HERMES_HOME env var

## Vertical Isolation Test Results

All three containers passed (exit_code=0, ok=true):

| Container | Mode      | Exit Code | Duration | Result |
|-----------|-----------|-----------|----------|--------|
| 1         | write     | 0         | 0.28s    | PASS   |
| 2         | recall    | 0         | 0.25s    | PASS   |
| 3         | isolation | 0         | 0.25s    | PASS   |

- Container 1: Wrote "The Zephyr project deployment window is October 15th at 3am UTC." to MEMORY.md and recalled it.
- Container 2: Fresh container, same volume. Called recover() to reload MEMORY.md from disk. Recalled the fact without any new ingest — proving the fact survived the container restart.
- Container 3: Fresh container, fresh empty volume. Called recover() finding no MEMORY.md. recall() correctly abstained (text=None, abstained=true) — proving a fresh container cannot see facts from a different volume.

Report files: `pilot-out/vertical-test/vertical-test-report.{json,md}`

## Measured Hermes Memory Adapter Verification

The `MeasuredHermesMemoryAdapter` is labeled `measured=True` so the runner
labels its results `measurement_kind=measured` / `provenance=hmem-measured`.
Only the real path produces this label; the policy-simulation stub in
`adapters.HermesMemoryAdapter` is retained for dry-run compatibility and is
never relabeled.

### Policy surface (matches the stub adapter)

| Policy            | Value  |
|-------------------|--------|
| newest_wins       | true   |
| forgets           | true   |
| synthesizes       | false  |
| premise_aware     | false  |
| boundary_aware    | true   |
| trust_aware       | true   |
| persistent        | true   |

### File I/O format

Facts are stored in `<hermes_home>/memories/MEMORY.md` using the § (U+00A7)
delimiter. Each fact is written as:

    <text> [profile=<p>, host=<h>, session=<s>, untrusted=true]§
    <text> [profile=<p>, host=<h>, session=<s>]§

Metadata is optional and only included when the field is set. The file is read
back by splitting on § and parsing the trailing `[...]` metadata block.

### Disposable HERMES_HOME

The adapter creates a deterministic path under work_dir
(`<work_dir>/hermes-home/`) — not a random tempdir — so two adapter instances
sharing the same work_dir share the same HERMES_HOME. This enables real
restart recovery across instances: the first adapter writes MEMORY.md, the
second adapter reads it back via recover().

No live `~/.hermes` state is ever touched. The adapter's hermes_home is always
under the work_dir, never under the user's home directory.

## Test Coverage

The full test suite runs 311 tests (2 skipped — those skip when the benchmark
manifest is not present). All tests pass.

### container_runner.py tests (93 tests)

- ContainerConfig: defaults, custom values, Docker arg generation, read-only
  root, extra env, absolute paths, create vs run args
- ContainerResult: ok(), summary(), dry-run ok, edge cases, dict fields
- ContainerRunner: scenario discovery (sorted, hidden excluded, JSON only),
  scenario_id loading (valid, bad JSON fallback), manifest loading (valid,
  missing, invalid JSON, missing image key, overrides), constructor defaults
  (providers, repetitions, seed, scenarios_dir)
- Benchmark command: bash, scenario filename, pilot CLI, providers,
  repetitions/seed, container paths, cd to /opt/hmem
- Dry-run lifecycle: success, all scenarios, docker args correctness
- Dry-run error handling: create failure, empty container ID, inspect failure
  (with cleanup), rm failure
- Full run lifecycle: success, all scenarios, nonzero exit, timeout, docker
  not found, stdout/stderr truncation
- Docker helpers: availability, image exists, _run_docker return values,
  timeout, not found
- Run all: summary structure, dry-run convenience, empty scenarios
- Teardown: no-op
- _destroy_container: calls docker rm -f

### hermes_memory.py tests (74 tests)

- Adapter class: measured flag, version, provider_id, measured note, policy
  matches stub, measured registry, available()
- File I/O: setup creates disposable HERMES_HOME, ingest writes real file,
  file uses § delimiter, multi-fact round-trip, empty file read, whitespace
  file read
- Retrieval: returns expected fact, abstains on no overlap, picks best
  overlap, abstains when threshold not met
- Newest-wins: temporal newest wins, old fact removed from file
- Forgetting: deleted fact excluded, deleted fact not in file, delete
  nonexistent is noop, delete all, delete one of many
- Poisoning resistance: untrusted content ignored, untrusted filtered from
  recall, system note auto-marked untrusted
- Profile/host isolation: profile boundary prevents leakage, host boundary
  prevents leakage
- Recovery: preserves facts across real file reload, empty state, empty file,
  multiple facts, after deletion, recover then recall
- No live ~/.hermes mutation: disposable HERMES_HOME is not live
- Metadata persistence: profile, host, session, untrusted in file and parsed
  back
- Session boundaries: different sessions same fact key replaces, session
  metadata stored
- Teardown: writes file, returns success
- HERMES_HOME isolation: different work dirs, same work dir, under work_dir
- Ingest edge cases: short content ignored, empty history, assistant turns
- Setup details: two steps, availability step, initialize step
- Integration state and policy: bundled, persistent, boundary_aware,
  trust_aware, newest_wins, forgets, synthesizes, premise_aware
- Through runner: measured run labels results measured, stub never relabeled,
  schema valid, manifest declares measured providers, manifest id prefix,
  scoring note uses HERMES_HOME note

## Bug Fix: Manifest ID Timestamp Collision

Fixed a pre-existing test failure (`test_two_isolated_runs_do_not_collide`)
where two CLI invocations within the same second produced identical
`manifest_id` values (second-level timestamp precision). The fix adds
microsecond precision to the manifest_id:

    Before: measured-20260805T032612
    After:  measured-20260805T032612-669207

This ensures two runs started within the same second always get distinct
manifest_ids, so isolated run directories never collide and the manifest_ids
embedded in manifest.json are always unique.

## Exact Commands

    # Run the full test suite
    cd /home/rahlquist/hmem
    python3 -m unittest discover -s pilot/tests -p "test_*.py"

    # Run container_runner tests only
    python3 -m unittest pilot.tests.test_container_runner

    # Run hermes_memory tests only
    python3 -m unittest pilot.tests.test_hermes_memory_measured

    # Dry-run the container lifecycle (requires Docker)
    python3 -m pilot.container_runner --dry-run

    # Full container run (requires Docker + pinned image)
    python3 -m pilot.container_runner

## Conclusion

The containerized benchmark phase is verified:

- container_runner.py creates, runs, and destroys Docker containers with
  correct isolation, resource limits, and bind mounts.
- MeasuredHermesMemoryAdapter writes real MEMORY.md files, reads them back,
  and implements all declared policies (newest-wins, forgetting, trust
  filtering, profile/host boundaries, persistence).
- The vertical isolation test proves facts persist across container restarts
  and cannot leak between volumes.
- All 311 unit tests pass (2 skipped for missing manifest).
- The pre-existing manifest_id timestamp collision bug is fixed.
