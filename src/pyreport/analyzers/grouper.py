"""Error grouping — hash-based traceback grouping."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from pyreport.core import TestRun


@dataclass
class ErrorGroup:
    """A group of tests that failed with the same error signature."""
    id: str  # hash of the normalized traceback
    headline: str  # short error message
    count: int = 0
    tests: list[str] = field(default_factory=list)  # test full_names


def normalize_traceback(traceback: str) -> str:
    """Strip variable details, line numbers, memory addresses from a traceback.

    Keeps the structure (file:line → function → error type) but normalizes
    variable values, memory addresses, and platform-specific paths.
    """
    if not traceback:
        return ""

    text = traceback

    # Normalize line numbers: "file.py:42" → "file.py:N"
    text = re.sub(r'(\.\w+):(\d+)', r'\1:N', text)

    # Normalize hex memory addresses
    text = re.sub(r'0x[0-9a-fA-F]+', '0xH', text)

    # Normalize paths (absolute/relative → basename)
    text = re.sub(r'/[^\s:)+]+/([\w./-]+\.\w+)', r'/\1', text)

    # Normalize string literals in assertions
    text = re.sub(r"'[^']*'", "'S'", text)
    text = re.sub(r'"[^"]*"', '"S"', text)

    # Normalize numbers
    text = re.sub(r'\b\d+\b', 'N', text)

    return text.strip()


def hash_traceback(traceback: str | None) -> str | None:
    """Return a SHA-256 hex digest of the normalized traceback, or None."""
    if not traceback:
        return None
    normalized = normalize_traceback(traceback)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def group_failures(run: TestRun) -> list[ErrorGroup]:
    """Group all failed/broken tests in a run by their error signature."""
    groups: dict[str, ErrorGroup] = {}

    for suite in run.suites:
        for case in suite.tests:
            if case.status.value not in ("failed", "broken"):
                continue
            if not case.traceback:
                continue

            h = hash_traceback(case.traceback)
            if h is None:
                continue

            if h not in groups:
                headline = case.message or case.traceback.split('\n')[0]
                groups[h] = ErrorGroup(id=h, headline=headline)

            groups[h].count += 1
            groups[h].tests.append(case.full_name)

    return sorted(groups.values(), key=lambda g: g.count, reverse=True)
