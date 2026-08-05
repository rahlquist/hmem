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


if __name__ == "__main__":
    unittest.main()
