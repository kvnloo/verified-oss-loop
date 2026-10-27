#!/usr/bin/env python3
"""Offline unit tests for scripts/cluster-similar-issues.py."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "cluster-similar-issues.py"
SPEC = importlib.util.spec_from_file_location("cluster_similar_issues", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT}")
clusterer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clusterer)


def write_fixture(directory: Path, data: object) -> Path:
    path = directory / "issues.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class ClusterUnits(unittest.TestCase):
    def test_tokens(self) -> None:
        self.assertEqual(
            clusterer.tokens("The Retry-after 400 a X"),
            frozenset({"retry", "400"}),
        )
        self.assertEqual(clusterer.tokens("RETRY!!!retry? 400"), frozenset({"retry", "400"}))

    def test_jaccard(self) -> None:
        empty = frozenset()
        one = frozenset({"a"})
        self.assertEqual(clusterer.jaccard(empty, empty), 0.0)
        self.assertEqual(clusterer.jaccard(empty, one), 0.0)
        self.assertEqual(clusterer.jaccard(one, empty), 0.0)
        self.assertAlmostEqual(
            clusterer.jaccard(frozenset({"a", "b"}), frozenset({"b", "c"})),
            1 / 3,
        )
        self.assertEqual(clusterer.jaccard(one, one), 1.0)

    def test_cluster_transitive(self) -> None:
        issues = [
            {"number": 3, "title": "gamma delta"},
            {"number": 1, "title": "alpha beta"},
            {"number": 2, "title": "beta gamma"},
        ]
        self.assertEqual(clusterer.cluster(issues, threshold=0.3), [[1, 2, 3]])
        self.assertEqual(clusterer.cluster(issues, threshold=0.5), [[1], [2], [3]])

    def test_cluster_order(self) -> None:
        issues = [
            {"number": 28, "title": "amber sapphire"},
            {"number": 11, "title": "brisk cedar"},
            {"number": 9, "title": "amber sapphire"},
            {"number": 4, "title": "maple pine"},
            {"number": 2, "title": "amber sapphire"},
            {"number": 17, "title": "brisk cedar"},
            {"number": 6, "title": "maple pine"},
            {"number": 1, "title": "unique elsewhere"},
        ]
        self.assertEqual(
            clusterer.cluster(issues, threshold=1.0),
            [[2, 9, 28], [4, 6], [11, 17], [1]],
        )

    def test_load_issues_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)

            path = write_fixture(directory, {"number": 1, "title": "not a list"})
            with self.assertRaises(SystemExit) as error:
                clusterer.load_issues(path, cap=2)
            self.assertEqual(str(error.exception), "fixture must be a JSON array of issues")

            path = write_fixture(directory, [{"number": 1}])
            with self.assertRaises(SystemExit) as error:
                clusterer.load_issues(path, cap=2)
            self.assertEqual(str(error.exception), "each issue needs number and title")

            path = write_fixture(directory, [{"title": "missing number"}])
            with self.assertRaises(SystemExit) as error:
                clusterer.load_issues(path, cap=2)
            self.assertEqual(str(error.exception), "each issue needs number and title")

            data = [
                {"number": "7", "title": "alpha beta"},
                {"number": 8, "title": "gamma delta"},
                {"number": 9, "title": "unique elsewhere"},
            ]
            path = write_fixture(directory, data)
            with self.assertRaises(SystemExit) as error:
                clusterer.load_issues(path, cap=2)
            self.assertIn("cap is 2", str(error.exception))
            self.assertEqual(
                clusterer.load_issues(path, cap=3),
                [
                    {"number": 7, "title": "alpha beta"},
                    {"number": 8, "title": "gamma delta"},
                    {"number": 9, "title": "unique elsewhere"},
                ],
            )

    def test_main_cap_and_text_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = write_fixture(
                Path(temp),
                [
                    {"number": 9, "title": "alpha beta"},
                    {"number": 7, "title": "unique elsewhere"},
                    {"number": 4, "title": "alpha beta"},
                ],
            )

            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = clusterer.main([str(path), "--cap", "65"])
            self.assertEqual(result, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("cap cannot exceed 64", stderr.getvalue())

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = clusterer.main([str(path)])
            self.assertEqual(result, 0)
            self.assertEqual(stdout.getvalue().splitlines(), ["4 9", "7"])

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = clusterer.main([str(path), "--json"])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(stdout.getvalue()), {"clusters": [[4, 9], [7]]})


if __name__ == "__main__":
    unittest.main()
