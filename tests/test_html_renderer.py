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
