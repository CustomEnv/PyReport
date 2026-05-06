"""JSON renderer — serializes a TestRun to JSON."""
from __future__ import annotations

import json
from pathlib import Path

from pyreport.core import TestRun, model_to_dict
from pyreport.renderers import Renderer


class JSONRenderer(Renderer):
    """Renders a TestRun to a JSON file."""

    def render(self, run: TestRun, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        data = model_to_dict(run)
        path = output_dir / "report.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return path
