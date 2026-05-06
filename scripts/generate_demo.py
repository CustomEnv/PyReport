#!/usr/bin/env python3
"""Generate a rich demo report showcasing all PyReport features.

Usage:
    python scripts/generate_demo.py [--output /tmp/pyreport-demo]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pyreport.core import Status, TestCase, TestRun, TestSuite
from pyreport.renderers.static.html_renderer import HTMLRenderer


def _build_run() -> TestRun:
    return TestRun(
        id="demo-001",
        project="PyReport Demo",
        name="Rich Diagnostics Demo",
        timestamp="2026-05-05T20:00:00",
        environment={
            "CI": "true",
            "GITHUB_ACTIONS": "true",
            "GITHUB_SHA": "abc123def456",
            "GITHUB_REF_NAME": "main",
            "GITHUB_RUN_ID": "1234567890",
            "GITHUB_REPOSITORY": "user/pyreport",
            "GITHUB_SERVER_URL": "https://github.com",
            "OS": "macOS",
            "PYTHON_VERSION": "3.11",
            "TZ": "UTC",
        },
        suites=[
            TestSuite(
                id="s1", name="tests/test_api.py", duration=1.2, status=Status.PASSED,
                tests=[
                    TestCase(
                        id="c1", name="test_get_users",
                        full_name="tests/test_api.py::test_get_users",
                        duration=0.3, status=Status.PASSED,
                        stdout='GET /api/users -> 200\nResponse: [{"id": 1, "name": "Alice"}]',
                        tags=["smoke"],
                    ),
                    TestCase(
                        id="c2", name="test_create_user",
                        full_name="tests/test_api.py::test_create_user",
                        duration=0.5, status=Status.PASSED,
                        stdout="POST /api/users -> 201\nCreated user #42",
                        stderr="[WARN] Rate limit: 100/1000 requests used",
                        tags=["smoke"],
                    ),
                    TestCase(
                        id="c3", name="test_delete_user",
                        full_name="tests/test_api.py::test_delete_user",
                        duration=0.4, status=Status.FAILED,
                        message="AssertionError: Expected 204, got 403",
                        traceback=(
                            '  File "tests/test_api.py", line 25, in test_delete_user\n'
                            "    assert response.status == 204, "
                            '"Expected 204, got {response.status}"\n'
                            "AssertionError: Expected 204, got 403\n"
                        ),
                        stdout="DELETE /api/users/42 -> 403",
                        tags=["security"],
                    ),
                ],
            ),
            TestSuite(
                id="s2", name="tests/test_auth.py", duration=0.8, status=Status.FAILED,
                tests=[
                    TestCase(
                        id="c4", name="test_login",
                        full_name="tests/test_auth.py::test_login",
                        duration=0.2, status=Status.PASSED,
                    ),
                    TestCase(
                        id="c5", name="test_unauthorized",
                        full_name="tests/test_auth.py::test_unauthorized",
                        duration=0.3, status=Status.FAILED,
                        message="AssertionError: Expected 401, got 200",
                        traceback=(
                            '  File "tests/test_auth.py", line 15, in test_unauthorized\n'
                            "    assert response.status == 401, "
                            '"Expected 401, got {response.status}"\n'
                            "AssertionError: Expected 401, got 200\n"
                        ),
                    ),
                    TestCase(
                        id="c6", name="test_expired_token",
                        full_name="tests/test_auth.py::test_expired_token",
                        duration=0.3, status=Status.FAILED,
                        message="AssertionError: Expected 401, got 200",
                        traceback=(
                            '  File "tests/test_auth.py", line 25, in test_expired_token\n'
                            "    assert response.status == 401, "
                            '"Expected 401, got {response.status}"\n'
                            "AssertionError: Expected 401, got 200\n"
                        ),
                    ),
                ],
            ),
            TestSuite(
                id="s3", name="tests/test_ui.py", duration=2.5, status=Status.PASSED,
                tests=[
                    TestCase(
                        id="c7", name="test_screenshot",
                        full_name="tests/test_ui.py::test_screenshot",
                        duration=1.2, status=Status.PASSED,
                        stdout="Screenshot saved: /tmp/screen.png",
                        log=(
                            "2026-05-05 20:00:01 [INFO] Page loaded\n"
                            "2026-05-05 20:00:02 [INFO] Element found\n"
                            "2026-05-05 20:00:02 [DEBUG] Screenshot captured"
                        ),
                        tags=["visual", "slow"],
                        attachments=[
                            {
                                "name": "screenshot.png",
                                "path": "https://placehold.co/400x300/1a1a2e/22c55e?text=Screenshot",
                                "mime_type": "image/png",
                                "size": 128000,
                            },
                            {
                                "name": "page_source.html",
                                "path": "https://placehold.co/200x100/1a1a2e/3b82f6?text=HTML",
                                "mime_type": "text/html",
                                "size": 45000,
                            },
                        ],
                    ),
                    TestCase(
                        id="c8", name="test_form_submit",
                        full_name="tests/test_ui.py::test_form_submit",
                        duration=0.8, status=Status.PASSED,
                        stdout="Form submitted successfully\nRedirecting to /dashboard",
                        stderr="[WARN] Deprecated: submit() will be removed in v3",
                    ),
                    TestCase(
                        id="c9", name="test_dashboard",
                        full_name="tests/test_ui.py::test_dashboard",
                        duration=0.0, status=Status.SKIPPED,
                        message="Skipped: feature flag FEATURE_X disabled",
                    ),
                ],
            ),
            TestSuite(
                id="s4", name="tests/test_orders.py", duration=1.5, status=Status.PASSED,
                tests=[
                    TestCase(
                        id="c10", name="test_create_order",
                        full_name="tests/test_orders.py::test_create_order",
                        duration=0.6, status=Status.PASSED,
                        parameters={"item": "laptop", "qty": "1"},
                        stdout="Order #9876 created",
                        tags=["smoke", "critical-path"],
                    ),
                    TestCase(
                        id="c11", name="test_create_order",
                        full_name="tests/test_orders.py::test_create_order[item=phone-qty=2]",
                        duration=0.5, status=Status.PASSED,
                        parameters={"item": "phone", "qty": "2"},
                        stdout="Order #9877 created",
                        tags=["smoke"],
                    ),
                    TestCase(
                        id="c12", name="test_cancel_order",
                        full_name="tests/test_orders.py::test_cancel_order",
                        duration=0.4, status=Status.BROKEN,
                        message="ConnectionError: Database timeout",
                        traceback=(
                            '  File "tests/test_orders.py", line 42, in test_cancel_order\n'
                            "    db.execute('CANCEL ORDER 9876')\n"
                            '  File "db/client.py", line 88, in execute\n'
                            "    raise ConnectionError('Database timeout')\n"
                            "ConnectionError: Database timeout\n"
                        ),
                        stdout="Attempting to cancel order #9876",
                        stderr="[ERROR] Connection pool exhausted",
                    ),
                ],
            ),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PyReport demo report")
    parser.add_argument(
        "--output", "-o",
        default="pyreport-demo",
        help="Output directory (default: pyreport-demo)",
    )
    args = parser.parse_args()

    run = _build_run()
    run.compute_stats()

    out = Path(args.output)
    renderer = HTMLRenderer()
    index = renderer.render(run, out)

    print(f"Demo report generated: {index}")
    print(f"  Tests: {run.stats.total} | "
          f"Passed: {run.stats.passed} | "
          f"Failed: {run.stats.failed} | "
          f"Broken: {run.stats.broken} | "
          f"Skipped: {run.stats.skipped}")
    print(f"  Pass rate: {run.stats.pass_rate}%")
    print(f"  Suites: {len(run.suites)}")
    print(f"  Open: file://{index.resolve()}")


if __name__ == "__main__":
    main()
