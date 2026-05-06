"""Tests for the pytest plugin."""
from __future__ import annotations

import json

import pytest

pytest_plugins = ("pytester",)


class TestPyReportPlugin:
    def test_generates_report_with_results(self, pytester: pytest.Pytester) -> None:
        """--pyreport produces a JSON report with correct stats."""
        pytester.makepyfile(
            test_demo="""
            def test_pass():
                assert True

            def test_fail():
                assert False

            def test_skip():
                import pytest
                pytest.skip("not ready")
            """,
        )

        result = pytester.runpytest("--pyreport", "--pyreport-output", "report")
        assert result.ret == 1  # one failure

        report_file = pytester.path / "report" / "report.json"
        assert report_file.exists()

        data = json.loads(report_file.read_text())
        assert data["stats"]["total"] == 3
        assert data["stats"]["passed"] == 1
        assert data["stats"]["failed"] == 1
        assert data["stats"]["skipped"] == 1
        assert data["status"] == "failed"

    def test_all_pass(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            test_all_good="""
            def test_one():
                assert 1 + 1 == 2
            def test_two():
                assert "hello".upper() == "HELLO"
            """,
        )

        result = pytester.runpytest("--pyreport", "--pyreport-output", "report")
        assert result.ret == 0

        report_file = pytester.path / "report" / "report.json"
        data = json.loads(report_file.read_text())
        assert data["stats"]["total"] == 2
        assert data["stats"]["passed"] == 2
        assert data["status"] == "passed"

    def test_suite_structure(self, pytester: pytest.Pytester) -> None:
        """Tests are grouped into suites by file."""
        pytester.makepyfile(
            test_foo="""
            def test_foo_pass():
                assert True
            """,
            test_bar="""
            def test_bar_pass():
                assert True
            """,
        )

        pytester.runpytest("--pyreport", "--pyreport-output", "report")
        data = json.loads((pytester.path / "report" / "report.json").read_text())

        suite_names = {s["name"] for s in data["suites"]}
        assert "test_foo.py" in suite_names
        assert "test_bar.py" in suite_names
        assert data["stats"]["total"] == 2

    def test_parametrized_tests(self, pytester: pytest.Pytester) -> None:
        """Parametrized tests capture parameters."""
        pytester.makepyfile(
            test_param="""
            import pytest

            @pytest.mark.parametrize("x,y,expected", [
                (1, 2, 3),
                (4, 5, 9),
            ])
            def test_add(x, y, expected):
                assert x + y == expected
            """,
        )

        pytester.runpytest("--pyreport", "--pyreport-output", "report")
        data = json.loads((pytester.path / "report" / "report.json").read_text())

        assert data["stats"]["passed"] == 2

    def test_traceback_on_failure(self, pytester: pytest.Pytester) -> None:
        """Failed tests include a traceback."""
        pytester.makepyfile(
            test_errors="""
            def test_bad():
                raise ValueError("something broke")
            """,
        )

        pytester.runpytest("--pyreport", "--pyreport-output", "report")
        data = json.loads((pytester.path / "report" / "report.json").read_text())

        case = data["suites"][0]["tests"][0]
        assert case["status"] == "failed"
        assert case["message"] is not None
        assert "ValueError" in case["traceback"]
