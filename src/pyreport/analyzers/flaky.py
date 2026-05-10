"""Flaky test detection — identify unstable tests across multiple runs."""
from __future__ import annotations

from dataclasses import dataclass, field

from pyreport.history.store import HistoryStore


@dataclass
class FlakyTest:
    """A test identified as flaky across multiple runs."""
    test_id: str
    name: str
    suite: str
    total_runs: int
    flaky_score: float  # 0.0 = stable, 1.0 = completely flaky
    status_changes: int  # number of status transitions
    statuses: list[str] = field(default_factory=list)  # status history ["passed", "failed", ...]


def detect_flaky(
    history_store: HistoryStore,
    min_runs: int = 3,
    min_score: float = 0.0,
) -> list[FlakyTest]:
    """Find flaky tests across all stored runs.

    Args:
        history_store: HistoryStore with saved runs.
        min_runs: Minimum number of runs required for analysis.
        min_score: Minimum flaky score to include (0.0 = all).

    Returns:
        Sorted list of FlakyTest (most flaky first).
    """
    runs = history_store.load_all_runs()
    if len(runs) < 2:
        return []

    # Collect status per test across runs
    test_statuses: dict[str, dict] = {}
    for run in runs:
        for suite in run.suites:
            for case in suite.tests:
                test_id = case.test_id or case.id
                if test_id not in test_statuses:
                    test_statuses[test_id] = {
                        "name": case.name,
                        "suite": suite.name,
                        "statuses": [],
                    }
                test_statuses[test_id]["statuses"].append(case.status.value)

    # Compute flaky scores
    results: list[FlakyTest] = []
    for test_id, info in test_statuses.items():
        statuses = info["statuses"]
        if len(statuses) < min_runs:
            continue

        transitions = sum(
            1 for i in range(1, len(statuses))
            if statuses[i] != statuses[i - 1]
        )
        score = round(transitions / (len(statuses) - 1), 2)

        if score < min_score:
            continue

        results.append(FlakyTest(
            test_id=test_id,
            name=info["name"],
            suite=info["suite"],
            total_runs=len(statuses),
            flaky_score=score,
            status_changes=transitions,
            statuses=statuses,
        ))

    results.sort(key=lambda f: f.flaky_score, reverse=True)
    return results
