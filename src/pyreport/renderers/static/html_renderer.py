"""HTML static site renderer — produces a standalone HTML report."""
from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from pyreport.core import TestRun, model_to_dict
from pyreport.renderers import Renderer

_MAX_EMBED_SIZE = 100 * 1024  # 100KB


def _embed_file_as_data_uri(path: str, source_dir: Path) -> str:
    """Read a file and return a base64 data URI.

    Falls back to the original path if file is not found or too large.
    """
    full_path = source_dir / path
    if not full_path.is_file():
        return path  # fallback to original path

    try:
        data = full_path.read_bytes()
    except OSError:
        return path

    if len(data) > _MAX_EMBED_SIZE:
        return path  # too large, keep as link

    mime_type, _ = mimetypes.guess_type(str(full_path))
    if mime_type is None:
        mime_type = "application/octet-stream"

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _embed_attachments(data: dict, source_dir: Path) -> None:
    """Walk through report data and embed small attachments as data URIs."""
    for suite in data.get("suites", []):
        for case in suite.get("tests", []):
            for att in case.get("attachments", []):
                att["path"] = _embed_file_as_data_uri(att["path"], source_dir)


class HTMLRenderer(Renderer):
    """Renders a TestRun to a standalone HTML file."""

    def __init__(self) -> None:
        self.env = Environment(
            loader=PackageLoader("pyreport.renderers.static", "templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render(self, run: TestRun, output_dir: Path,
               embed_attachments: bool = False,
               source_dir: Path | None = None) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        template = self.env.get_template("report.html")
        data = model_to_dict(run)

        if embed_attachments and source_dir is not None:
            _embed_attachments(data, source_dir)

        html = template.render(run=data, data_json=json.dumps(data))
        path = output_dir / "index.html"
        path.write_text(html, encoding="utf-8")
        return path

    def render_history(
        self,
        flaky_tests: list | None = None,
        trends: list | None = None,
        output_dir: Path = Path("pyreport-history"),
        run_meta_list: list[dict] | None = None,
        slowest_tests: list | None = None,
    ) -> Path:
        """Generate a history HTML page showing flaky tests, trends, and run timeline."""
        output_dir.mkdir(parents=True, exist_ok=True)
        template = self.env.get_template("history.html")

        runs_data = run_meta_list or []
        flaky_data = [{
            "test_id": f.test_id,
            "name": f.name,
            "suite": f.suite,
            "total_runs": f.total_runs,
            "flaky_score": f.flaky_score,
            "status_changes": f.status_changes,
            "statuses": f.statuses,
        } for f in (flaky_tests or [])]

        trends_data = [{
            "test_id": t.test_id,
            "name": t.name,
            "suite": t.suite,
            "points": [
                {"run_id": p.run_id, "timestamp": p.timestamp, "duration": p.duration}
                for p in t.points
            ],
            "change_pct": t.change_pct,
            "avg_duration": round(t.avg_duration, 3),
            "max_duration": round(t.max_duration, 3),
            "latest_duration": round(t.latest_duration, 3),
        } for t in (trends or [])]

        slowest_data = [{
            "name": t.name,
            "suite": t.suite.name if hasattr(t, "suite") and hasattr(t.suite, "name") else "",
            "duration": t.duration,
            "status": t.status.value,
        } for t in (slowest_tests or [])]

        html = template.render(
            runs=runs_data,
            flaky_tests=flaky_data,
            trends=trends_data,
            slowest_tests=slowest_data,
            runs_json=json.dumps(runs_data),
            flaky_json=json.dumps(flaky_data),
            trends_json=json.dumps(trends_data),
        )
        path = output_dir / "history.html"
        path.write_text(html, encoding="utf-8")
        return path
