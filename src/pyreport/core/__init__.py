from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Optional


class Status(Enum):
    PASSED = "passed"
    FAILED = "failed"
    BROKEN = "broken"
    SKIPPED = "skipped"


@dataclass
class Step:
    """A single step within a test case."""
    name: str
    status: Status
    duration: float  # seconds
    message: Optional[str] = None
    attachments: list[Attachment] = field(default_factory=list)


@dataclass
class Attachment:
    """File attached to a test or step (screenshot, log, etc.)."""
    name: str
    path: str  # relative path within report
    mime_type: str
    size: int = 0


@dataclass
class CommitInfo:
    sha: str
    branch: str
    message: str
    author: str
    url: Optional[str] = None


@dataclass
class CIInfo:
    name: str  # "github-actions", "jenkins", etc.
    url: Optional[str] = None
    run_id: Optional[str] = None


@dataclass
class RunStats:
    total: int = 0
    passed: int = 0
    failed: int = 0
    broken: int = 0
    skipped: int = 0

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.passed / self.total * 100, 1)

    @property
    def duration(self) -> float:
        return 0.0


@dataclass
class TestHistory:
    """Aggregated history for a single test."""
    total_runs: int = 0
    total_failures: int = 0
    statuses: list[Status] = field(default_factory=list)
    durations: list[float] = field(default_factory=list)

    @property
    def flaky_score(self) -> float:
        """0.0 = стабильный, 1.0 = полностью flaky."""
        if self.total_runs < 3:
            return 0.0
        transitions = sum(
            1 for i in range(1, len(self.statuses))
            if self.statuses[i] != self.statuses[i - 1]
        )
        return round(transitions / (self.total_runs - 1), 2)


@dataclass
class TestCase:
    id: str
    name: str
    full_name: str  # module::class::method[params]
    duration: float
    status: Status
    message: Optional[str] = None
    traceback: Optional[str] = None
    parameters: dict[str, str] = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    history: Optional[TestHistory] = None
    retries: list[TestCase] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    test_id: str = ""  # stable identifier for matching across runs (e.g. nodeid without params)
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    log: Optional[str] = None


@dataclass
class TestSuite:
    id: str
    name: str
    duration: float
    status: Status
    tests: list[TestCase] = field(default_factory=list)


@dataclass
class TestRun:
    """Root object — one test run."""
    id: str
    project: str = ""
    name: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration: float = 0.0
    status: Status = Status.PASSED
    stats: RunStats = field(default_factory=RunStats)
    suites: list[TestSuite] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    attachments: list[Attachment] = field(default_factory=list)
    commit: Optional[CommitInfo] = None
    ci: Optional[CIInfo] = None

    def compute_stats(self) -> None:
        """Recalculate stats from suites."""
        stats = RunStats()
        max_status = Status.PASSED
        for suite in self.suites:
            for case in suite.tests:
                stats.total += 1
                if case.status == Status.PASSED:
                    stats.passed += 1
                elif case.status == Status.FAILED:
                    stats.failed += 1
                    max_status = Status.FAILED
                elif case.status == Status.BROKEN:
                    stats.broken += 1
                    if max_status != Status.FAILED:
                        max_status = Status.BROKEN
                elif case.status == Status.SKIPPED:
                    stats.skipped += 1
        self.stats = stats
        self.status = max_status


def model_to_dict(obj):
    """Convert a dataclass tree to a JSON-serializable dict."""
    return _to_dict(obj)


def _extra_fields(obj) -> dict:
    """Return extra computed fields not in dataclass fields."""
    extra: dict = {}
    if isinstance(obj, RunStats):
        extra["pass_rate"] = obj.pass_rate
    if isinstance(obj, TestHistory):
        extra["flaky_score"] = obj.flaky_score
    return extra


def _to_dict(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [_to_dict(item) for item in obj]
    if hasattr(obj, "__dataclass_fields__"):
        result = {f.name: _to_dict(getattr(obj, f.name)) for f in fields(obj)}
        result.update(_extra_fields(obj))
        return result
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj
