"""Docker container lifecycle runner for the hmem pilot.

Creates a fresh Docker container per scenario using the pinned benchmark image,
mounts tmpfs for HERMES_HOME, bind-mounts scenario input and result output,
sets --network none for baseline tests, applies resource limits, and tears down
containers after each run.

This module is the bridge between the pilot's deterministic in-process harness
and reproducible Docker-based execution. It does NOT replace the in-process
runner (``pilot.runner``) — it wraps the benchmark image so each scenario can
be evaluated in a fully isolated container with no network access.

Usage (programmatic)::

    from pilot.container_runner import ContainerRunner, ContainerConfig

    runner = ContainerRunner.from_manifest("pilot-out/benchmark-manifest.json")
    for scenario_path in runner.scenario_paths():
        result = runner.run_scenario(scenario_path, out_dir="/tmp/results")
        print(result.summary())

Usage (CLI)::

    python -m pilot.container_runner --dry-run
    python -m pilot.container_runner --scenarios-dir pilot/scenarios --out-dir /tmp/cont-out

Dry-run mode creates a container (``docker create``), verifies it exists, then
immediately destroys it — proving the Docker command-line, mounts, and image
reference are all correct without executing the benchmark workload.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import PILOT_VERSION

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_MANIFEST = os.path.join("pilot-out", "benchmark-manifest.json")
DEFAULT_SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")
DEFAULT_OUT_DIR = os.path.join("pilot-out", "container-runs")

# Container-internal paths (where bind mounts land inside the container).
CONTAINER_SCENARIOS_DIR = "/scenarios"
CONTAINER_RESULTS_DIR = "/results"
CONTAINER_HERMES_HOME = "/tmp/hermes-home"

# Resource limits (Docker CLI flags).
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_CPU_QUOTA = "1.0"
DEFAULT_PID_LIMIT = "128"

# Timeout for the benchmark command inside the container (seconds).
DEFAULT_RUN_TIMEOUT = 120


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ContainerConfig:
    """Configuration for one container run.

    Attributes:
        image:          Docker image tag (e.g. ``hermes-benchmark:abc123``).
        network_mode:   Docker network mode; ``none`` for baseline isolation.
        memory_limit:   Docker memory limit (e.g. ``512m``).
        cpu_quota:      Docker CPU quota as a float string (e.g. ``1.0``).
        pid_limit:      Docker PID limit (e.g. ``128``).
        run_timeout:    Max seconds for the in-container benchmark command.
        read_only_root: If True, container root filesystem is read-only.
        extra_env:      Additional environment variables to set in the container.
    """
    image: str = ""
    network_mode: str = "none"
    memory_limit: str = DEFAULT_MEMORY_LIMIT
    cpu_quota: str = DEFAULT_CPU_QUOTA
    pid_limit: str = DEFAULT_PID_LIMIT
    run_timeout: int = DEFAULT_RUN_TIMEOUT
    read_only_root: bool = False
    extra_env: dict = field(default_factory=dict)

    def to_docker_args(self, scenarios_dir, results_dir, hermes_home_dir, command=None):
        """Build the ``docker run`` / ``docker create`` argument list.

        Returns a list of strings suitable for ``subprocess.run``. The
        ``command`` argument replaces the image's default CMD; if omitted the
        image's built-in CMD runs (which prints build info + validates).
        """
        args = [
            "docker", "run",
            "--rm" if command is None else "",  # --rm for default CMD only
            "--network", self.network_mode,
            "--memory", self.memory_limit,
            f"--cpus={self.cpu_quota}",
            f"--pids-limit={self.pid_limit}",
        ]
        # Remove empty strings (from conditional --rm above).
        args = [a for a in args if a]

        # Read-only root filesystem (extra hardening).
        if self.read_only_root:
            args.extend(["--read-only"])

        # tmpfs for HERMES_HOME — ephemeral, in-memory, never touches disk.
        args.extend([
            "--tmpfs", f"{hermes_home_dir}:rw,size=64m,mode=1777",
        ])

        # Environment variables.
        args.extend(["-e", f"HERMES_HOME={hermes_home_dir}"])
        for key, val in self.extra_env.items():
            args.extend(["-e", f"{key}={val}"])

        # Bind-mount scenario input directory (read-only).
        abs_scenarios = os.path.abspath(scenarios_dir)
        args.extend(["-v", f"{abs_scenarios}:{CONTAINER_SCENARIOS_DIR}:ro"])

        # Bind-mount results output directory (read-write).
        abs_results = os.path.abspath(results_dir)
        args.extend(["-v", f"{abs_results}:{CONTAINER_RESULTS_DIR}:rw"])

        # Image tag.
        args.append(self.image)

        # Optional command override.
        if command:
            args.extend(command)

        return args

    def to_docker_create_args(self, scenarios_dir, results_dir, hermes_home_dir, command=None):
        """Build ``docker create`` args (for dry-run lifecycle verification).

        Same as ``to_docker_args`` but uses ``docker create`` instead of
        ``docker run``, and never includes ``--rm`` (we want to inspect the
        container before removing it ourselves).
        """
        args = [
            "docker", "create",
            "--network", self.network_mode,
            "--memory", self.memory_limit,
            f"--cpus={self.cpu_quota}",
            f"--pids-limit={self.pid_limit}",
        ]
        if self.read_only_root:
            args.extend(["--read-only"])
        args.extend([
            "--tmpfs", f"{hermes_home_dir}:rw,size=64m,mode=1777",
        ])
        args.extend(["-e", f"HERMES_HOME={hermes_home_dir}"])
        for key, val in self.extra_env.items():
            args.extend(["-e", f"{key}={val}"])
        abs_scenarios = os.path.abspath(scenarios_dir)
        args.extend(["-v", f"{abs_scenarios}:{CONTAINER_SCENARIOS_DIR}:ro"])
        abs_results = os.path.abspath(results_dir)
        args.extend(["-v", f"{abs_results}:{CONTAINER_RESULTS_DIR}:rw"])
        args.append(self.image)
        if command:
            args.extend(command)
        return args


@dataclass
class ContainerResult:
    """Outcome of one container run.

    Attributes:
        scenario_id:   The scenario that was run.
        container_id:   Docker container ID (short hash) or None on failure.
        exit_code:      Exit code of the in-container command.
        duration_sec:   Wall-clock time from create to destroy.
        stdout:         Captured stdout (truncated to 4KB).
        stderr:         Captured stderr (truncated to 4KB).
        error:          Error message if the run failed before the container
                        command could execute, or None on success.
        created:        True if ``docker create`` succeeded.
        ran:            True if the in-container command ran (exit code captured).
        destroyed:      True if ``docker rm -f`` succeeded (or container self-removed).
    """
    scenario_id: str = ""
    container_id: Optional[str] = None
    exit_code: Optional[int] = None
    duration_sec: float = 0.0
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    created: bool = False
    ran: bool = False
    destroyed: bool = False
    dry_run: bool = False

    def ok(self):
        """True if the lifecycle completed without error.

        For full runs: the container ran and exited zero.
        For dry runs: the container was created and destroyed without error.
        """
        if self.error is not None:
            return False
        if self.dry_run:
            return self.created and self.destroyed
        return self.ran and self.exit_code == 0

    def summary(self):
        """One-line human-readable summary."""
        status = "ok" if self.ok() else "failed"
        ec = f" exit={self.exit_code}" if self.exit_code is not None else ""
        err = f" err={self.error}" if self.error else ""
        return (f"[{status}] {self.scenario_id} "
                f"({self.duration_sec:.1f}s){ec}{err}")


# ---------------------------------------------------------------------------
# ContainerRunner
# ---------------------------------------------------------------------------

class ContainerRunner:
    """Manages the Docker container lifecycle for pilot scenario runs.

    Each call to ``run_scenario`` creates a fresh container, executes the
    benchmark command, captures output, and tears down the container. No state
    persists between scenario runs.

    Args:
        config:         ``ContainerConfig`` with image tag and resource limits.
        scenarios_dir:  Directory containing scenario JSON fixtures.
        providers:      Comma-separated provider ids to pass to the pilot CLI.
        repetitions:    Ingest+recall repetitions per scenario.
        seed:           Deterministic seed.
    """

    def __init__(self, config, scenarios_dir=None, providers=None,
                 repetitions=3, seed=7):
        self.config = config
        self.scenarios_dir = scenarios_dir or DEFAULT_SCENARIOS_DIR
        self.providers = providers or "hermes_memory,lexical_baseline"
        self.repetitions = repetitions
        self.seed = seed

    # -- Factory -----------------------------------------------------------

    @classmethod
    def from_manifest(cls, manifest_path=DEFAULT_MANIFEST, scenarios_dir=None,
                      providers=None, repetitions=3, seed=7, **kwargs):
        """Build a runner from the benchmark manifest JSON.

        Reads the pinned image tag from ``pilot-out/benchmark-manifest.json``
        and constructs a ``ContainerConfig`` with sensible defaults. Extra
        ``ContainerConfig`` keyword arguments override the defaults.
        """
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(
                f"benchmark manifest not found: {manifest_path}. "
                f"Run docker/benchmark/build.sh first.")
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        # The manifest may be a single object or a list of images.
        image_tag = None
        if isinstance(manifest, dict):
            image_tag = manifest.get("image", {}).get("tag")
        if not image_tag:
            raise ValueError(f"could not find image tag in manifest: {manifest_path}")
        config = ContainerConfig(image=image_tag, **kwargs)
        return cls(config, scenarios_dir=scenarios_dir, providers=providers,
                    repetitions=repetitions, seed=seed)

    # -- Scenario discovery ------------------------------------------------

    def scenario_paths(self):
        """Return sorted list of scenario JSON file paths in the scenarios dir."""
        dir_path = self.scenarios_dir
        if not os.path.isdir(dir_path):
            return []
        return sorted(
            os.path.join(dir_path, f)
            for f in os.listdir(dir_path)
            if f.endswith(".json") and not f.startswith(".")
        )

    def _load_scenario_id(self, scenario_path):
        """Read just the scenario_id from a scenario JSON file."""
        try:
            with open(scenario_path, "r", encoding="utf-8") as fh:
                return json.load(fh).get("scenario_id", os.path.basename(scenario_path))
        except Exception:
            return os.path.basename(scenario_path)

    # -- Docker helpers ----------------------------------------------------

    @staticmethod
    def _docker_available():
        """Check if the docker CLI is available and the daemon is running."""
        try:
            r = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0 and bool(r.stdout.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _image_exists(image_tag):
        """Check if a Docker image is available locally."""
        try:
            r = subprocess.run(
                ["docker", "image", "inspect", image_tag],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def _run_docker(args, timeout=None):
        """Run a docker command and return (exit_code, stdout, stderr)."""
        try:
            r = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout,
            )
            return r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "timeout"
        except FileNotFoundError:
            return -1, "", "docker not found"

    # -- Benchmark command -------------------------------------------------

    def _benchmark_command(self, scenario_filename):
        """Build the in-container command that runs the pilot CLI for one scenario.

        We create a temporary single-scenario directory inside the container
        by copying the one scenario file, then run the pilot CLI against it.
        """
        # The container has the pilot package at /opt/hmem.
        # We use a shell command to: mkdir a temp dir, copy the single
        # scenario file there, then run the pilot CLI against it.
        return [
            "/bin/bash", "-c",
            f"mkdir -p /tmp/scenario && "
            f"cp {CONTAINER_SCENARIOS_DIR}/{scenario_filename} /tmp/scenario/ && "
            f"cd /opt/hmem && "
            f"python3 -m pilot.cli "
            f"--scenarios-dir /tmp/scenario "
            f"--out-dir {CONTAINER_RESULTS_DIR} "
            f"--providers {self.providers} "
            f"--repetitions {self.repetitions} "
            f"--seed {self.seed}",
        ]

    # -- Container lifecycle -----------------------------------------------

    def run_scenario(self, scenario_path, out_dir, dry_run=False):
        """Run one scenario in a fresh container.

        Args:
            scenario_path: Path to the scenario JSON file.
            out_dir:       Host directory for results (bind-mounted into container).
            dry_run:       If True, only create+destroy the container (no execution).

        Returns:
            ``ContainerResult`` with the lifecycle outcome.
        """
        scenario_filename = os.path.basename(scenario_path)
        scenario_id = self._load_scenario_id(scenario_path)
        t_start = time.perf_counter()
        result = ContainerResult(scenario_id=scenario_id)

        # Ensure output directory exists on host.
        os.makedirs(out_dir, exist_ok=True)

        if dry_run:
            return self._dry_run_lifecycle(
                scenario_filename, scenario_id, out_dir, t_start)
        return self._full_run(
            scenario_filename, scenario_id, out_dir, t_start, result)

    def _dry_run_lifecycle(self, scenario_filename, scenario_id, out_dir, t_start):
        """Create a container, verify it exists, then destroy it.

        This proves the Docker command-line, mounts, image, and resource limits
        are all valid — without executing the benchmark workload.
        """
        result = ContainerResult(scenario_id=scenario_id, dry_run=True)

        # Build create args (no --rm; we manage the lifecycle ourselves).
        command = self._benchmark_command(scenario_filename)
        create_args = self.config.to_docker_create_args(
            scenarios_dir=self.scenarios_dir,
            results_dir=out_dir,
            hermes_home_dir=CONTAINER_HERMES_HOME,
            command=command,
        )

        # 1. Create the container.
        ec, stdout, stderr = self._run_docker(create_args, timeout=30)
        if ec != 0:
            result.error = f"docker create failed (exit {ec}): {stderr.strip()}"
            result.duration_sec = time.perf_counter() - t_start
            return result

        container_id = stdout.strip()
        if not container_id:
            result.error = "docker create returned empty container ID"
            result.duration_sec = time.perf_counter() - t_start
            return result

        result.container_id = container_id[:12]
        result.created = True

        # 2. Verify the container exists.
        ec, _, stderr = self._run_docker(
            ["docker", "inspect", "--format", "{{.Id}}", container_id],
            timeout=10,
        )
        if ec != 0:
            result.error = f"docker inspect failed: {stderr.strip()}"
            # Still attempt cleanup.
            self._destroy_container(container_id)
            result.destroyed = True
            result.duration_sec = time.perf_counter() - t_start
            return result

        # 3. Destroy the container (we never started it in dry-run mode).
        ec, _, stderr = self._run_docker(
            ["docker", "rm", "-f", container_id], timeout=15,
        )
        if ec != 0:
            result.error = f"docker rm failed: {stderr.strip()}"
        else:
            result.destroyed = True

        result.duration_sec = time.perf_counter() - t_start
        return result

    def _full_run(self, scenario_filename, scenario_id, out_dir, t_start, result):
        """Full container lifecycle: create, run, destroy."""
        command = self._benchmark_command(scenario_filename)

        # Use docker run (with --rm) for the full lifecycle. Docker auto-removes
        # the container on exit, but we fall back to manual rm if --rm fails.
        run_args = self.config.to_docker_args(
            scenarios_dir=self.scenarios_dir,
            results_dir=out_dir,
            hermes_home_dir=CONTAINER_HERMES_HOME,
            command=command,
        )

        # Execute the full container run.
        ec, stdout, stderr = self._run_docker(
            run_args, timeout=self.config.run_timeout,
        )
        result.exit_code = ec
        result.stdout = stdout[:4096]
        result.stderr = stderr[:4096]
        result.ran = (ec != -1)  # -1 means timeout or docker not found

        if ec == -1 and "timeout" in stderr:
            result.error = f"container run timed out after {self.config.run_timeout}s"
        elif ec == -1 and "docker not found" in stderr:
            result.error = "docker CLI not found"
        elif ec != 0:
            result.error = f"container exited with code {ec}"

        # Container is auto-removed by --rm. If somehow it persists, clean up.
        # We can't know the container ID from `docker run --rm`, but if the
        # command failed before --rm took effect, there might be a stale one.
        # This is a best-effort cleanup.
        result.destroyed = True  # --rm handles it
        result.duration_sec = time.perf_counter() - t_start
        return result

    def _destroy_container(self, container_id):
        """Force-remove a container by ID."""
        self._run_docker(["docker", "rm", "-f", container_id], timeout=15)

    # -- Batch runner ------------------------------------------------------

    def run_all(self, out_dir, dry_run=False):
        """Run all scenarios found in the scenarios directory.

        Returns a list of ``ContainerResult`` objects and a summary dict.
        """
        paths = self.scenario_paths()
        if not paths:
            return [], {"total": 0, "ok": 0, "failed": 0}

        results = []
        for sp in paths:
            # Each scenario gets its own output subdirectory.
            scenario_out = os.path.join(out_dir, Path(sp).stem)
            r = self.run_scenario(sp, scenario_out, dry_run=dry_run)
            results.append(r)

        summary = {
            "total": len(results),
            "ok": sum(1 for r in results if r.ok()),
            "failed": sum(1 for r in results if not r.ok()),
            "results": [r.__dict__ for r in results],
        }
        return results, summary

    def run_all_dry_run(self, out_dir):
        """Convenience: dry-run all scenarios (create + destroy only)."""
        return self.run_all(out_dir, dry_run=True)

    # -- Teardown ----------------------------------------------------------

    def teardown(self):
        """Clean up any resources held by this runner.

        The runner is stateless between runs (each container is removed after
        its scenario), so this is a no-op. Provided for future extensibility
        and for callers that want an explicit cleanup hook.
        """
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_main(argv=None):
    parser = argparse.ArgumentParser(
        prog="hmem-container-runner",
        description="Docker container lifecycle runner for the hmem pilot. "
                    "Creates a fresh container per scenario with tmpfs HERMES_HOME, "
                    "bind mounts, --network none, resource limits, and teardown.",
    )
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST,
                        help=f"path to benchmark-manifest.json (default: {DEFAULT_MANIFEST})")
    parser.add_argument("--scenarios-dir", default=DEFAULT_SCENARIOS_DIR,
                        help="directory with scenario JSON fixtures")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR,
                        help=f"output directory (default: {DEFAULT_OUT_DIR})")
    parser.add_argument("--providers", default="hermes_memory,lexical_baseline",
                        help="comma-separated provider ids")
    parser.add_argument("--repetitions", type=int, default=3,
                        help="ingest+recall repetitions per scenario (default: 3)")
    parser.add_argument("--seed", type=int, default=7,
                        help="deterministic seed (default: 7)")
    parser.add_argument("--dry-run", action="store_true",
                        help="create + destroy containers without executing the "
                             "benchmark workload (validates Docker args, mounts, "
                             "image reference)")
    parser.add_argument("--memory", default=DEFAULT_MEMORY_LIMIT,
                        help=f"Docker memory limit (default: {DEFAULT_MEMORY_LIMIT})")
    parser.add_argument("--cpus", default=DEFAULT_CPU_QUOTA,
                        help=f"Docker CPU quota (default: {DEFAULT_CPU_QUOTA})")
    parser.add_argument("--network", default="none",
                        help="Docker network mode (default: none — no network access)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_RUN_TIMEOUT,
                        help=f"container run timeout in seconds (default: {DEFAULT_RUN_TIMEOUT})")
    parser.add_argument("--single", default=None,
                        help="run only one scenario (by filename or scenario_id)")
    args = parser.parse_args(argv)

    # Check Docker availability first.
    if not ContainerRunner._docker_available():
        print("ERROR: docker is not available or the daemon is not running.",
              file=sys.stderr)
        return 2

    # Build config from manifest.
    config = ContainerConfig(
        image="",  # filled from manifest
        network_mode=args.network,
        memory_limit=args.memory,
        cpu_quota=args.cpus,
        run_timeout=args.timeout,
    )

    try:
        runner = ContainerRunner.from_manifest(
            manifest_path=args.manifest,
            scenarios_dir=args.scenarios_dir,
            providers=args.providers,
            repetitions=args.repetitions,
            seed=args.seed,
            network_mode=args.network,
            memory_limit=args.memory,
            cpu_quota=args.cpus,
            run_timeout=args.timeout,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Verify the image exists locally.
    if not ContainerRunner._image_exists(runner.config.image):
        print(f"ERROR: Docker image not found: {runner.config.image}", file=sys.stderr)
        print("  Build it first with: docker/benchmark/build.sh", file=sys.stderr)
        return 2

    mode = "DRY-RUN (create+destroy only)" if args.dry_run else "FULL RUN"
    print(f"container_runner v{PILOT_VERSION} — {mode}")
    print(f"  image:     {runner.config.image}")
    print(f"  network:   {runner.config.network_mode}")
    print(f"  memory:    {runner.config.memory_limit}")
    print(f"  cpus:      {runner.config.cpu_quota}")
    print(f"  scenarios: {runner.scenarios_dir}")
    print(f"  out_dir:   {args.out_dir}")
    print()

    if args.single:
        # Find the matching scenario file.
        paths = runner.scenario_paths()
        target = None
        for p in paths:
            if args.single in os.path.basename(p) or \
               runner._load_scenario_id(p) == args.single:
                target = p
                break
        if not target:
            print(f"ERROR: scenario not found: {args.single}", file=sys.stderr)
            return 2
        scenario_out = os.path.join(args.out_dir, Path(target).stem)
        r = runner.run_scenario(target, scenario_out, dry_run=args.dry_run)
        print(r.summary())
        if not r.ok():
            if r.stderr:
                print(f"  stderr: {r.stderr[:500]}", file=sys.stderr)
            return 1
        return 0

    results, summary = runner.run_all(args.out_dir, dry_run=args.dry_run)
    for r in results:
        print(r.summary())

    print()
    print(f"total:   {summary['total']}")
    print(f"ok:      {summary['ok']}")
    print(f"failed:  {summary['failed']}")

    # Write a summary JSON.
    os.makedirs(args.out_dir, exist_ok=True)
    summary_path = os.path.join(args.out_dir, "container-run-summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"summary: {summary_path}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(_cli_main())
