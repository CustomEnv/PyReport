"""HTML static site renderer — produces a standalone HTML report."""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from pyreport.core import TestRun, model_to_dict
from pyreport.renderers import Renderer


class HTMLRenderer(Renderer):
    """Renders a TestRun to a standalone HTML file."""

    def __init__(self) -> None:
        self.env = Environment(
            loader=PackageLoader("pyreport.renderers.static", "templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render(self, run: TestRun, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        template = self.env.get_template("report.html")
        data = model_to_dict(run)
        html = template.render(run=data, data_json=json.dumps(data))
        path = output_dir / "index.html"
        path.write_text(html, encoding="utf-8")
        return path
