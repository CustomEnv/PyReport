"""Integration tests: end-to-end flow with real pytest runs."""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from pyreport.cli.commands import app

pytest_plugins = ("pytester",)
runner = CliRunner()


class TestEndToEnd:
    """Full end-to-end: pytest -> report.json -> CLI -> HTML."""

    def test_pytest_plugin_generates_html(self, pytester: pytest.Pytester) -> None:
        """pytest --pyreport generates both JSON and HTML."""
        pytester.makepyfile(
            test_demo="""
            import pytest

            def test_pass():
                assert True

            @pytest.mark.smoke
            def test_with_marker():
                assert True

            def test_fail():
                assert 1 == 2
            """,
        )

        result = pytester.runpytest(
            "--pyreport",
            "--pyreport-output", "report",
        )
        assert result.ret == 1  # one fail

        output_dir = pytester.path / "report"
        assert (output_dir / "report.json").exists()
        assert (output_dir / "index.html").exists()

        # Verify JSON content
        data = json.loads((output_dir / "report.json").read_text())
        assert data["stats"]["total"] == 3
        assert data["stats"]["passed"] == 2
        assert data["stats"]["failed"] == 1

        # Verify marker was collected
        tests = [t for s in data["suites"] for t in s["tests"]]
        markers = [t["tags"] for t in tests if t["name"] == "test_with_marker"]
        assert len(markers) == 1
        assert "smoke" in markers[0]

        # Verify traceback on failed test
        failed = [t for t in tests if t["status"] == "failed"][0]
        assert "1 == 2" in failed["traceback"]

        # Verify HTML is valid
        html = (output_dir / "index.html").read_text()
        assert "<!DOCTYPE html>" in html
        assert "test_pass" in html
        assert "test_fail" in html
        assert "test_with_marker" in html

    def test_cli_generate_from_plugin_output(self, pytester: pytest.Pytester) -> None:
        """CLI generate works with pytest plugin output."""
        pytester.makepyfile(
            example_test="""
            def test_ok():
                assert True
            """,
        )

        pytester.runpytest(
            "--pyreport",
            "--pyreport-output", "report",
        )

        json_path = pytester.path / "report" / "report.json"
        out_dir = pytester.path / "html-report"

        result = runner.invoke(app, [
            "generate", str(json_path),
            "-o", str(out_dir),
        ])
        assert result.exit_code == 0

        html = (out_dir / "index.html").read_text()
        assert "test_ok" in html

    def test_pytest_plugin_marks(self, pytester: pytest.Pytester) -> None:
        """Custom markers appear in report tags."""
        pytester.makepyfile(
            test_marks="""
            import pytest

            @pytest.mark.slow
            @pytest.mark.integration
            def test_heavy():
                assert True
            """,
        )

        pytester.runpytest(
            "--pyreport",
            "--pyreport-output", "report",
        )

        data = json.loads((pytester.path / "report" / "report.json").read_text())
        tests = [t for s in data["suites"] for t in s["tests"]]
        assert tests[0]["tags"] == ["integration", "slow"]


class TestRichReport:
    """Integration test: generates a report with all Phase 1 features visible."""

    def test_rich_report_with_all_features(self, pytester: pytest.Pytester) -> None:
        """Generate a report with stdout, stderr, log, attachments, and failures."""
        pytester.makepyfile(
            test_rich="""
            def test_with_stdout():
                print("Hello from stdout")
                print("More output", flush=True)
                assert True

            def test_with_stderr():
                import sys
                print("Error message", file=sys.stderr)
                assert True

            def test_with_logging():
                import logging
                logging.warning("User logged in")
                logging.error("Response time 1500ms")
                assert True

            def test_with_attachment(pyreport_attach):
                pyreport_attach("screenshot.png", b"fake-png-data", "image/png")
                pyreport_attach("log.txt", b"session log", "text/plain")
                assert True

            def test_all_together(pyreport_attach):
                import sys
                print("Processing data")
                print("Error in step 2", file=sys.stderr)
                pyreport_attach("output.json", b'{"ok": true}', "application/json")
                assert True

            def test_failure_with_details(pyreport_attach):
                print("Starting computation")
                pyreport_attach("config.xml", b"<config/>", "text/xml")
                assert 1 == 2, "Expected 200, got 500"
            """,
        )

        result = pytester.runpytest(
            "-v",
            "--pyreport",
            "--pyreport-output", "report",
        )
        assert result.ret == 1  # one fail

        output_dir = pytester.path / "report"
        data = json.loads((output_dir / "report.json").read_text())

        # Verify stats
        assert data["stats"]["total"] == 6
        assert data["stats"]["passed"] == 5
        assert data["stats"]["failed"] == 1

        # Verify stdout/stderr/log capture
        tests = {t["name"]: t for s in data["suites"] for t in s["tests"]}
        assert "Hello from stdout" in tests["test_with_stdout"]["stdout"]
        assert "Error message" in tests["test_with_stderr"]["stderr"]
        assert "User logged in" in tests["test_with_logging"]["log"]

        # Verify attachments exist
        assert len(tests["test_with_attachment"]["attachments"]) == 2
        names = {a["name"] for a in tests["test_with_attachment"]["attachments"]}
        assert names == {"screenshot.png", "log.txt"}

        # Verify test with both stdout, stderr, and attachments
        all_together = tests["test_all_together"]
        assert "Processing data" in all_together["stdout"]
        assert "Error in step 2" in all_together["stderr"]
        assert len(all_together["attachments"]) == 1

        # Verify failure with details
        failed = tests["test_failure_with_details"]
        assert failed["status"] == "failed"
        assert "Expected 200, got 500" in (failed.get("traceback") or "")
        assert len(failed["attachments"]) == 1

        # Attachment files exist on disk
        attachments_dir = output_dir / "attachments"
        assert attachments_dir.is_dir()
        assert len(list(attachments_dir.iterdir())) == 4  # 4 attachments total

        # HTML contains all features
        html = (output_dir / "index.html").read_text()
        assert "Hello from stdout" in html
        assert "Error message" in html
        assert "User logged in" in html
        assert "screenshot.png" in html
        assert "config.xml" in html
        assert "Expected 200, got 500" in html
        assert "Error Groups" in html
