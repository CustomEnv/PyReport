"""HistoryStore — persistence and retrieval of test runs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pyreport.core import Status, TestHistory, TestRun


@dataclass
class RunMeta:
    """Metadata for a historical run."""
    id: str
    timestamp: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    broken: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    duration: float = 0.0


class HistoryStore:
    """Stores and retrieves test runs from a history directory.

    Directory structure:
        <history_dir>/
            index.json         # list of run metadata, sorted by timestamp desc
            <run_id>.json      # full TestRun data
    """

    def __init__(self, history_dir: Path) -> None:
        self.history_dir = history_dir

    # ── write ──────────────────────────────────────────────────────────────

    def save_run(self, run: TestRun) -> Path:
        """Save a TestRun to the history store. Returns the path to the saved file."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

        from pyreport.core import model_to_dict

        run_path = self.history_dir / f"{run.id}.json"
        data = model_to_dict(run)
        run_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        self._update_index(run)
        return run_path

    def _update_index(self, run: TestRun) -> None:
        """Append or update this run in the index."""
        index_path = self.history_dir / "index.json"
        runs = self._read_index(index_path)

        # Remove existing entry for same run_id (if re-saving)
        runs = [r for r in runs if r["id"] != run.id]

        ts = (
            run.timestamp.isoformat()
            if hasattr(run.timestamp, "isoformat")
            else str(run.timestamp)
        )
        runs.append({
            "id": run.id,
            "timestamp": ts,
            "total": run.stats.total,
            "passed": run.stats.passed,
            "failed": run.stats.failed,
            "broken": run.stats.broken,
            "skipped": run.stats.skipped,
            "pass_rate": run.stats.pass_rate,
            "duration": run.duration,
        })

        # Sort by timestamp descending (newest first)
        runs.sort(key=lambda r: r["timestamp"], reverse=True)

        index_path.write_text(json.dumps(runs, indent=2, ensure_ascii=False))

    # ── read ───────────────────────────────────────────────────────────────

    def list_runs(self) -> list[dict]:
        """Return list of run metadata dicts, sorted newest-first."""
        return self._read_index(self.history_dir / "index.json")

    def load_run(self, run_id: str) -> TestRun | None:
        """Load a specific TestRun by ID."""
        run_path = self.history_dir / f"{run_id}.json"
        if not run_path.is_file():
            return None
        return self._load_from_path(run_path)

    def get_previous_run(self, run_id: str) -> TestRun | None:
        """Load the chronologically previous run relative to the given run_id."""
        runs = self.list_runs()
        # runs are sorted newest-first; find current, previous is next in list
        for i, r in enumerate(runs):
            if r["id"] == run_id and i + 1 < len(runs):
                return self.load_run(runs[i + 1]["id"])
        return None

    def get_test_history(self, test_id: str) -> TestHistory:
        """Collect history for a test across all stored runs.

        Matches tests by test_id field (stable identifier).
        """
        history = TestHistory()
        for run_meta in self.list_runs():
            run = self.load_run(run_meta["id"])
            if run is None:
                continue
            for suite in run.suites:
                for case in suite.tests:
                    if case.test_id == test_id:
                        history.total_runs += 1
                        if case.status in (Status.FAILED, Status.BROKEN):
                            history.total_failures += 1
                        history.statuses.append(case.status)
                        history.durations.append(case.duration)
                        break
        return history

    def load_all_runs(self) -> list[TestRun]:
        """Load all stored runs, newest first."""
        runs: list[TestRun] = []
        for meta in self.list_runs():
            run = self.load_run(meta["id"])
            if run is not None:
                runs.append(run)
        return runs

    # ── internal ───────────────────────────────────────────────────────────

    @staticmethod
    def _read_index(index_path: Path) -> list[dict]:
        if not index_path.is_file():
            return []
        try:
            return json.loads(index_path.read_text())
        except (json.JSONDecodeError, OSError):
            return []

    @staticmethod
    def _load_from_path(path: Path) -> TestRun | None:
        """Load a TestRun from a JSON file path."""
        from pyreport.cli.commands import _model_from_dict

        try:
            data = json.loads(path.read_text())
            return _model_from_dict(data)
        except (json.JSONDecodeError, OSError, KeyError, ValueError):
            return None
