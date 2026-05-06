#!/usr/bin/env python3
"""Generate a rich demo report showcasing all PyReport features.

Generates multiple test runs to demonstrate history, flaky detection,
and duration trends alongside Phase 0 and Phase 1 features.

Usage:
    python scripts/generate_demo.py [--output /tmp/pyreport-demo]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from pyreport.analyzers.flaky import detect_flaky
from pyreport.analyzers.trends import analyze_duration, get_slowest_tests
from pyreport.core import Attachment, Status, TestCase, TestRun, TestSuite
from pyreport.history.store import HistoryStore
from pyreport.renderers.static.html_renderer import HTMLRenderer

SUITE_API = "tests/test_api.py"
SUITE_AUTH = "tests/test_auth.py"
SUITE_UI = "tests/test_ui.py"
SUITE_ORDERS = "tests/test_orders.py"


def _build_run(
    run_id: str,
    timestamp: datetime,
    durations: dict[str, float],
    statuses: dict[str, str],
) -> TestRun:
    """Build a TestRun with given parameters.

    Args:
        run_id: Unique run identifier.
        timestamp: Run timestamp.
        durations: Dict mapping test_id -> duration in seconds.
        statuses: Dict mapping test_id -> status string.
    """
    tests = {}
    for test_id in durations:
        params: dict[str, str] = {}
        name = test_id.split("::")[-1]
        if "[" in name:
            name = name.split("[")[0]
            param_str = test_id.split("[")[1].rstrip("]")
            for p in param_str.split("-"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = v

        full_name = test_id
        status_str = statuses.get(test_id, "passed")
        status = Status(status_str)

        message = None
        traceback = None
        if status == Status.FAILED:
            message = "AssertionError: Expected 200, got 500"
            traceback = (
                f'  File "{test_id.rsplit("::", 1)[0]}", line 42, in {name}\n'
                f"    assert response.status == 200\n"
                f"AssertionError: Expected 200, got 500\n"
            )
        elif status == Status.BROKEN:
            message = "ConnectionError: Database timeout"
            traceback = (
                f'  File "{test_id.rsplit("::", 1)[0]}", line 55, in {name}\n'
                f"    db.execute('SELECT 1')\n"
                f'  File "db/client.py", line 88, in execute\n'
                f"    raise ConnectionError('Database timeout')\n"
                f"ConnectionError: Database timeout\n"
            )

        tests[test_id] = TestCase(
            id=test_id,
            name=name,
            full_name=full_name,
            test_id=test_id.split("[")[0],
            duration=durations[test_id],
            status=status,
            message=message,
            traceback=traceback,
            parameters=params,
            tags=_tags_for(test_id),
            stdout=_stdout_for(test_id),
            stderr=_stderr_for(test_id),
            log=_log_for(test_id),
        )

    # Organize tests into suites based on filename
    suite_map: dict[str, list[TestCase]] = {}
    for test_id, case in tests.items():
        suite_name = test_id.split("::")[0]
        suite_map.setdefault(suite_name, []).append(case)

    suites = []
    for name, cases in suite_map.items():
        max_duration = max(c.duration for c in cases)
        suite_status = Status.PASSED
        for s in (Status.FAILED, Status.BROKEN):
            if any(c.status == s for c in cases):
                suite_status = s
                break
        suites.append(TestSuite(
            id=name, name=name, duration=round(max_duration, 3),
            status=suite_status, tests=cases,
        ))

    total_duration = round(sum(durations.values()), 3)
    run = TestRun(
        id=run_id,
        project="PyReport Demo",
        name=f"Demo Run ({timestamp.strftime('%Y-%m-%d %H:%M')})",
        timestamp=timestamp,
        duration=total_duration,
        suites=suites,
        environment={
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_SHA": f"abc{run_id[-3:]}def",
            "GITHUB_REF_NAME": "main",
            "GITHUB_RUN_ID": run_id,
            "GITHUB_REPOSITORY": "user/pyreport",
            "GITHUB_SERVER_URL": "https://github.com",
            "OS": "macOS",
            "PYTHON_VERSION": "3.11",
            "TZ": "UTC",
        },
    )
    run.compute_stats()
    return run


def _tags_for(test_id: str) -> list[str]:
    tags = {"smoke"}
    if "auth" in test_id:
        tags.add("security")
    if "ui" in test_id or "screenshot" in test_id:
        tags.add("visual")
    if "order" in test_id:
        tags.add("critical-path")
    return sorted(tags)


def _make_demo_png(width: int = 200, height: int = 100) -> bytes:
    """Generate a small visible PNG with colored bars (pure Python, no deps)."""
    import struct
    import zlib

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))  # 8-bit RGB

    raw = bytearray()
    bar_w = max(1, width // 5)
    colors = [(255, 80, 80), (80, 255, 80), (80, 130, 255), (255, 220, 50), (180, 100, 255)]
    for y in range(height):
        raw.append(0)  # filter byte
        for x in range(width):
            r, g, b = colors[(x // bar_w) % len(colors)]
            raw.extend([r, g, b])
    idat = chunk(b"IDAT", zlib.compress(bytes(raw)))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _create_demo_attachments(output_dir: Path) -> Path:
    """Create demo attachment files and return the attachments directory."""
    att_dir = output_dir / "attachments"
    att_dir.mkdir(parents=True, exist_ok=True)

    # Visible PNG with colored bars
    (att_dir / "screenshot.png").write_bytes(_make_demo_png())

    # Small HTML page source
    (att_dir / "page_source.html").write_text(
        "<html><body><h1>Dashboard</h1><p>Welcome to the dashboard.</p></body></html>"
    )

    return att_dir


def _add_attachments(run: TestRun, att_dir: Path, test_ids: list[str]) -> None:
    """Attach real files to specific tests in a run."""
    for suite in run.suites:
        for case in suite.tests:
            case_id = case.full_name or case.id
            if case_id in test_ids or any(t in case_id for t in test_ids):
                if "screenshot" in case_id:
                    file_path = att_dir / "screenshot.png"
                    case.attachments.append(Attachment(
                        name="screenshot.png",
                        path="attachments/screenshot.png",
                        mime_type="image/png",
                        size=file_path.stat().st_size,
                    ))
                if "form_submit" in case_id:
                    file_path = att_dir / "page_source.html"
                    case.attachments.append(Attachment(
                        name="page_source.html",
                        path="attachments/page_source.html",
                        mime_type="text/html",
                        size=file_path.stat().st_size,
                    ))


def _stdout_for(test_id: str) -> str | None:
    if "get_users" in test_id:
        return 'GET /api/users -> 200\nResponse: [{"id": 1, "name": "Alice"}]'
    if "create_user" in test_id:
        return "POST /api/users -> 201\nCreated user #42"
    if "delete_user" in test_id:
        return "DELETE /api/users/42 -> 403"
    if "login" in test_id:
        return "POST /auth/login -> 200\nToken: eyJ..."
    if "screenshot" in test_id:
        return "Screenshot saved: /tmp/screen.png"
    if "create_order" in test_id:
        return "Order #9876 created"
    if "cancel_order" in test_id:
        return "Attempting to cancel order #9876"
    return None


def _stderr_for(test_id: str) -> str | None:
    if "create_user" in test_id:
        return "[WARN] Rate limit: 100/1000 requests used"
    if "form_submit" in test_id:
        return "[WARN] Deprecated: submit() will be removed in v3"
    if "cancel_order" in test_id:
        return "[ERROR] Connection pool exhausted"
    return None


def _log_for(test_id: str) -> str | None:
    if "screenshot" in test_id:
        return (
            "2026-05-05 20:00:01 [INFO] Page loaded\n"
            "2026-05-05 20:00:02 [INFO] Element found\n"
            "2026-05-05 20:00:02 [DEBUG] Screenshot captured"
        )
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PyReport demo report")
    parser.add_argument(
        "--output", "-o",
        default="pyreport-demo",
        help="Output directory (default: pyreport-demo)",
    )
    args = parser.parse_args()

    out = Path(args.output)
    renderer = HTMLRenderer()

    # ── Generate 3 historical runs for flaky/trend analysis ──────────────
    base_time = datetime(2026, 5, 4, 10, 0, 0)
    store = HistoryStore(out / ".pyreport_history")

    # Run 1: all tests pass except test_delete_user
    run1 = _build_run(
        run_id="demo-001",
        timestamp=base_time,
        durations={
            "tests/test_api.py::test_get_users": 0.3,
            "tests/test_api.py::test_create_user": 0.5,
            "tests/test_api.py::test_delete_user": 0.4,
            "tests/test_auth.py::test_login": 0.2,
            "tests/test_auth.py::test_unauthorized": 0.3,
            "tests/test_ui.py::test_screenshot": 1.2,
            "tests/test_ui.py::test_form_submit": 0.8,
            "tests/test_ui.py::test_dashboard": 0.0,
            "tests/test_orders.py::test_create_order[item=laptop-qty=1]": 0.6,
            "tests/test_orders.py::test_create_order[item=phone-qty=2]": 0.5,
            "tests/test_orders.py::test_cancel_order": 0.4,
        },
        statuses={
            "tests/test_api.py::test_get_users": "passed",
            "tests/test_api.py::test_create_user": "passed",
            "tests/test_api.py::test_delete_user": "failed",  # always fails
            "tests/test_auth.py::test_login": "passed",
            "tests/test_auth.py::test_unauthorized": "failed",  # flaky: run1=fail
            "tests/test_ui.py::test_screenshot": "passed",
            "tests/test_ui.py::test_form_submit": "passed",
            "tests/test_ui.py::test_dashboard": "skipped",
            "tests/test_orders.py::test_create_order[item=laptop-qty=1]": "passed",
            "tests/test_orders.py::test_create_order[item=phone-qty=2]": "passed",
            "tests/test_orders.py::test_cancel_order": "broken",
        },
    )
    store.save_run(run1)
    s = run1.stats
    print(f"Run 1: {s.passed}p/{s.failed}f/{s.skipped}s/{s.broken}b")

    # Run 2: test_unauthorized passes (flaky!), test_screenshot slows down
    run2 = _build_run(
        run_id="demo-002",
        timestamp=base_time + timedelta(hours=2),
        durations={
            "tests/test_api.py::test_get_users": 0.3,
            "tests/test_api.py::test_create_user": 0.6,   # +0.1s
            "tests/test_api.py::test_delete_user": 0.4,
            "tests/test_auth.py::test_login": 0.2,
            "tests/test_auth.py::test_unauthorized": 0.3,
            "tests/test_ui.py::test_screenshot": 1.8,     # +0.6s (slowing down)
            "tests/test_ui.py::test_form_submit": 0.8,
            "tests/test_ui.py::test_dashboard": 0.0,
            "tests/test_orders.py::test_create_order[item=laptop-qty=1]": 0.6,
            "tests/test_orders.py::test_create_order[item=phone-qty=2]": 0.5,
            "tests/test_orders.py::test_cancel_order": 0.4,
        },
        statuses={
            "tests/test_api.py::test_get_users": "passed",
            "tests/test_api.py::test_create_user": "passed",
            "tests/test_api.py::test_delete_user": "failed",
            "tests/test_auth.py::test_login": "passed",
            "tests/test_auth.py::test_unauthorized": "passed",  # flaky: run2=pass
            "tests/test_ui.py::test_screenshot": "passed",
            "tests/test_ui.py::test_form_submit": "passed",
            "tests/test_ui.py::test_dashboard": "skipped",
            "tests/test_orders.py::test_create_order[item=laptop-qty=1]": "passed",
            "tests/test_orders.py::test_create_order[item=phone-qty=2]": "passed",
            "tests/test_orders.py::test_cancel_order": "failed",  # new failure
        },
    )
    store.save_run(run2)
    s = run2.stats
    print(f"Run 2: {s.passed}p/{s.failed}f/{s.skipped}s/{s.broken}b")

    # Run 3: test_unauthorized fails again (flaky confirmed!), screenshot even slower
    run3 = _build_run(
        run_id="demo-003",
        timestamp=base_time + timedelta(hours=4),
        durations={
            "tests/test_api.py::test_get_users": 0.3,
            "tests/test_api.py::test_create_user": 0.7,   # +0.2s from run1
            "tests/test_api.py::test_delete_user": 0.4,
            "tests/test_auth.py::test_login": 0.2,
            "tests/test_auth.py::test_unauthorized": 0.3,
            "tests/test_ui.py::test_screenshot": 2.5,     # +1.3s from run1 (much slower)
            "tests/test_ui.py::test_form_submit": 0.8,
            "tests/test_ui.py::test_dashboard": 0.0,
            "tests/test_orders.py::test_create_order[item=laptop-qty=1]": 0.6,
            "tests/test_orders.py::test_create_order[item=phone-qty=2]": 0.5,
            "tests/test_orders.py::test_cancel_order": 0.4,
        },
        statuses={
            "tests/test_api.py::test_get_users": "passed",
            "tests/test_api.py::test_create_user": "passed",
            "tests/test_api.py::test_delete_user": "failed",
            "tests/test_auth.py::test_login": "passed",
            "tests/test_auth.py::test_unauthorized": "failed",  # flaky: run3=fail
            "tests/test_ui.py::test_screenshot": "passed",
            "tests/test_ui.py::test_form_submit": "passed",
            "tests/test_ui.py::test_dashboard": "skipped",
            "tests/test_orders.py::test_create_order[item=laptop-qty=1]": "passed",
            "tests/test_orders.py::test_create_order[item=phone-qty=2]": "passed",
            "tests/test_orders.py::test_cancel_order": "failed",
        },
    )
    store.save_run(run3)
    s = run3.stats
    print(f"Run 3: {s.passed}p/{s.failed}f/{s.skipped}s/{s.broken}b")

    # ── Analyze history ──────────────────────────────────────────────────
    flaky_tests = detect_flaky(store)
    trends = analyze_duration(store)
    slowest = get_slowest_tests(run3, 5)

    print(f"\nFlaky tests: {len(flaky_tests)}")
    for ft in flaky_tests:
        print(f"  {ft.name}: score={ft.flaky_score}, changes={ft.status_changes}/{ft.total_runs}")

    print(f"\nDuration trends: {len(trends)} tests tracked")
    for t in trends[:3]:
        change = f" ({t.change_pct:+.1f}%)" if t.change_pct else ""
        print(f"  {t.name}: {t.latest_duration:.2f}s avg={t.avg_duration:.2f}s{change}")

    # ── Generate reports ──────────────────────────────────────────────────
    # 1. Create demo attachment files
    att_dir = _create_demo_attachments(out)

    # 2. Attach real files to specific tests in the latest run
    _add_attachments(run3, att_dir, ["screenshot", "form_submit"])

    # 3. Main report (latest run) with embedded attachments
    index = renderer.render(run3, out, embed_attachments=True, source_dir=out)
    print(f"\nMain report: {index}")

    # 4. History report
    runs_meta = store.list_runs()
    history_index = renderer.render_history(
        flaky_tests=flaky_tests,
        trends=trends,
        output_dir=out,
        run_meta_list=runs_meta,
        slowest_tests=slowest,
    )
    print(f"History report: {history_index}")

    print(f"\n  Total tests (latest): {run3.stats.total}")
    print(f"  Passed: {run3.stats.passed} | Failed: {run3.stats.failed} | "
          f"Broken: {run3.stats.broken} | Skipped: {run3.stats.skipped}")
    print(f"  Pass rate: {run3.stats.pass_rate}%")
    print(f"  Suites: {len(run3.suites)}")
    print(f"  History: {len(runs_meta)} run(s)")
    print(f"  Open: file://{index.resolve()}")
    print(f"  History: file://{history_index.resolve()}")


if __name__ == "__main__":
    main()
