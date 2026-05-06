"""Renderer base and built-in renderers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pyreport.core import TestRun


class Renderer(ABC):
    """Base class for all renderers."""

    @abstractmethod
    def render(self, run: TestRun, output_dir: Path) -> Path:
        """Render a TestRun to the output directory. Returns path to the main output file."""
        ...
