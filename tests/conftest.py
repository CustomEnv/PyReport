"""Shared fixtures for tests."""
from __future__ import annotations

import pytest


@pytest.fixture
def sample_test_run():
    """Build a minimal TestRun with one suite and two test cases."""
    from pyreport.core import (
        CIInfo,
        CommitInfo,
        Status,
        TestCase,
        TestRun,
        TestSuite,
    )

    return TestRun(
        id="run-001",
        project="demo",
        name="CI Run #42",
        suites=[
            TestSuite(
                id="suite-1",
                name="tests/test_api.py",
                duration=2.5,
                status=Status.PASSED,
                tests=[
                    TestCase(
                        id="case-1",
                        name="test_get_users",
                        full_name="tests/test_api.py::test_get_users",
                        duration=0.5,
                        status=Status.PASSED,
                        tags=["smoke", "api"],
                    ),
                    TestCase(
                        id="case-2",
                        name="test_create_user",
                        full_name="tests/test_api.py::test_create_user",
                        duration=1.2,
                        status=Status.FAILED,
                        message="AssertionError: 400 != 201",
                        traceback="Traceback (most recent call last):\n  ...",
                        parameters={"role": "admin"},
                        tags=["api"],
                    ),
                ],
            ),
            TestSuite(
                id="suite-2",
                name="tests/test_ui.py",
                duration=0.8,
                status=Status.PASSED,
                tests=[
                    TestCase(
                        id="case-3",
                        name="test_login",
                        full_name="tests/test_ui.py::test_login",
                        duration=0.8,
                        status=Status.PASSED,
                    ),
                ],
            ),
        ],
        environment={"OS": "ubuntu-22.04", "Python": "3.11"},
        commit=CommitInfo(sha="abc123", branch="main", message="fix tests", author="bot"),
        ci=CIInfo(name="github-actions", url="https://github.com/org/repo/actions/runs/1"),
    )
