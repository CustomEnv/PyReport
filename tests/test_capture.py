"""Tests for stdout/stderr and log capture in the plugin."""
from __future__ import annotations

import json

import pytest

pytest_plugins = ("pytester",)


class TestStdoutCapture:
    def test_captures_stdout(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            test_print="""
            def test_prints():
                print("hello from test")
                assert True
            """,
        )
        pytester.runpytest("--pyreport", "--pyreport-output", "report")
        data = json.loads((pytester.path / "report" / "report.json").read_text())
        case = data["suites"][0]["tests"][0]
        assert case["stdout"] is not None
        assert "hello from test" in case["stdout"]

    def test_captures_stderr(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            test_err="""
            import sys
            def test_stderr():
                print("error output", file=sys.stderr)
                assert True
            """,
        )
        pytester.runpytest("--pyreport", "--pyreport-output", "report")
        data = json.loads((pytester.path / "report" / "report.json").read_text())
        case = data["suites"][0]["tests"][0]
        assert case["stderr"] is not None
        assert "error output" in case["stderr"]

    def test_captures_logging(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            test_log="""
            import logging
            LOG = logging.getLogger(__name__)
            def test_logging():
                LOG.warning("warning message")
                assert True
            """,
        )
        pytester.runpytest("--pyreport", "--pyreport-output", "report",
                           "-p", "logging")
        data = json.loads((pytester.path / "report" / "report.json").read_text())
        case = data["suites"][0]["tests"][0]
        assert case["log"] is not None
