"""Tests for flaky test detection."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pyreport.analyzers.flaky import FlakyTest, detect_flaky
from pyreport.core import Status, TestCase, TestRun, TestSuite
from pyreport.history.store import HistoryStore


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / ".pyreport_history")


def _make_run(run_id: str, test_statuses: dict[str, str]) -> TestRun:
    """Create a TestRun with tests having given statuses."""
    tests = []
    for test_id, status_str in test_statuses.items():
        tests.append(TestCase(
            id=test_id,
            name=test_id.split("::")[-1],
            full_name=test_id,
            test_id=test_id,
            duration=0.5,
            status=Status(status_str),
        ))
    suite = TestSuite(
        id="suite-1",
        name="tests/test_api.py",
        duration=1.0,
        status=Status.PASSED,
        tests=tests,
    )
    run = TestRun(
        id=run_id,
        project="demo",
        name=f"Run {run_id}",
        timestamp=datetime.now(),
        suites=[suite],
    )
    run.compute_stats()
    return run


class TestDetectFlaky:
    def test_no_runs(self, store: HistoryStore) -> None:
        assert detect_flaky(store) == []

    def test_single_run(self, store: HistoryStore) -> None:
        run = _make_run("run-001", {"test_a": "passed", "test_b": "failed"})
        store.save_run(run)
        assert detect_flaky(store) == []

    def test_stable_test(self, store: HistoryStore) -> None:
        for i in range(3):
            run = _make_run(f"run-00{i+1}", {"test_a": "passed", "test_b": "failed"})
            store.save_run(run)

        results = detect_flaky(store)
        # Both tests have 0 transitions (always same status), score = 0.0
        assert len(results) == 2
        assert all(r.flaky_score == 0.0 for r in results)

    def test_flaky_test(self, store: HistoryStore) -> None:
        statuses = ["passed", "failed", "passed"]
        for i, s in enumerate(statuses):
            run = _make_run(f"run-00{i+1}", {"test_a": s})
            store.save_run(run)

        results = detect_flaky(store)
        assert len(results) == 1
        assert results[0].test_id == "test_a"
        assert results[0].flaky_score == 1.0  # 2 transitions / 2 = 1.0
        assert results[0].status_changes == 2

    def test_flaky_with_four_runs(self, store: HistoryStore) -> None:
        statuses = ["passed", "passed", "failed", "passed"]
        for i, s in enumerate(statuses):
            run = _make_run(f"run-00{i+1}", {"test_a": s})
            store.save_run(run)

        results = detect_flaky(store)
        assert len(results) == 1
        # 2 transitions / 3 = 0.67
        assert results[0].flaky_score == 0.67
        assert results[0].status_changes == 2

    def test_min_runs_filter(self, store: HistoryStore) -> None:
        statuses = ["passed", "failed"]
        for i, s in enumerate(statuses):
            run = _make_run(f"run-00{i+1}", {"test_a": s})
            store.save_run(run)

        # Default min_runs=3, should not find anything
        assert len(detect_flaky(store)) == 0

        # With min_runs=2 should find
        results = detect_flaky(store, min_runs=2)
        assert len(results) == 1

    def test_min_score_filter(self, store: HistoryStore) -> None:
        statuses = ["passed", "failed", "failed"]
        for i, s in enumerate(statuses):
            run = _make_run(f"run-00{i+1}", {"test_a": s})
            store.save_run(run)

        results = detect_flaky(store, min_score=0.5)
        # 1 transition / 2 = 0.5, >= 0.5
        assert len(results) == 1

        results = detect_flaky(store, min_score=0.6)
        # 0.5 < 0.6
        assert len(results) == 0

    def test_multiple_tests(self, store: HistoryStore) -> None:
        for i in range(3):
            run = _make_run(f"run-00{i+1}", {
                "test_a": "passed",
                "test_b": "failed",
                "test_c": "passed" if i % 2 == 0 else "failed",
            })
            store.save_run(run)

        results = detect_flaky(store)
        # test_c is flaky (score 1.0); test_a (0.0) and test_b (0.0) are not
        assert len(results) == 3
        # Sorted by flaky_score desc — test_c first
        assert results[0].test_id == "test_c"
        assert results[0].flaky_score == 1.0

    def test_different_test_ids_across_runs(self, store: HistoryStore) -> None:
        """Tests that appear in only some runs should still be analyzed."""
        run1 = _make_run("run-001", {"test_a": "passed"})
        store.save_run(run1)

        run2 = _make_run("run-002", {"test_a": "passed", "test_b": "failed"})
        store.save_run(run2)

        run3 = _make_run("run-003", {"test_b": "passed"})
        store.save_run(run3)

        results = detect_flaky(store, min_runs=2)
        # test_a: 2 runs, always passed → score 0.0
        # test_b: 2 runs, failed, passed → score 1.0 (but only 1 transition / 1 = 1.0)
        assert len(results) == 2
        # Sorted by flaky_score desc — test_b first
        assert results[0].test_id == "test_b"
        assert results[0].flaky_score == 1.0


class TestFlakyTestDataclass:
    def test_flaky_test_creation(self) -> None:
        ft = FlakyTest(
            test_id="test_a",
            name="test_a",
            suite="suite-1",
            total_runs=3,
            flaky_score=0.67,
            status_changes=2,
            statuses=["passed", "failed", "passed"],
        )
        assert ft.test_id == "test_a"
        assert ft.flaky_score == 0.67

    def test_flaky_test_sorting(self) -> None:
        ft1 = FlakyTest("a", "a", "s1", 3, 0.5, 1, ["p", "f", "p"])
        ft2 = FlakyTest("b", "b", "s1", 3, 1.0, 2, ["p", "f", "p"])
        ft3 = FlakyTest("c", "c", "s1", 3, 0.2, 1, ["p", "f", "p"])

        sorted_tests = sorted([ft1, ft2, ft3], key=lambda f: f.flaky_score, reverse=True)
        assert sorted_tests[0].test_id == "b"
        assert sorted_tests[1].test_id == "a"
        assert sorted_tests[2].test_id == "c"
