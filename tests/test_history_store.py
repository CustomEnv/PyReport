"""Tests for HistoryStore."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from pyreport.core import Status, TestCase, TestRun, TestSuite
from pyreport.history.store import HistoryStore


@pytest.fixture
def store(tmp_path: Path) -> HistoryStore:
    return HistoryStore(tmp_path / ".pyreport_history")


@pytest.fixture
def sample_run() -> TestRun:
    run = TestRun(
        id="run-001",
        project="demo",
        name="Test Run 1",
        timestamp=datetime(2026, 5, 1, 10, 0, 0),
        duration=5.0,
        suites=[
            TestSuite(
                id="suite-1",
                name="tests/test_api.py",
                duration=2.0,
                status=Status.PASSED,
                tests=[
                    TestCase(
                        id="test_a",
                        name="test_a",
                        full_name="tests/test_api.py::test_a",
                        test_id="tests/test_api.py::test_a",
                        duration=0.5,
                        status=Status.PASSED,
                    ),
                    TestCase(
                        id="test_b",
                        name="test_b",
                        full_name="tests/test_api.py::test_b",
                        test_id="tests/test_api.py::test_b",
                        duration=0.3,
                        status=Status.FAILED,
                    ),
                ],
            ),
        ],
    )
    run.compute_stats()
    return run


class TestHistoryStore:
    def test_save_and_list(self, store: HistoryStore, sample_run: TestRun) -> None:
        store.save_run(sample_run)
        runs = store.list_runs()
        assert len(runs) == 1
        assert runs[0]["id"] == "run-001"
        assert runs[0]["total"] == 2
        assert runs[0]["passed"] == 1
        assert runs[0]["failed"] == 1

    def test_save_multiple_runs(self, store: HistoryStore, sample_run: TestRun) -> None:
        run2 = TestRun(
            id="run-002",
            project="demo",
            name="Test Run 2",
            timestamp=datetime(2026, 5, 2, 10, 0, 0),
            duration=3.0,
            suites=sample_run.suites,
        )
        run2.compute_stats()

        store.save_run(sample_run)
        store.save_run(run2)

        runs = store.list_runs()
        assert len(runs) == 2
        # Newest first
        assert runs[0]["id"] == "run-002"

    def test_load_run(self, store: HistoryStore, sample_run: TestRun) -> None:
        store.save_run(sample_run)
        loaded = store.load_run("run-001")
        assert loaded is not None
        assert loaded.id == "run-001"
        assert len(loaded.suites) == 1
        assert len(loaded.suites[0].tests) == 2
        assert loaded.suites[0].tests[0].test_id == "tests/test_api.py::test_a"

    def test_load_nonexistent_run(self, store: HistoryStore) -> None:
        assert store.load_run("nonexistent") is None

    def test_get_previous_run(self, store: HistoryStore, sample_run: TestRun) -> None:
        run2 = TestRun(
            id="run-002",
            project="demo",
            name="Test Run 2",
            timestamp=datetime(2026, 5, 2, 10, 0, 0),
            duration=3.0,
            suites=sample_run.suites,
        )
        run2.compute_stats()

        store.save_run(sample_run)
        store.save_run(run2)

        prev = store.get_previous_run("run-002")
        assert prev is not None
        assert prev.id == "run-001"

        # No previous for the oldest run
        assert store.get_previous_run("run-001") is None

    def test_get_test_history(self, store: HistoryStore, sample_run: TestRun) -> None:
        store.save_run(sample_run)

        # Second run: test_a passed again, test_b also passed
        run2 = TestRun(
            id="run-002",
            project="demo",
            name="Test Run 2",
            timestamp=datetime(2026, 5, 2, 10, 0, 0),
            duration=3.0,
            suites=[
                TestSuite(
                    id="suite-1",
                    name="tests/test_api.py",
                    duration=2.0,
                    status=Status.PASSED,
                    tests=[
                        TestCase(
                            id="test_a",
                            name="test_a",
                            full_name="tests/test_api.py::test_a",
                            test_id="tests/test_api.py::test_a",
                            duration=0.6,
                            status=Status.PASSED,
                        ),
                        TestCase(
                            id="test_b",
                            name="test_b",
                            full_name="tests/test_api.py::test_b",
                            test_id="tests/test_api.py::test_b",
                            duration=0.4,
                            status=Status.PASSED,
                        ),
                    ],
                ),
            ],
        )
        run2.compute_stats()
        store.save_run(run2)

        # test_b had 1 failure out of 2 runs
        # get_test_history returns statuses newest-first
        history = store.get_test_history("tests/test_api.py::test_b")
        assert history.total_runs == 2
        assert history.total_failures == 1
        assert len(history.statuses) == 2
        assert history.statuses[0] == Status.PASSED  # newest run: run-002
        assert history.statuses[1] == Status.FAILED  # older run: run-001

    def test_list_runs_empty(self, store: HistoryStore) -> None:
        assert store.list_runs() == []

    def test_index_file_created(self, store: HistoryStore, sample_run: TestRun) -> None:
        store.save_run(sample_run)
        index_path = store.history_dir / "index.json"
        assert index_path.is_file()
        data = json.loads(index_path.read_text())
        assert len(data) == 1

    def test_save_run_replaces_existing(self, store: HistoryStore, sample_run: TestRun) -> None:
        store.save_run(sample_run)
        store.save_run(sample_run)  # save again with same id
        runs = store.list_runs()
        assert len(runs) == 1  # no duplicate

    def test_load_run_with_corrupted_json(self, store: HistoryStore) -> None:
        """Corrupted run file should return None."""
        store.history_dir.mkdir(parents=True, exist_ok=True)
        (store.history_dir / "bad-run.json").write_text("not valid json")
        assert store.load_run("bad-run") is None

    def test_list_runs_with_corrupted_index(self, store: HistoryStore) -> None:
        """Corrupted index.json should return empty list."""
        store.history_dir.mkdir(parents=True, exist_ok=True)
        (store.history_dir / "index.json").write_text("corrupted")
        assert store.list_runs() == []

    def test_get_test_history_unknown_test(self, store: HistoryStore, sample_run: TestRun) -> None:
        """Unknown test_id returns empty TestHistory."""
        store.save_run(sample_run)
        history = store.get_test_history("nonexistent_test")
        assert history.total_runs == 0
        assert history.total_failures == 0
        assert history.statuses == []

    def test_load_all_runs(self, store: HistoryStore, sample_run: TestRun) -> None:
        """load_all_runs returns all stored runs newest-first."""
        run2 = TestRun(
            id="run-002",
            project="demo",
            name="Test Run 2",
            timestamp=datetime(2026, 5, 2, 10, 0, 0),
        )
        run2.compute_stats()
        store.save_run(sample_run)
        store.save_run(run2)

        all_runs = store.load_all_runs()
        assert len(all_runs) == 2
        assert all_runs[0].id == "run-002"  # newest first
        assert all_runs[1].id == "run-001"

    def test_save_run_creates_history_dir(self, store: HistoryStore, sample_run: TestRun) -> None:
        """save_run auto-creates the history directory."""
        assert not store.history_dir.exists()
        store.save_run(sample_run)
        assert store.history_dir.is_dir()
