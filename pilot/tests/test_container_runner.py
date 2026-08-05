"""Tests for pilot.container_runner: container lifecycle, config, dry-run.

These tests use subprocess mocking so they run without a real Docker daemon.
The acceptance criterion — a dry-run of the container lifecycle (create,
inspect, destroy) succeeds for at least one scenario — is covered by
``TestDryRunLifecycle``.
"""
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

import pilot.container_runner as cr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENARIOS_DIR = os.path.join(ROOT, "scenarios")
MANIFEST_PATH = os.path.join(ROOT, "pilot-out", "benchmark-manifest.json")


def _fake_subprocess_run(args, capture_output=True, text=True, timeout=None, **kw):
    """Mock subprocess.run that simulates docker CLI responses."""
    class FakeResult:
        def __init__(self, code, out, err):
            self.returncode = code
            self.stdout = out
            self.stderr = err
            # Match real subprocess.run behavior: args is available
            self.args = args

    cmd = args[0] if args else ""
    if len(args) >= 2:
        sub = args[1]
    else:
        sub = ""

    if cmd == "docker":
        if sub == "info":
            # Docker daemon is running.
            return FakeResult(0, "27.0.0\n", "")
        if sub == "image" and len(args) >= 3 and args[2] == "inspect":
            return FakeResult(0, "[]\n", "")
        if sub == "create":
            # Return a fake container ID (64 hex chars, like real docker).
            return FakeResult(0, "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n", "")
        if sub == "inspect":
            # Verify container exists — return the full ID.
            return FakeResult(0, "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n", "")
        if sub == "rm":
            return FakeResult(0, "a1b2c3d4e5f6\n", "")
        if sub == "run":
            # Simulate a successful benchmark run.
            return FakeResult(0, "pilot v0.1.0 OK\nmanifest: dryrun-...\n", "")

    # Default: not found.
    raise FileNotFoundError(f"command not found: {cmd}")


class TestContainerConfig(unittest.TestCase):
    """ContainerConfig dataclass: defaults, Docker arg generation."""

    def test_defaults(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        self.assertEqual(cfg.network_mode, "none")
        self.assertEqual(cfg.memory_limit, "512m")
        self.assertEqual(cfg.cpu_quota, "1.0")
        self.assertEqual(cfg.pid_limit, "128")
        self.assertEqual(cfg.run_timeout, 120)
        self.assertFalse(cfg.read_only_root)
        self.assertEqual(cfg.extra_env, {})

    def test_to_docker_args_includes_network_none(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        self.assertIn("--network", args)
        idx = args.index("--network")
        self.assertEqual(args[idx + 1], "none")

    def test_to_docker_args_includes_memory_limit(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test", memory_limit="256m")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        self.assertIn("--memory", args)
        idx = args.index("--memory")
        self.assertEqual(args[idx + 1], "256m")

    def test_to_docker_args_includes_cpu_quota(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test", cpu_quota="0.5")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        self.assertIn("--cpus=0.5", args)

    def test_to_docker_args_includes_pid_limit(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        self.assertIn("--pids-limit=128", args)

    def test_to_docker_args_includes_tmpfs_hermes_home(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        self.assertIn("--tmpfs", args)
        idx = args.index("--tmpfs")
        tmpfs_arg = args[idx + 1]
        self.assertIn("/tmp/hermes-home", tmpfs_arg)
        self.assertIn("rw", tmpfs_arg)

    def test_to_docker_args_includes_hermes_home_env(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        self.assertIn("-e", args)
        # Find HERMES_HOME=...
        env_args = [args[i + 1] for i, a in enumerate(args) if a == "-e"]
        hermes_env = [e for e in env_args if e.startswith("HERMES_HOME=")]
        self.assertTrue(hermes_env)
        self.assertIn("/tmp/hermes-home", hermes_env[0])

    def test_to_docker_args_includes_bind_mounts(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        # Find -v args
        vol_args = [args[i + 1] for i, a in enumerate(args) if a == "-v"]
        self.assertTrue(any(":ro" in v for v in vol_args),
                        "scenarios dir should be mounted read-only")
        self.assertTrue(any(":rw" in v for v in vol_args),
                        "results dir should be mounted read-write")

    def test_to_docker_args_includes_image(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:abc123")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        self.assertIn("hermes-benchmark:abc123", args)

    def test_to_docker_args_includes_command_when_given(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        cmd = ["/bin/bash", "-c", "echo hello"]
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home", command=cmd)
        # The command elements should appear after the image tag
        img_idx = args.index("hermes-benchmark:test")
        rest = args[img_idx + 1:]
        self.assertIn("/bin/bash", rest)
        self.assertIn("echo hello", rest)

    def test_to_docker_args_rm_only_without_command(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        self.assertIn("--rm", args)

    def test_to_docker_args_no_rm_with_command(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home",
                                  command=["echo", "hi"])
        self.assertNotIn("--rm", args)

    def test_to_docker_create_args_never_has_rm(self):
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        args = cfg.to_docker_create_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home",
                                         command=["echo", "hi"])
        self.assertNotIn("--rm", args)
        self.assertIn("create", args)

    def test_read_only_root(self):
        cfg = cr.ContainerConfig(image="test:latest", read_only_root=True)
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        self.assertIn("--read-only", args)

    def test_extra_env(self):
        cfg = cr.ContainerConfig(image="test:latest",
                                  extra_env={"FOO": "bar", "BAZ": "qux"})
        args = cfg.to_docker_args("/tmp/scen", "/tmp/out", "/tmp/hermes-home")
        env_args = [args[i + 1] for i, a in enumerate(args) if a == "-e"]
        self.assertIn("FOO=bar", env_args)
        self.assertIn("BAZ=qux", env_args)


class TestContainerResult(unittest.TestCase):
    """ContainerResult: ok(), summary()."""

    def test_ok_on_success(self):
        r = cr.ContainerResult(scenario_id="test-001", exit_code=0, ran=True)
        self.assertTrue(r.ok())

    def test_ok_false_on_failure(self):
        r = cr.ContainerResult(scenario_id="test-001", exit_code=1, ran=True)
        self.assertFalse(r.ok())

    def test_ok_false_on_error(self):
        r = cr.ContainerResult(scenario_id="test-001", exit_code=0, ran=True,
                                error="something went wrong")
        self.assertFalse(r.ok())

    def test_ok_false_when_not_ran(self):
        r = cr.ContainerResult(scenario_id="test-001", ran=False)
        self.assertFalse(r.ok())

    def test_summary_success(self):
        r = cr.ContainerResult(scenario_id="test-001", exit_code=0, ran=True,
                                duration_sec=1.5)
        s = r.summary()
        self.assertIn("[ok]", s)
        self.assertIn("test-001", s)
        self.assertIn("exit=0", s)

    def test_summary_failure(self):
        r = cr.ContainerResult(scenario_id="test-001", exit_code=1, ran=True,
                                error="bad stuff")
        s = r.summary()
        self.assertIn("[failed]", s)
        self.assertIn("err=bad stuff", s)


class TestContainerRunnerDiscovery(unittest.TestCase):
    """ContainerRunner: scenario discovery, manifest loading."""

    def test_scenario_paths_finds_scenarios(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        paths = runner.scenario_paths()
        self.assertGreater(len(paths), 0)
        self.assertTrue(all(p.endswith(".json") for p in paths))

    def test_scenario_paths_nonexistent_dir(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir="/nonexistent/path",
        )
        self.assertEqual(runner.scenario_paths(), [])

    def test_load_scenario_id(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        paths = runner.scenario_paths()
        sid = runner._load_scenario_id(paths[0])
        self.assertTrue(sid)


class TestContainerRunnerFromManifest(unittest.TestCase):
    """ContainerRunner.from_manifest: manifest parsing."""

    def test_from_manifest_reads_image_tag(self):
        if not os.path.exists(MANIFEST_PATH):
            self.skipTest("benchmark-manifest.json not found; run build.sh first")
        runner = cr.ContainerRunner.from_manifest(
            manifest_path=MANIFEST_PATH,
            scenarios_dir=SCENARIOS_DIR,
        )
        self.assertTrue(runner.config.image)
        self.assertTrue(runner.config.image.startswith("hermes-benchmark:"))

    def test_from_manifest_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            cr.ContainerRunner.from_manifest(manifest_path="/nonexistent/manifest.json")


class TestDryRunLifecycle(unittest.TestCase):
    """Acceptance: dry-run of the container lifecycle (create, inspect, destroy)
    succeeds for at least one scenario.

    Uses subprocess mocking so the test runs without a real Docker daemon.
    """

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_dry_run_lifecycle_one_scenario(self, mock_run):
        """A single scenario: docker create -> inspect -> rm succeeds."""
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        self.assertGreater(len(paths), 0, "need at least one scenario fixture")

        out_dir = tempfile.mkdtemp(prefix="cont-test-")
        result = runner.run_scenario(paths[0], out_dir, dry_run=True)

        self.assertTrue(result.created, "container should be created")
        self.assertTrue(result.destroyed, "container should be destroyed")
        self.assertIsNone(result.error, f"unexpected error: {result.error}")
        self.assertTrue(result.container_id)
        self.assertGreater(result.duration_sec, 0)

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_dry_run_all_scenarios(self, mock_run):
        """Dry-run all scenarios: every one creates and destroys cleanly."""
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        out_dir = tempfile.mkdtemp(prefix="cont-test-")
        results, summary = runner.run_all(out_dir, dry_run=True)

        self.assertGreater(summary["total"], 0)
        self.assertEqual(summary["ok"], summary["total"],
                         "all scenarios should pass dry-run lifecycle")
        self.assertEqual(summary["failed"], 0)
        for r in results:
            self.assertTrue(r.created)
            self.assertTrue(r.destroyed)

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_dry_run_docker_args_correct(self, mock_run):
        """Verify the docker create command has all required flags."""
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp(prefix="cont-test-")
        runner.run_scenario(paths[0], out_dir, dry_run=True)

        # Check the docker create call was made with correct arguments.
        create_calls = [
            c for c in mock_run.call_args_list
            if c.args and len(c.args) >= 1 and isinstance(c.args[0], list)
            and c.args[0][:2] == ["docker", "create"]
        ]
        self.assertTrue(create_calls, "docker create should have been called")
        create_args = create_calls[0].args[0]
        self.assertIn("--network", create_args)
        net_idx = create_args.index("--network")
        self.assertEqual(create_args[net_idx + 1], "none")
        self.assertIn("--memory", create_args)
        self.assertIn("--tmpfs", create_args)
        self.assertIn("-e", create_args)
        self.assertIn("hermes-benchmark:test", create_args)


class TestFullRunLifecycle(unittest.TestCase):
    """Full container run lifecycle (mocked docker run)."""

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_full_run_one_scenario(self, mock_run):
        """Full run: docker run --rm with benchmark command succeeds."""
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp(prefix="cont-test-")
        result = runner.run_scenario(paths[0], out_dir, dry_run=False)

        self.assertTrue(result.ran, "container should have run")
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.destroyed, "container should be destroyed (via --rm)")
        self.assertTrue(result.ok())
        self.assertGreater(result.duration_sec, 0)

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_full_run_all_scenarios(self, mock_run):
        """Full run all scenarios: all exit zero."""
        cfg = cr.ContainerConfig(image="hermes-benchmark:test")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        out_dir = tempfile.mkdtemp(prefix="cont-test-")
        results, summary = runner.run_all(out_dir, dry_run=False)
        self.assertGreater(summary["total"], 0)
        self.assertEqual(summary["ok"], summary["total"])


class TestDockerAvailability(unittest.TestCase):
    """Docker availability checks (mocked)."""

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_docker_available_true(self, mock_run):
        self.assertTrue(cr.ContainerRunner._docker_available())

    @mock.patch("subprocess.run", side_effect=FileNotFoundError("docker"))
    def test_docker_available_false_no_binary(self, mock_run):
        self.assertFalse(cr.ContainerRunner._docker_available())

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_image_exists_true(self, mock_run):
        self.assertTrue(cr.ContainerRunner._image_exists("hermes-benchmark:test"))


class TestTeardown(unittest.TestCase):
    """Runner teardown is a safe no-op."""

    def test_teardown_no_op(self):
        runner = cr.ContainerRunner(cr.ContainerConfig(image="test:latest"),
                                     scenarios_dir=SCENARIOS_DIR)
        runner.teardown()  # should not raise


# ---------------------------------------------------------------------------
# Extended tests: edge cases, error handling, CLI, benchmark command.
# ---------------------------------------------------------------------------

class TestContainerConfigEdgeCases(unittest.TestCase):
    """ContainerConfig: custom values, boundary conditions."""

    def test_custom_network_mode(self):
        cfg = cr.ContainerConfig(image="test:latest", network_mode="bridge")
        args = cfg.to_docker_args("/tmp/s", "/tmp/o", "/tmp/h")
        idx = args.index("--network")
        self.assertEqual(args[idx + 1], "bridge")

    def test_custom_memory_limit(self):
        cfg = cr.ContainerConfig(image="test:latest", memory_limit="2g")
        args = cfg.to_docker_args("/tmp/s", "/tmp/o", "/tmp/h")
        idx = args.index("--memory")
        self.assertEqual(args[idx + 1], "2g")

    def test_custom_cpu_quota(self):
        cfg = cr.ContainerConfig(image="test:latest", cpu_quota="2.0")
        args = cfg.to_docker_args("/tmp/s", "/tmp/o", "/tmp/h")
        self.assertIn("--cpus=2.0", args)

    def test_custom_pid_limit(self):
        cfg = cr.ContainerConfig(image="test:latest", pid_limit="256")
        args = cfg.to_docker_args("/tmp/s", "/tmp/o", "/tmp/h")
        self.assertIn("--pids-limit=256", args)

    def test_custom_run_timeout(self):
        cfg = cr.ContainerConfig(image="test:latest", run_timeout=300)
        self.assertEqual(cfg.run_timeout, 300)

    def test_empty_image_tag(self):
        """An empty image tag is valid dataclass state (validation is at runtime)."""
        cfg = cr.ContainerConfig(image="")
        self.assertEqual(cfg.image, "")

    def test_to_docker_args_absolute_paths(self):
        """Bind mounts should use absolute paths."""
        cfg = cr.ContainerConfig(image="test:latest")
        args = cfg.to_docker_args("relative/scenarios", "relative/out",
                                  "/tmp/hermes-home")
        vol_args = [args[i + 1] for i, a in enumerate(args) if a == "-v"]
        for v in vol_args:
            # The host-side path (before the colon) should be absolute
            host_path = v.split(":")[0]
            self.assertTrue(os.path.isabs(host_path),
                            f"host path {host_path} should be absolute, got: {v}")

    def test_to_docker_create_args_matches_run_except_no_rm(self):
        """docker create args should have same content as docker run minus --rm."""
        cfg = cr.ContainerConfig(image="test:latest")
        run_args = cfg.to_docker_args("/tmp/s", "/tmp/o", "/tmp/h",
                                      command=["echo", "hi"])
        create_args = cfg.to_docker_create_args("/tmp/s", "/tmp/o", "/tmp/h",
                                                command=["echo", "hi"])
        # create should not have --rm
        self.assertNotIn("--rm", create_args)
        # create should have 'create' not 'run'
        self.assertIn("create", create_args)
        self.assertIn("run", run_args)
        # Both should reference the image
        self.assertIn("test:latest", create_args)
        self.assertIn("test:latest", run_args)

    def test_read_only_root_in_create_args(self):
        cfg = cr.ContainerConfig(image="test:latest", read_only_root=True)
        args = cfg.to_docker_create_args("/tmp/s", "/tmp/o", "/tmp/h")
        self.assertIn("--read-only", args)

    def test_extra_env_in_create_args(self):
        cfg = cr.ContainerConfig(
            image="test:latest",
            extra_env={"DEBUG": "1", "LOG_LEVEL": "warn"},
        )
        args = cfg.to_docker_create_args("/tmp/s", "/tmp/o", "/tmp/h")
        env_args = [args[i + 1] for i, a in enumerate(args) if a == "-e"]
        self.assertIn("DEBUG=1", env_args)
        self.assertIn("LOG_LEVEL=warn", env_args)


class TestContainerResultEdgeCases(unittest.TestCase):
    """ContainerResult: dry-run ok, edge cases."""

    def test_dry_run_ok(self):
        r = cr.ContainerResult(scenario_id="s1", dry_run=True,
                                created=True, destroyed=True)
        self.assertTrue(r.ok())

    def test_dry_run_not_ok_without_created(self):
        r = cr.ContainerResult(scenario_id="s1", dry_run=True,
                                created=False, destroyed=True)
        self.assertFalse(r.ok())

    def test_dry_run_not_ok_without_destroyed(self):
        r = cr.ContainerResult(scenario_id="s1", dry_run=True,
                                created=True, destroyed=False)
        self.assertFalse(r.ok())

    def test_summary_dry_run(self):
        r = cr.ContainerResult(scenario_id="dry-1", dry_run=True,
                                created=True, destroyed=True, duration_sec=0.5)
        s = r.summary()
        self.assertIn("[ok]", s)
        self.assertIn("dry-1", s)

    def test_summary_no_exit_code(self):
        r = cr.ContainerResult(scenario_id="s2", ran=False)
        s = r.summary()
        self.assertIn("[failed]", s)
        # exit= should NOT appear when exit_code is None
        self.assertNotIn("exit=", s)

    def test_ok_with_nonzero_exit(self):
        r = cr.ContainerResult(scenario_id="s3", exit_code=42, ran=True)
        self.assertFalse(r.ok())

    def test_result_dict_fields(self):
        r = cr.ContainerResult(scenario_id="s4", exit_code=0, ran=True,
                                duration_sec=1.2, stdout="hello",
                                stderr="world")
        d = r.__dict__
        self.assertEqual(d["scenario_id"], "s4")
        self.assertEqual(d["exit_code"], 0)
        self.assertEqual(d["stdout"], "hello")
        self.assertEqual(d["stderr"], "world")
        self.assertTrue(d["ran"])
        self.assertFalse(d["dry_run"])


class TestBenchmarkCommand(unittest.TestCase):
    """ContainerRunner._benchmark_command: structure and content."""

    def test_command_uses_bash(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        cmd = runner._benchmark_command("scenario-001.json")
        self.assertEqual(cmd[0], "/bin/bash")
        self.assertEqual(cmd[1], "-c")

    def test_command_includes_scenario_filename(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        cmd = runner._benchmark_command("my-scenario.json")
        self.assertIn("my-scenario.json", cmd[2])

    def test_command_includes_pilot_cli(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        cmd = runner._benchmark_command("s.json")
        self.assertIn("python3 -m pilot.cli", cmd[2])

    def test_command_includes_providers(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
            providers="hermes_memory,lexical_baseline",
        )
        cmd = runner._benchmark_command("s.json")
        self.assertIn("--providers hermes_memory,lexical_baseline", cmd[2])

    def test_command_includes_repetitions_and_seed(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
            repetitions=5, seed=42,
        )
        cmd = runner._benchmark_command("s.json")
        self.assertIn("--repetitions 5", cmd[2])
        self.assertIn("--seed 42", cmd[2])

    def test_command_uses_container_paths(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        cmd = runner._benchmark_command("s.json")
        self.assertIn(cr.CONTAINER_SCENARIOS_DIR, cmd[2])
        self.assertIn(cr.CONTAINER_RESULTS_DIR, cmd[2])

    def test_command_cd_to_hmem(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        cmd = runner._benchmark_command("s.json")
        self.assertIn("cd /opt/hmem", cmd[2])


class TestScenarioDiscovery(unittest.TestCase):
    """ContainerRunner scenario discovery edge cases."""

    def test_scenario_paths_sorted(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        paths = runner.scenario_paths()
        self.assertEqual(paths, sorted(paths))

    def test_scenario_paths_excludes_hidden(self):
        """Hidden files (starting with .) should not be in scenario paths."""
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        paths = runner.scenario_paths()
        for p in paths:
            self.assertFalse(os.path.basename(p).startswith("."))

    def test_scenario_paths_excludes_non_json(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        paths = runner.scenario_paths()
        for p in paths:
            self.assertTrue(p.endswith(".json"))

    def test_load_scenario_id_fallback_on_bad_json(self):
        """_load_scenario_id should return filename on bad JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as fh:
            fh.write("{invalid json")
            tmp_path = fh.name
        try:
            runner = cr.ContainerRunner(
                cr.ContainerConfig(image="test:latest"),
                scenarios_dir=SCENARIOS_DIR,
            )
            sid = runner._load_scenario_id(tmp_path)
            self.assertEqual(sid, os.path.basename(tmp_path))
        finally:
            os.unlink(tmp_path)

    def test_load_scenario_id_uses_field(self):
        """_load_scenario_id should read scenario_id from valid JSON."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as fh:
            json.dump({"scenario_id": "custom-id-123"}, fh)
            tmp_path = fh.name
        try:
            runner = cr.ContainerRunner(
                cr.ContainerConfig(image="test:latest"),
                scenarios_dir=SCENARIOS_DIR,
            )
            sid = runner._load_scenario_id(tmp_path)
            self.assertEqual(sid, "custom-id-123")
        finally:
            os.unlink(tmp_path)


class TestDryRunErrorHandling(unittest.TestCase):
    """Dry-run lifecycle error handling with mocked Docker failures."""

    @mock.patch("subprocess.run")
    def test_dry_run_create_failure(self, mock_run):
        """Dry run should capture error when docker create fails."""
        class FakeResult:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err
                self.args = []

        mock_run.return_value = FakeResult(1, "", "docker create error: image not found\n")
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp()
        result = runner.run_scenario(paths[0], out_dir, dry_run=True)
        self.assertFalse(result.created)
        self.assertIsNotNone(result.error)
        self.assertIn("docker create failed", result.error)

    @mock.patch("subprocess.run")
    def test_dry_run_empty_container_id(self, mock_run):
        """Dry run should error when docker create returns empty ID."""
        class FakeResult:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err
                self.args = []

        # First call (docker create) returns empty stdout.
        mock_run.return_value = FakeResult(0, "\n", "")
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp()
        result = runner.run_scenario(paths[0], out_dir, dry_run=True)
        self.assertFalse(result.created)
        self.assertIsNotNone(result.error)
        self.assertIn("empty container ID", result.error)

    @mock.patch("subprocess.run")
    def test_dry_run_inspect_failure(self, mock_run):
        """Dry run should capture error when docker inspect fails."""
        class FakeResult:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err
                self.args = []

        class FakeSequence:
            def __init__(self):
                self._calls = [
                    # docker create succeeds
                    FakeResult(0, "abc123def456\n", ""),
                    # docker inspect fails
                    FakeResult(1, "", "container not found\n"),
                    # docker rm (cleanup) succeeds
                    FakeResult(0, "abc123def456\n", ""),
                ]
                self._idx = 0

            def __call__(self, *args, **kwargs):
                r = self._calls[self._idx]
                self._idx += 1
                return r

        mock_run.side_effect = FakeSequence()
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp()
        result = runner.run_scenario(paths[0], out_dir, dry_run=True)
        self.assertTrue(result.created)
        self.assertIsNotNone(result.error)
        self.assertIn("docker inspect failed", result.error)
        # Should still attempt cleanup
        self.assertTrue(result.destroyed)

    @mock.patch("subprocess.run")
    def test_dry_run_rm_failure(self, mock_run):
        """Dry run should capture error when docker rm fails."""
        class FakeResult:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err
                self.args = []

        class FakeSequence:
            def __init__(self):
                self._calls = [
                    FakeResult(0, "abc123def456\n", ""),       # create
                    FakeResult(0, "abc123def456\n", ""),       # inspect
                    FakeResult(1, "", "rm failed\n"),          # rm
                ]
                self._idx = 0

            def __call__(self, *args, **kwargs):
                r = self._calls[self._idx]
                self._idx += 1
                return r

        mock_run.side_effect = FakeSequence()
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp()
        result = runner.run_scenario(paths[0], out_dir, dry_run=True)
        self.assertTrue(result.created)
        self.assertIsNotNone(result.error)
        self.assertIn("docker rm failed", result.error)
        self.assertFalse(result.destroyed)


class TestFullRunErrorHandling(unittest.TestCase):
    """Full run lifecycle error handling."""

    @mock.patch("subprocess.run")
    def test_full_run_nonzero_exit(self, mock_run):
        class FakeResult:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err
                self.args = []

        mock_run.return_value = FakeResult(1, "some output\n", "error\n")
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp()
        result = runner.run_scenario(paths[0], out_dir, dry_run=False)
        self.assertTrue(result.ran)
        self.assertEqual(result.exit_code, 1)
        self.assertIsNotNone(result.error)
        self.assertIn("exited with code 1", result.error)
        self.assertFalse(result.ok())

    @mock.patch("subprocess.run")
    def test_full_run_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=5)
        cfg = cr.ContainerConfig(image="test:latest", run_timeout=5)
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp()
        result = runner.run_scenario(paths[0], out_dir, dry_run=False)
        self.assertFalse(result.ran)
        self.assertEqual(result.exit_code, -1)
        self.assertIsNotNone(result.error)
        self.assertIn("timed out", result.error)

    @mock.patch("subprocess.run")
    def test_full_run_docker_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError("docker")
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp()
        result = runner.run_scenario(paths[0], out_dir, dry_run=False)
        self.assertFalse(result.ran)
        self.assertEqual(result.exit_code, -1)
        self.assertIsNotNone(result.error)
        self.assertIn("docker CLI not found", result.error)

    @mock.patch("subprocess.run")
    def test_full_run_stdout_truncated(self, mock_run):
        """stdout should be truncated to 4KB."""
        class FakeResult:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err
                self.args = []

        long_stdout = "x" * 10000
        mock_run.return_value = FakeResult(0, long_stdout, "")
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp()
        result = runner.run_scenario(paths[0], out_dir, dry_run=False)
        self.assertEqual(len(result.stdout), 4096)

    @mock.patch("subprocess.run")
    def test_full_run_stderr_truncated(self, mock_run):
        """stderr should be truncated to 4KB."""
        class FakeResult:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err
                self.args = []

        long_stderr = "y" * 10000
        mock_run.return_value = FakeResult(0, "ok\n", long_stderr)
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        paths = runner.scenario_paths()
        out_dir = tempfile.mkdtemp()
        result = runner.run_scenario(paths[0], out_dir, dry_run=False)
        self.assertEqual(len(result.stderr), 4096)


class TestRunAllSummary(unittest.TestCase):
    """run_all: summary structure and correctness."""

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_run_all_summary_structure(self, mock_run):
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        out_dir = tempfile.mkdtemp()
        results, summary = runner.run_all(out_dir, dry_run=True)
        self.assertIn("total", summary)
        self.assertIn("ok", summary)
        self.assertIn("failed", summary)
        self.assertIn("results", summary)
        self.assertEqual(summary["total"], len(results))
        self.assertEqual(summary["ok"] + summary["failed"], summary["total"])

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_run_all_dry_run_convenience(self, mock_run):
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir=SCENARIOS_DIR)
        out_dir = tempfile.mkdtemp()
        results, summary = runner.run_all_dry_run(out_dir)
        self.assertGreater(summary["total"], 0)
        self.assertEqual(summary["failed"], 0)

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_run_all_empty_scenarios(self, mock_run):
        """run_all with no scenarios returns empty results."""
        cfg = cr.ContainerConfig(image="test:latest")
        runner = cr.ContainerRunner(cfg, scenarios_dir="/nonexistent")
        out_dir = tempfile.mkdtemp()
        results, summary = runner.run_all(out_dir)
        self.assertEqual(results, [])
        self.assertEqual(summary, {"total": 0, "ok": 0, "failed": 0})


class TestDockerHelpers(unittest.TestCase):
    """Static Docker helper methods."""

    @mock.patch("subprocess.run")
    def test_image_exists_false_on_nonzero(self, mock_run):
        class FakeResult:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err
                self.args = []

        mock_run.return_value = FakeResult(1, "", "no such image\n")
        self.assertFalse(cr.ContainerRunner._image_exists("nonexistent:tag"))

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_docker_available_false_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=10)
        self.assertFalse(cr.ContainerRunner._docker_available())

    @mock.patch("subprocess.run")
    def test_run_docker_returns_tuple(self, mock_run):
        class FakeResult:
            def __init__(self, code, out, err):
                self.returncode = code
                self.stdout = out
                self.stderr = err
                self.args = []

        mock_run.return_value = FakeResult(0, "output\n", "err\n")
        ec, stdout, stderr = cr.ContainerRunner._run_docker(
            ["docker", "info"], timeout=5,
        )
        self.assertEqual(ec, 0)
        self.assertEqual(stdout, "output\n")
        self.assertEqual(stderr, "err\n")

    @mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=5))
    def test_run_docker_timeout(self, mock_run):
        ec, stdout, stderr = cr.ContainerRunner._run_docker(
            ["docker", "run"], timeout=5,
        )
        self.assertEqual(ec, -1)
        self.assertEqual(stderr, "timeout")

    @mock.patch("subprocess.run", side_effect=FileNotFoundError("docker"))
    def test_run_docker_not_found(self, mock_run):
        ec, stdout, stderr = cr.ContainerRunner._run_docker(
            ["docker", "run"], timeout=5,
        )
        self.assertEqual(ec, -1)
        self.assertEqual(stderr, "docker not found")


class TestFromManifestEdgeCases(unittest.TestCase):
    """ContainerRunner.from_manifest: error handling."""

    def test_from_manifest_invalid_json(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as fh:
            fh.write("{invalid")
            tmp_path = fh.name
        try:
            with self.assertRaises(json.JSONDecodeError):
                cr.ContainerRunner.from_manifest(manifest_path=tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_from_manifest_missing_image_key(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as fh:
            json.dump({"no_image": "here"}, fh)
            tmp_path = fh.name
        try:
            with self.assertRaises(ValueError):
                cr.ContainerRunner.from_manifest(manifest_path=tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_from_manifest_with_overrides(self):
        if not os.path.exists(MANIFEST_PATH):
            self.skipTest("benchmark-manifest.json not found")
        runner = cr.ContainerRunner.from_manifest(
            manifest_path=MANIFEST_PATH,
            scenarios_dir=SCENARIOS_DIR,
            network_mode="bridge",
            memory_limit="1g",
        )
        self.assertEqual(runner.config.network_mode, "bridge")
        self.assertEqual(runner.config.memory_limit, "1g")

    def test_from_manifest_list_format(self):
        """Manifest may be a list of images; the first image tag is used."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as fh:
            json.dump({"image": {"tag": "hermes-benchmark:listtest"}}, fh)
            tmp_path = fh.name
        try:
            runner = cr.ContainerRunner.from_manifest(manifest_path=tmp_path)
            self.assertEqual(runner.config.image, "hermes-benchmark:listtest")
        finally:
            os.unlink(tmp_path)


class TestRunnerConstructor(unittest.TestCase):
    """ContainerRunner constructor: default values."""

    def test_default_providers(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        self.assertEqual(runner.providers, "hermes_memory,lexical_baseline")

    def test_custom_providers(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
            providers="hindsight",
        )
        self.assertEqual(runner.providers, "hindsight")

    def test_default_repetitions(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        self.assertEqual(runner.repetitions, 3)

    def test_custom_repetitions(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
            repetitions=10,
        )
        self.assertEqual(runner.repetitions, 10)

    def test_default_seed(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        self.assertEqual(runner.seed, 7)

    def test_custom_seed(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
            seed=99,
        )
        self.assertEqual(runner.seed, 99)

    def test_default_scenarios_dir(self):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
        )
        self.assertEqual(runner.scenarios_dir, cr.DEFAULT_SCENARIOS_DIR)


class TestDestroyContainer(unittest.TestCase):
    """_destroy_container: calls docker rm -f."""

    @mock.patch("subprocess.run", side_effect=_fake_subprocess_run)
    def test_destroy_container_calls_rm(self, mock_run):
        runner = cr.ContainerRunner(
            cr.ContainerConfig(image="test:latest"),
            scenarios_dir=SCENARIOS_DIR,
        )
        runner._destroy_container("abc123")
        # Find the docker rm call
        rm_calls = [
            c for c in mock_run.call_args_list
            if c.args and len(c.args) >= 1 and isinstance(c.args[0], list)
            and c.args[0][:3] == ["docker", "rm", "-f"]
        ]
        self.assertTrue(rm_calls, "docker rm -f should have been called")
        self.assertIn("abc123", rm_calls[0].args[0])


if __name__ == "__main__":
    unittest.main()
