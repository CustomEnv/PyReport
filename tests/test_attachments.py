"""Tests for attachment support in the pytest plugin."""
from __future__ import annotations

import json

import pytest

pytest_plugins = ("pytester",)


class TestAttachments:
    def test_attach_text_file(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            test_attach="""
            def test_with_attachment(pyreport_attach):
                pyreport_attach("note.txt", b"hello world", "text/plain")
                assert True
            """,
        )
        pytester.runpytest("--pyreport", "--pyreport-output", "report")
        data = json.loads((pytester.path / "report" / "report.json").read_text())
        case = data["suites"][0]["tests"][0]
        assert len(case["attachments"]) == 1
        att = case["attachments"][0]
        assert att["name"] == "note.txt"
        assert att["mime_type"] == "text/plain"
        assert att["size"] == 11

    def test_attach_file_copied_to_output(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            test_attach="""
            def test_with_file(pyreport_attach):
                pyreport_attach("data.bin", b"\\x00\\x01\\x02", "application/octet-stream")
                assert True
            """,
        )
        pytester.runpytest("--pyreport", "--pyreport-output", "report")
        attachments_dir = pytester.path / "report" / "attachments"
        assert attachments_dir.is_dir()
        files = list(attachments_dir.iterdir())
        assert len(files) == 1

    def test_multiple_attachments(self, pytester: pytest.Pytester) -> None:
        pytester.makepyfile(
            test_multi="""
            def test_multi_attach(pyreport_attach):
                pyreport_attach("a.txt", b"aaa", "text/plain")
                pyreport_attach("b.txt", b"bbb", "text/plain")
                assert True
            """,
        )
        pytester.runpytest("--pyreport", "--pyreport-output", "report")
        data = json.loads((pytester.path / "report" / "report.json").read_text())
        attachments = data["suites"][0]["tests"][0]["attachments"]
        assert len(attachments) == 2
        names = {a["name"] for a in attachments}
        assert names == {"a.txt", "b.txt"}

    def test_attachments_in_html_report(self, pytester: pytest.Pytester) -> None:
        """Attachments should appear in the HTML report."""
        pytester.makepyfile(
            test_att="""
            def test_attached(pyreport_attach):
                pyreport_attach("log.txt", b"test output", "text/plain")
                assert True
            """,
        )
        pytester.runpytest("--pyreport", "--pyreport-output", "report")
        html = (pytester.path / "report" / "index.html").read_text()
        assert "log.txt" in html

    def test_attachment_without_fixture(self, pytester: pytest.Pytester) -> None:
        """Test without pyreport_attach fixture still works."""
        pytester.makepyfile(
            test_normal="""
            def test_normal():
                assert True
            """,
        )
        result = pytester.runpytest("--pyreport", "--pyreport-output", "report")
        assert result.ret == 0
        data = json.loads((pytester.path / "report" / "report.json").read_text())
        assert data["stats"]["passed"] == 1
