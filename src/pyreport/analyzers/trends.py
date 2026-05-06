"""Duration trend analysis — track test performance over time."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pyreport.core import TestCase, TestRun
from pyreport.history.store import HistoryStore


@dataclass
class DurationPoint:
    """A single duration measurement for a test in one run."""
    run_id: str
    timestamp: str
    duration: float


@dataclass
class DurationTrend:
    """Duration trend data for a single test."""
    test_id: str
    name: str
    suite: str
    points: list[DurationPoint]
    change_pct: Optional[float] = None  # % change relative to first run

    @property
    def avg_duration(self) -> float:
        if not self.points:
            return 0.0
        return sum(p.duration for p in self.points) / len(self.points)

    @property
    def max_duration(self) -> float:
        if not self.points:
            return 0.0
        return max(p.duration for p in self.points)

    @property
    def latest_duration(self) -> float:
        if not self.points:
            return 0.0
        return self.points[0].duration  # newest first


def analyze_duration(history_store: HistoryStore) -> list[DurationTrend]:
    """Analyze duration trends for all tests across stored runs.

    Returns:
        Sorted list of DurationTrend (most recently slowest first).
    """
    runs = history_store.load_all_runs()
    if len(runs) < 2:
        return []

    # Collect duration per test across runs
    test_points: dict[str, dict] = {}
    for run in runs:
        ts = (
            run.timestamp.isoformat()
            if hasattr(run.timestamp, 'isoformat')
            else str(run.timestamp)
        )
        for suite in run.suites:
            for case in suite.tests:
                test_id = case.test_id or case.id
                if test_id not in test_points:
                    test_points[test_id] = {
                        "name": case.name,
                        "suite": suite.name,
                        "points": [],
                    }
                test_points[test_id]["points"].append(DurationPoint(
                    run_id=run.id,
                    timestamp=ts,
                    duration=case.duration,
                ))

    # Compute trends
    # Points are collected in the order runs are loaded (newest first from load_all_runs)
    results: list[DurationTrend] = []
    for test_id, info in test_points.items():
        points = info["points"]
        # Reverse to get chronological order for change_pct calculation
        points_chrono = list(reversed(points))

        change_pct: Optional[float] = None
        if len(points_chrono) >= 2 and points_chrono[0].duration > 0:
            first = points_chrono[0].duration
            last = points_chrono[-1].duration
            change_pct = round((last - first) / first * 100, 1)

        results.append(DurationTrend(
            test_id=test_id,
            name=info["name"],
            suite=info["suite"],
            points=points,  # already newest-first from load_all_runs()
            change_pct=change_pct,
        ))

    # Sort by latest duration descending (slowest tests first)
    results.sort(key=lambda t: t.latest_duration, reverse=True)
    return results


def get_slowest_tests(run: TestRun, top_n: int = 10) -> list[TestCase]:
    """Get the slowest N tests in a run.

    Returns:
        List of TestCase sorted by duration descending.
    """
    all_tests: list[TestCase] = []
    for suite in run.suites:
        for case in suite.tests:
            all_tests.append(case)

    all_tests.sort(key=lambda t: t.duration, reverse=True)
    return all_tests[:top_n]
