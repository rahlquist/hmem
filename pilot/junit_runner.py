#!/usr/bin/env python3
"""Run the pilot unittest suite and write a JUnit XML report."""

from __future__ import annotations

import argparse
import sys
import time
import unittest
from pathlib import Path
from typing import cast
from xml.etree import ElementTree as ET


class JUnitResult(unittest.TextTestResult):
    """Text result that also records one JUnit testcase per unittest test."""

    def startTest(self, test: unittest.TestCase) -> None:
        self._started_at = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase) -> None:
        elapsed = time.perf_counter() - self._started_at
        status = "passed"
        detail = ""
        if any(failed_test is test for failed_test, _ in self.failures):
            status = "failure"
            detail = next(text for failed_test, text in self.failures if failed_test is test)
        elif any(error_test is test for error_test, _ in self.errors):
            status = "error"
            detail = next(text for error_test, text in self.errors if error_test is test)
        elif any(skipped_test is test for skipped_test, _ in self.skipped):
            status = "skipped"
            detail = next(reason for skipped_test, reason in self.skipped if skipped_test is test)
        self.records.append((test, elapsed, status, detail))
        super().stopTest(test)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.records: list[tuple[unittest.TestCase, float, str, str]] = []


def write_junit(result: JUnitResult, output: Path, elapsed: float) -> None:
    suite = ET.Element(
        "testsuite",
        {
            "name": "pilot.tests",
            "tests": str(result.testsRun),
            "failures": str(len(result.failures)),
            "errors": str(len(result.errors)),
            "skipped": str(len(result.skipped)),
            "time": f"{elapsed:.6f}",
        },
    )
    for test, duration, status, detail in result.records:
        test_id = test.id()
        class_name, _, test_name = test_id.rpartition(".")
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": class_name,
                "name": test_name,
                "time": f"{duration:.6f}",
            },
        )
        if status in {"failure", "error"}:
            node = ET.SubElement(case, status, {"message": detail.splitlines()[-1] if detail else status})
            node.text = detail
        elif status == "skipped":
            ET.SubElement(case, "skipped", {"message": detail})

    tree = ET.ElementTree(suite)
    ET.indent(tree, space="  ")
    output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("test-results.xml"))
    parser.add_argument("--start-directory", default="pilot/tests")
    parser.add_argument("--pattern", default="test_*.py")
    args = parser.parse_args()

    suite = unittest.defaultTestLoader.discover(args.start_directory, pattern=args.pattern)
    runner = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, resultclass=JUnitResult)
    started = time.perf_counter()
    result = cast(JUnitResult, runner.run(suite))
    write_junit(result, args.output, time.perf_counter() - started)
    print(f"JUnit report: {args.output} ({result.testsRun} tests)")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
