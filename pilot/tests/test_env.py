"""Tests for pilot.env: environment capture, percentiles, token estimates, resources."""
import unittest

import pilot.env as env


class TestEnvironmentCapture(unittest.TestCase):
    def test_capture_returns_required_keys(self):
        snap = env.capture_environment()
        for key in ("os", "python_version", "machine", "cpu_count", "captured_iso"):
            self.assertIn(key, snap, f"missing key {key}")

    def test_capture_values_are_strings_or_ints(self):
        snap = env.capture_environment()
        self.assertIsInstance(snap["python_version"], str)
        self.assertIsInstance(snap["cpu_count"], int)
        self.assertGreaterEqual(snap["cpu_count"], 1)


class TestPercentiles(unittest.TestCase):
    def test_p50_p95_nearest_rank(self):
        samples = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        out = env.percentiles(samples)
        self.assertEqual(out["p50"], 50.0)
        self.assertEqual(out["p95"], 100.0)

    def test_single_sample(self):
        out = env.percentiles([7.0])
        self.assertEqual(out["p50"], 7.0)
        self.assertEqual(out["p95"], 7.0)

    def test_empty_returns_none(self):
        out = env.percentiles([])
        self.assertIsNone(out["p50"])
        self.assertIsNone(out["p95"])


class TestTokenEstimate(unittest.TestCase):
    def test_deterministic_word_tokens(self):
        self.assertEqual(env.estimate_tokens("hello world"), 2)
        self.assertEqual(env.estimate_tokens(""), 0)
        self.assertEqual(env.estimate_tokens("a b c d"), 4)

    def test_same_input_same_output(self):
        text = "The staging database runs on willow-01 with port 5433."
        self.assertEqual(env.estimate_tokens(text), env.estimate_tokens(text))


class TestResourceCapture(unittest.TestCase):
    def test_snapshot_returns_required_keys(self):
        snap = env.resource_snapshot()
        for key in ("cpu_percent", "peak_ram_mb", "disk_free_mb", "network_egress_bytes"):
            self.assertIn(key, snap, f"missing key {key}")

    def test_measure_resources_returns_required_keys(self):
        before = env.resource_snapshot()
        after = env.resource_snapshot()
        out = env.measure_resources(before, after)
        for key in ("cpu_percent", "peak_ram_mb", "disk_growth_mb", "network_egress_bytes"):
            self.assertIn(key, out, f"missing key {key}")


if __name__ == "__main__":
    unittest.main()
