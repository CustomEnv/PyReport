"""Tests for the CLI commands."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pyreport.cli.commands import app
from pyreport.core import Status, TestCase, TestRun, TestSuite, model_to_dict

runner = CliRunner()


def _make_fixture(path: Path, run: TestRun) -> Path:
    """Write a TestRun to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model_to_dict(run), indent=2))
    return path


class TestGenerate:
    def test_generate_from_json(self, tmp_path: Path) -> None:
        run = TestRun(
            id="test-001",
            project="demo",
            name="Demo Run",
            suites=[
                TestSuite(
                    id="s1", name="tests/test_demo.py", duration=0.5, status=Status.PASSED,
                    tests=[
                        TestCase(id="c1", name="test_ok", full_name="test_demo.py::test_ok",
                                 duration=0.1, status=Status.PASSED),
                    ],
                ),
            ],
        )
        run.compute_stats()
        fixture = _make_fixture(tmp_path / "input" / "report.json", run)
        out_dir = tmp_path / "output"

        result = runner.invoke(app, ["generate", str(fixture), "--output", str(out_dir)])
        assert result.exit_code == 0
        assert (out_dir / "index.html").exists()

    def test_generate_file_not_found(self) -> None:
        result = runner.invoke(app, ["generate", "/nonexistent/report.json"])
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_merge_two_reports(self, tmp_path: Path) -> None:
        r1 = TestRun(id="r1", suites=[
            TestSuite(id="s1", name="suite_a.py", duration=0, status=Status.FAILED,
                      tests=[TestCase(id="c1", name="test_fail", full_name="suite_a.py::test_fail",
                                      duration=0.1, status=Status.FAILED, message="err")]),
        ])
        r1.compute_stats()
        r2 = TestRun(id="r2", suites=[
            TestSuite(id="s2", name="suite_b.py", duration=0, status=Status.PASSED,
                      tests=[TestCase(id="c2", name="test_pass", full_name="suite_b.py::test_pass",
                                      duration=0.2, status=Status.PASSED)]),
        ])
        r2.compute_stats()
        f1 = _make_fixture(tmp_path / "r1" / "report.json", r1)
        f2 = _make_fixture(tmp_path / "r2" / "report.json", r2)
        out = tmp_path / "merged"

        result = runner.invoke(app, ["merge", str(f1), str(f2), "-o", str(out)])
        assert result.exit_code == 0, result.output

        html = (out / "index.html").read_text()
        assert "suite_a.py" in html
        assert "suite_b.py" in html
        assert "test_fail" in html
        assert "test_pass" in html

    def test_merge_no_inputs(self) -> None:
        result = runner.invoke(app, ["merge"])
        assert result.exit_code != 0

    def test_generate_multiple_suites(self, tmp_path: Path) -> None:
        run = TestRun(
            id="multi",
            suites=[
                TestSuite(id="s1", name="suite1.py", duration=0.1, status=Status.PASSED,
                          tests=[TestCase(id="c1", name="test_a", full_name="suite1.py::test_a",
                                          duration=0.1, status=Status.PASSED)]),
                TestSuite(id="s2", name="suite2.py", duration=0.1, status=Status.FAILED,
                          tests=[TestCase(id="c2", name="test_b", full_name="suite2.py::test_b",
                                          duration=0.1, status=Status.FAILED,
                                          message="fail", traceback="error")]),
            ],
        )
        run.compute_stats()
        fixture = _make_fixture(tmp_path / "in.json", run)
        out = tmp_path / "out"

        result = runner.invoke(app, ["generate", str(fixture), "-o", str(out)])
        assert result.exit_code == 0

        html = (out / "index.html").read_text()
        assert "suite1.py" in html
        assert "suite2.py" in html
        assert "test_a" in html
        assert "test_b" in html
        assert "fail" in html
