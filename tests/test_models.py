"""Tests for core data models."""
from __future__ import annotations

from pyreport.core import (
    RunStats,
    Status,
    TestCase,
    TestHistory,
    TestRun,
    TestSuite,
    model_to_dict,
)


class TestStatus:
    def test_values(self):
        assert Status.PASSED.value == "passed"
        assert Status.FAILED.value == "failed"
        assert Status.SKIPPED.value == "skipped"
        assert Status.BROKEN.value == "broken"


class TestRunStats:
    def test_pass_rate_full(self):
        stats = RunStats(total=10, passed=10)
        assert stats.pass_rate == 100.0

    def test_pass_rate_half(self):
        stats = RunStats(total=10, passed=5, failed=5)
        assert stats.pass_rate == 50.0

    def test_pass_rate_zero(self):
        stats = RunStats()
        assert stats.pass_rate == 0.0


class TestTestHistory:
    def test_flaky_score_stable(self):
        h = TestHistory(
            total_runs=10,
            statuses=[Status.PASSED] * 10,
        )
        assert h.flaky_score == 0.0

    def test_flaky_score_alternating(self):
        h = TestHistory(
            total_runs=5,
            statuses=[
                Status.PASSED,
                Status.FAILED,
                Status.PASSED,
                Status.FAILED,
                Status.PASSED,
            ],
        )
        assert h.flaky_score == 1.0

    def test_flaky_score_insufficient_data(self):
        h = TestHistory(total_runs=2, statuses=[Status.PASSED, Status.FAILED])
        assert h.flaky_score == 0.0


class TestTestRun:
    def test_compute_stats(self, sample_test_run):
        run = sample_test_run
        run.compute_stats()
        assert run.stats.total == 3
        assert run.stats.passed == 2
        assert run.stats.failed == 1
        assert run.stats.skipped == 0
        assert run.status == Status.FAILED

    def test_compute_stats_all_pass(self):
        run = TestRun(
            id="test",
            suites=[
                TestSuite(
                    id="s1", name="s1", duration=0, status=Status.PASSED,
                    tests=[
                        TestCase(
                            id="c1", name="c1", full_name="c1",
                            duration=0, status=Status.PASSED,
                        ),
                    ],
                ),
            ],
        )
        run.compute_stats()
        assert run.stats.passed == 1
        assert run.status == Status.PASSED

    def test_compute_stats_all_skipped(self):
        run = TestRun(
            id="test",
            suites=[
                TestSuite(
                    id="s1", name="s1", duration=0, status=Status.SKIPPED,
                    tests=[
                        TestCase(
                            id="c1", name="c1", full_name="c1",
                            duration=0, status=Status.SKIPPED,
                        ),
                    ],
                ),
            ],
        )
        run.compute_stats()
        assert run.stats.skipped == 1
        assert run.status == Status.PASSED


class TestModelToDict:
    def test_serializes_correctly(self, sample_test_run):
        d = model_to_dict(sample_test_run)
        assert d["id"] == "run-001"
        assert d["project"] == "demo"
        assert d["status"] == "passed"
        assert len(d["suites"]) == 2
        # datetime should be isoformat string
        assert isinstance(d["timestamp"], str)
        assert "T" in d["timestamp"]
        # status enum serialized to value
        assert d["suites"][0]["tests"][0]["status"] == "passed"
        assert d["suites"][0]["tests"][1]["status"] == "failed"
        # parameters dict preserved
        assert d["suites"][0]["tests"][1]["parameters"] == {"role": "admin"}
        # commit info serialized
        assert d["commit"]["sha"] == "abc123"
        assert d["commit"]["branch"] == "main"
        # ci info serialized
        assert d["ci"]["name"] == "github-actions"
