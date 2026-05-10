"""PyTest plugin: collects test results and generates PyReport."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from pyreport.core import (
    Attachment,
    Status,
    TestCase,
    TestRun,
    TestSuite,
    model_to_dict,
)
from pyreport.history.store import HistoryStore
from pyreport.renderers.static.html_renderer import HTMLRenderer


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("pyreport")
    group.addoption(
        "--pyreport",
        action="store_true",
        default=False,
        help="Generate PyReport test report",
    )
    group.addoption(
        "--pyreport-output",
        default="pyreport-output",
        help="Output directory for PyReport (default: pyreport-output)",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--pyreport", default=False):
        plugin = PyReportPlugin(config)
        config.pluginmanager.register(plugin)
        config._pyreport_plugin = plugin  # type: ignore[attr-defined]


@pytest.fixture
def pyreport_attach(request: pytest.FixtureRequest) -> None:
    """Fixture to attach files to a test.

    Usage:
        def test_screenshot(pyreport_attach):
            pyreport_attach("screenshot.png", data, "image/png")
    """
    plugin = getattr(request.config, "_pyreport_plugin", None)
    if plugin is None:
        return None

    def _attach(name: str, data: bytes, mime_type: str = "application/octet-stream") -> None:
        plugin._add_attachment(request.node.nodeid, name, data, mime_type)

    return _attach


def pytest_unconfigure(config: pytest.Config) -> None:
    plugin = getattr(config, "_pyreport_plugin", None)
    if plugin is not None:
        config.pluginmanager.unregister(plugin)
        del config._pyreport_plugin  # type: ignore[attr-defined]


class PyReportPlugin:
    """Collects test run data and writes a report at session end."""

    def __init__(self, config: pytest.Config) -> None:
        self.config = config
        self.output_dir = Path(str(config.getoption("--pyreport-output")))
        self.test_cases: dict[str, TestCase] = {}
        self.attachments: dict[str, list[Attachment]] = {}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo) -> None:  # noqa: ARG002
        outcome = yield
        report = outcome.get_result()
        # Capture results from "call" phase (normal test execution)
        # and "setup" phase (for skipped tests that never reach "call")
        if call.when == "call" or (call.when == "setup" and report.skipped):
            self._record_test(item, report)

    def _add_attachment(self, node_id: str, name: str, data: bytes,
                        mime_type: str = "text/plain") -> Attachment:
        """Store an attachment and copy it to the output dir."""
        from hashlib import md5

        ext = name.rsplit(".", 1)[-1] if "." in name else "bin"
        digest = md5(data).hexdigest()[:12]
        fname = f"{digest}.{ext}"
        attachments_dir = self.attachments_dir
        attachments_dir.mkdir(parents=True, exist_ok=True)
        dest = attachments_dir / fname
        dest.write_bytes(data)

        att = Attachment(
            name=name, path=f"attachments/{fname}", mime_type=mime_type, size=len(data),
        )
        self.attachments.setdefault(node_id, []).append(att)
        return att

    @property
    def attachments_dir(self) -> Path:
        return self.output_dir / "attachments"

    def _record_test(self, item: pytest.Item, report: pytest.TestReport) -> None:
        node_id = item.nodeid

        parameters: dict[str, str] = {}
        if hasattr(item, "callspec"):
            parameters = {k: str(v) for k, v in item.callspec.params.items()}

        status = self._resolve_status(report)

        message: str | None = None
        traceback: str | None = None
        if report.failed:
            message = str(report.head_line) if report.head_line else "Test failed"
            longrepr = getattr(report, "longreprtext", None)
            traceback = str(longrepr) if longrepr else None

        # Collect custom markers (skip built-in ones)
        tags = sorted({m.name for m in item.iter_markers() if not m.name.startswith("_")})

        case_attachments = self.attachments.pop(node_id, [])
        self.test_cases[node_id] = TestCase(
            id=node_id,
            name=item.name,
            full_name=node_id,
            test_id=node_id.split("[")[0],  # stable id without params
            duration=getattr(report, "duration", 0.0),
            status=status,
            message=message,
            traceback=traceback,
            parameters=parameters,
            tags=tags,
            attachments=case_attachments,
            stdout=getattr(report, "capstdout", None),
            stderr=getattr(report, "capstderr", None),
            log=getattr(report, "caplog", None),
        )

    @staticmethod
    def _resolve_status(report: pytest.TestReport) -> Status:
        if report.passed:
            return Status.PASSED
        if report.failed:
            return Status.FAILED
        if report.skipped:
            return Status.SKIPPED
        return Status.BROKEN

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if not self.test_cases:
            return

        run = self._build_run(session)
        self._write_report(run)

    def _build_run(self, session: pytest.Session) -> TestRun:
        suite_map: dict[str, list[TestCase]] = {}
        for node_id, case in self.test_cases.items():
            suite_name = node_id.split("::")[0]
            suite_map.setdefault(suite_name, []).append(case)

        suites = [
            TestSuite(
                id=name,
                name=name,
                duration=round(max(c.duration for c in cases), 3),
                status=self._suite_status(cases),
                tests=cases,
            )
            for name, cases in suite_map.items()
        ]

        total_duration = round(sum(c.duration for c in self.test_cases.values()), 3)
        env = self._collect_environment()

        run = TestRun(
            id=datetime.now().strftime("%Y%m%d%H%M%S"),
            project=Path(session.config.rootpath).name,
            name=f"Test Run {datetime.now().isoformat()}",
            timestamp=datetime.now(),
            duration=total_duration,
            suites=suites,
            environment=env,
        )
        run.compute_stats()
        return run

    @staticmethod
    def _suite_status(cases: list[TestCase]) -> Status:
        for s in (Status.FAILED, Status.BROKEN):
            if any(c.status == s for c in cases):
                return s
        if any(c.status == Status.SKIPPED for c in cases):
            if all(c.status == Status.SKIPPED for c in cases):
                return Status.SKIPPED
        return Status.PASSED

    @staticmethod
    def _collect_environment() -> dict[str, str]:
        env = {}
        for key in ("CI", "GITHUB_ACTIONS", "GITHUB_SHA", "GITHUB_REF_NAME",
                     "GITHUB_RUN_ID", "GITHUB_SERVER_URL", "GITHUB_REPOSITORY",
                     "PYTHON_VERSION", "OS", "TZ"):
            val = os.environ.get(key)
            if val is not None:
                env[key] = val
        return env

    def _write_report(self, run: TestRun) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        data = model_to_dict(run)

        # Write JSON
        json_path = self.output_dir / "report.json"
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

        # Save to history store
        try:
            store = HistoryStore(self.output_dir / ".pyreport_history")
            store.save_run(run)
        except Exception:  # noqa: BLE001
            pass  # non-blocking — should not break test run

        # Write HTML
        try:
            renderer = HTMLRenderer()
            renderer.render(run, self.output_dir)
        except Exception as exc:  # noqa: BLE001
            import warnings
            warnings.warn(f"Failed to generate HTML report: {exc}")
