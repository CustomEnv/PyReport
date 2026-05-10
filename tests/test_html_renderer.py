"""Tests for the HTML renderer."""
from __future__ import annotations

import json
from pathlib import Path

from pyreport.renderers.static.html_renderer import HTMLRenderer


class TestHTMLRenderer:
    def test_renders_valid_html(self, tmp_path: Path, sample_test_run) -> None:
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)

        assert output.exists()
        html = output.read_text(encoding="utf-8")

        # Basic HTML structure
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

        # Contains data from the test run
        assert "run-001" in html or "demo" in html
        assert "CI Run #42" in html

    def test_contains_stats(self, tmp_path: Path, sample_test_run) -> None:
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        assert "3" in html  # total tests
        assert "2" in html  # passed
        assert "1" in html  # failed

    def test_contains_suites(self, tmp_path: Path, sample_test_run) -> None:
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        assert "tests/test_api.py" in html
        assert "tests/test_ui.py" in html

    def test_contains_test_cases(self, tmp_path: Path, sample_test_run) -> None:
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        assert "test_get_users" in html
        assert "test_create_user" in html
        assert "test_login" in html

    def test_contains_failure_details(self, tmp_path: Path, sample_test_run) -> None:
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        assert "400 != 201" in html
        assert "Traceback" in html

    def test_contains_embedded_data(self, tmp_path: Path, sample_test_run) -> None:
        """The full data is embedded as JSON in the HTML."""
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        # The DATA variable should contain our run data
        assert "const DATA = " in html
        assert "run-001" in html

    def test_embedded_json_is_valid(self, tmp_path: Path, sample_test_run) -> None:
        """Embedded DATA must be parseable JSON (not HTML-escaped)."""
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        prefix = "const DATA = "
        start = html.index(prefix) + len(prefix)
        end = html.index(";", start)
        raw = html[start:end]
        data = json.loads(raw)  # will raise if HTML-escaped
        assert "suites" in data
        assert "stats" in data
        assert data["project"] == "demo"

    def test_search_calls_render_tests(self, tmp_path: Path, sample_test_run) -> None:
        """Search input must call renderTests(), not undefined filterTests()."""
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        assert 'oninput="renderTests()"' in html
        assert 'oninput="filterTests()"' not in html

    def test_all_suites_button_in_sidebar(self, tmp_path: Path, sample_test_run) -> None:
        """Sidebar must have an 'All Suites' button to deselect suites."""
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        assert "All Suites" in html
        assert 'onclick="selectSuite(null)' in html or 'onclick="selectSuite(null' in html

    def test_selectSuite_handles_deselection(self, tmp_path: Path, sample_test_run) -> None:
        """selectSuite JS must handle clicking the same suite again (deselect)."""
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        assert "selectedSuite === suiteId" in html
        assert "suiteId = null" in html

    def test_stdout_stderr_log_sections_use_toggle(self, tmp_path: Path, sample_test_run) -> None:
        """Stdout/stderr/log toggle buttons must use toggleSection()."""
        renderer = HTMLRenderer()
        output = renderer.render(sample_test_run, tmp_path)
        html = output.read_text(encoding="utf-8")

        assert 'toggleSection(this)' in html
        assert '[+] stdout' in html
        assert '[+] stderr' in html

    def test_empty_run(self, tmp_path: Path) -> None:
        """Render a run with zero tests."""
        from pyreport.core import TestRun

        run = TestRun(id="empty")
        run.compute_stats()
        renderer = HTMLRenderer()
        output = renderer.render(run, tmp_path)
        assert output.exists()
        html = output.read_text(encoding="utf-8")
        assert "0" in html


class TestEmbedAttachments:
    def test_embed_small_file(self, tmp_path: Path) -> None:
        from pyreport.core import Attachment, Status, TestCase, TestRun, TestSuite

        # Create a source dir with an attachment
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        att_dir = src_dir / "attachments"
        att_dir.mkdir()
        att_file = att_dir / "hello.txt"
        att_file.write_text("Hello, World!")

        run = TestRun(
            id="test-embed",
            suites=[
                TestSuite(
                    id="s1", name="test_s.py", duration=0.1, status=Status.PASSED,
                    tests=[
                        TestCase(
                            id="c1", name="test_attach", full_name="test_s.py::test_attach",
                            duration=0.1, status=Status.PASSED,
                            attachments=[
                                Attachment(name="hello.txt", path="attachments/hello.txt",
                                           mime_type="text/plain", size=13),
                            ],
                        ),
                    ],
                ),
            ],
        )
        run.compute_stats()

        renderer = HTMLRenderer()
        out = tmp_path / "out"
        renderer.render(run, out, embed_attachments=True, source_dir=src_dir)

        html = (out / "index.html").read_text()
        assert "data:text/plain;base64," in html
        assert "SGVsbG8sIFdvcmxkIQ==" in html  # base64 of "Hello, World!"

    def test_no_embed_large_file(self, tmp_path: Path) -> None:
        from pyreport.core import Attachment, Status, TestCase, TestRun, TestSuite

        src_dir = tmp_path / "source"
        src_dir.mkdir()
        att_dir = src_dir / "attachments"
        att_dir.mkdir()
        att_file = att_dir / "large.bin"
        # Create a 200KB file (over 100KB limit)
        att_file.write_bytes(b"X" * (200 * 1024))

        run = TestRun(
            id="test-large",
            suites=[
                TestSuite(
                    id="s1", name="test_s.py", duration=0.1, status=Status.PASSED,
                    tests=[
                        TestCase(
                            id="c1", name="test_large", full_name="test_s.py::test_large",
                            duration=0.1, status=Status.PASSED,
                            attachments=[
                                Attachment(name="large.bin", path="attachments/large.bin",
                                           mime_type="application/octet-stream", size=200*1024),
                            ],
                        ),
                    ],
                ),
            ],
        )
        run.compute_stats()

        renderer = HTMLRenderer()
        out = tmp_path / "out"
        renderer.render(run, out, embed_attachments=True, source_dir=src_dir)

        html = (out / "index.html").read_text()
        assert "data:application/octet-stream;base64," not in html
        assert "attachments/large.bin" in html

    def test_embed_no_source_dir_fallback(self, tmp_path: Path) -> None:
        from pyreport.core import Attachment, Status, TestCase, TestRun, TestSuite

        run = TestRun(
            id="test-no-src",
            suites=[
                TestSuite(
                    id="s1", name="test_s.py", duration=0.1, status=Status.PASSED,
                    tests=[
                        TestCase(
                            id="c1", name="test_attach", full_name="test_s.py::test_attach",
                            duration=0.1, status=Status.PASSED,
                            attachments=[
                                Attachment(name="f.txt", path="attachments/f.txt",
                                           mime_type="text/plain", size=5),
                            ],
                        ),
                    ],
                ),
            ],
        )
        run.compute_stats()

        renderer = HTMLRenderer()
        out = tmp_path / "out"
        # embed=True but no source_dir with file → should not crash, keep path
        renderer.render(run, out, embed_attachments=True, source_dir=tmp_path / "nonexistent")
        html = (out / "index.html").read_text()
        assert "attachments/f.txt" in html


class TestRenderHistory:
    def test_render_history_empty(self, tmp_path: Path) -> None:
        """render_history with no data should not crash."""
        renderer = HTMLRenderer()
        out = tmp_path / "history"
        path = renderer.render_history(output_dir=out)
        assert path.exists()
        html = path.read_text()
        assert "Test History" in html
        assert "No runs recorded yet" in html

    def test_render_history_with_flaky_only(self, tmp_path: Path) -> None:
        """render_history with flaky data shows flaky section."""
        from pyreport.analyzers.flaky import FlakyTest

        renderer = HTMLRenderer()
        out = tmp_path / "history"
        flaky_tests = [
            FlakyTest("t1", "test_flaky", "suite.py", 3, 0.67, 2, ["p", "f", "p"]),
        ]

        path = renderer.render_history(
            flaky_tests=flaky_tests,
            run_meta_list=[{"id": "r1", "timestamp": "2026-05-01", "total": 3,
                            "passed": 2, "failed": 1, "broken": 0, "skipped": 0,
                            "pass_rate": 66.7, "duration": 5.0}],
            output_dir=out,
        )
        html = path.read_text()
        assert "test_flaky" in html
        assert "0.67" in html

    def test_render_history_with_trends_only(self, tmp_path: Path) -> None:
        """render_history with trend data shows trends section."""
        from pyreport.analyzers.trends import DurationPoint, DurationTrend

        renderer = HTMLRenderer()
        out = tmp_path / "history"
        trends = [
            DurationTrend("t1", "test_slow", "suite.py", [
                DurationPoint("r1", "2026-05-01", 0.5),
                DurationPoint("r2", "2026-05-02", 1.5),
            ], change_pct=200.0),
        ]

        path = renderer.render_history(
            trends=trends,
            run_meta_list=[{"id": "r1", "timestamp": "2026-05-01", "total": 1,
                            "passed": 1, "failed": 0, "broken": 0, "skipped": 0,
                            "pass_rate": 100.0, "duration": 0.5}],
            output_dir=out,
        )
        html = path.read_text()
        assert "test_slow" in html
        assert "200.0" in html

    def test_render_history_with_slowest_tests(self, tmp_path: Path) -> None:
        """render_history with slowest tests data."""
        from pyreport.core import Status, TestCase

        renderer = HTMLRenderer()
        out = tmp_path / "history"
        slowest = [
            TestCase(id="t1", name="test_slow", full_name="t1",
                     duration=2.5, status=Status.PASSED),
        ]

        path = renderer.render_history(
            slowest_tests=slowest,
            run_meta_list=[{"id": "r1", "timestamp": "2026-05-01", "total": 1,
                            "passed": 1, "failed": 0, "broken": 0, "skipped": 0,
                            "pass_rate": 100.0, "duration": 2.5}],
            output_dir=out,
        )
        html = path.read_text()
        assert "test_slow" in html
        assert "Slowest Tests" in html
