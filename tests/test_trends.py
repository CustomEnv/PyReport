"""Tests for duration trend analysis."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pyreport.analyzers.trends import (
    DurationPoint,
    DurationTrend,
    analyze_duration,
    get_slowest_tests,
)
from pyreport.core import Status, TestCase, TestRun, TestSuite
from pyreport.history.store import HistoryStore


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / ".pyreport_history")


def _make_run(run_id: str, durations: dict[str, float]) -> TestRun:
    """Create a TestRun with tests having given durations."""
    tests = []
    for test_id, duration in durations.items():
        tests.append(TestCase(
            id=test_id,
            name=test_id.split("::")[-1],
            full_name=test_id,
            test_id=test_id,
            duration=duration,
            status=Status.PASSED,
        ))
    suite = TestSuite(
        id="suite-1",
        name="tests/test_api.py",
        duration=sum(durations.values()),
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


class TestAnalyzeDuration:
    def test_no_runs(self, store: HistoryStore) -> None:
        assert analyze_duration(store) == []

    def test_single_run(self, store: HistoryStore) -> None:
        run = _make_run("run-001", {"test_a": 0.5, "test_b": 1.2})
        store.save_run(run)
        assert analyze_duration(store) == []

    def test_two_runs(self, store: HistoryStore) -> None:
        run1 = _make_run("run-001", {"test_a": 0.5, "test_b": 1.0})
        store.save_run(run1)

        run2 = _make_run("run-002", {"test_a": 0.8, "test_b": 0.9})
        store.save_run(run2)

        trends = analyze_duration(store)
        assert len(trends) == 2

        # Find test_a
        trend_a = [t for t in trends if t.test_id == "test_a"][0]
        assert len(trend_a.points) == 2
        assert trend_a.latest_duration == 0.8
        assert trend_a.avg_duration == pytest.approx(0.65)
        assert trend_a.change_pct == pytest.approx(60.0)  # (0.8-0.5)/0.5 * 100

    def test_duration_increase_trend(self, store: HistoryStore) -> None:
        run1 = _make_run("run-001", {"test_a": 0.5})
        store.save_run(run1)
        run2 = _make_run("run-002", {"test_a": 1.5})
        store.save_run(run2)
        run3 = _make_run("run-003", {"test_a": 2.0})
        store.save_run(run3)

        trends = analyze_duration(store)
        assert len(trends) == 1
        t = trends[0]
        assert t.change_pct == pytest.approx(300.0)  # (2.0-0.5)/0.5 * 100

    def test_duration_decrease(self, store: HistoryStore) -> None:
        run1 = _make_run("run-001", {"test_a": 2.0})
        store.save_run(run1)
        run2 = _make_run("run-002", {"test_a": 1.0})
        store.save_run(run2)

        trends = analyze_duration(store)
        t = trends[0]
        assert t.change_pct == pytest.approx(-50.0)  # (1.0-2.0)/2.0 * 100

    def test_sort_by_latest_duration(self, store: HistoryStore) -> None:
        run1 = _make_run("run-001", {"test_a": 0.5, "test_b": 1.0})
        store.save_run(run1)
        run2 = _make_run("run-002", {"test_a": 3.0, "test_b": 2.0})
        store.save_run(run2)

        trends = analyze_duration(store)
        assert len(trends) == 2
        # Should be sorted by latest duration desc
        assert trends[0].test_id == "test_a"  # 3.0
        assert trends[1].test_id == "test_b"  # 2.0

    def test_multiple_tests_different_suites(self, store: HistoryStore) -> None:
        run1 = _make_run("run-001", {"test_a": 0.5})
        store.save_run(run1)

        # Second run with different test
        run2 = _make_run("run-002", {"test_b": 1.5})
        store.save_run(run2)

        # Both should appear but only in points where they exist
        trends = analyze_duration(store)
        # test_a has 1 point, test_b has 1 point, but need >=2 runs for analysis
        # Actually analyze_duration requires len(runs) >= 2, which is satisfied
        # But each test only has 1 point, so they get included
        test_ids = [t.test_id for t in trends]
        assert "test_a" in test_ids
        assert "test_b" in test_ids


class TestGetSlowestTests:
    def test_slowest_tests(self) -> None:
        suite = TestSuite(
            id="s1",
            name="tests/test_api.py",
            duration=10.0,
            status=Status.PASSED,
            tests=[
                TestCase(id="t1", name="fast", full_name="t1", duration=0.1, status=Status.PASSED),
                TestCase(id="t2", name="medium", full_name="t2",
                         duration=0.5, status=Status.PASSED),
                TestCase(id="t3", name="slow", full_name="t3", duration=2.0, status=Status.PASSED),
            ],
        )
        run = TestRun(id="r1", suites=[suite])
        run.compute_stats()

        slowest = get_slowest_tests(run, top_n=2)
        assert len(slowest) == 2
        assert slowest[0].name == "slow"
        assert slowest[1].name == "medium"

    def test_top_n_larger_than_total(self) -> None:
        suite = TestSuite(
            id="s1",
            name="tests/test_api.py",
            duration=1.0,
            status=Status.PASSED,
            tests=[
                TestCase(id="t1", name="t1", full_name="t1", duration=0.1, status=Status.PASSED),
            ],
        )
        run = TestRun(id="r1", suites=[suite])
        assert len(get_slowest_tests(run, top_n=10)) == 1


class TestDurationTrendDataclass:
    def test_duration_trend_creation(self) -> None:
        trend = DurationTrend(
            test_id="test_a",
            name="test_a",
            suite="suite-1",
            points=[
                DurationPoint(run_id="r1", timestamp="2026-01-01", duration=0.5),
                DurationPoint(run_id="r2", timestamp="2026-01-02", duration=1.0),
            ],
            change_pct=100.0,
        )
        assert trend.avg_duration == 0.75
        assert trend.max_duration == 1.0
        assert trend.latest_duration == 0.5  # points[0] is r1 (newest-first from load_all_runs)

    def test_empty_points(self) -> None:
        trend = DurationTrend(test_id="a", name="a", suite="s", points=[])
        assert trend.avg_duration == 0.0
        assert trend.max_duration == 0.0
        assert trend.latest_duration == 0.0
