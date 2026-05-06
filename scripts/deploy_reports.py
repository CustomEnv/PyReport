"""Merge new reports into gh-pages checkout and generate root index.html."""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _discover_runs(reports_dir: Path) -> list[tuple[str, float, bool, bool]]:
    """Return sorted (run_id, mtime, has_demo, has_tests) list, newest first."""
    if not reports_dir.is_dir():
        return []
    runs = []
    for child in sorted(reports_dir.iterdir()):
        if not child.is_dir():
            continue
        demo = (child / "demo" / "index.html").is_file()
        tests = (child / "test-report" / "index.html").is_file()
        if demo or tests:
            runs.append((child.name, child.stat().st_mtime, demo, tests))
    runs.sort(key=lambda r: r[1], reverse=True)
    return runs


def _generate_index(runs: list[tuple[str, float, bool, bool]]) -> str:
    rows = []
    for run_id, mtime, has_demo, has_tests in runs:
        ts = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        demo = f"<a href='reports/{run_id}/demo/'>demo</a>" if has_demo else "—"
        tests = f"<a href='reports/{run_id}/test-report/'>tests</a>" if has_tests else "—"
        rows.append(f"<tr><td>{run_id}</td><td>{ts}</td><td>{demo}</td><td>{tests}</td></tr>")

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PyReport — test runs</title>
<style>
body{font-family:system-ui,sans-serif;max-width:800px;margin:40px auto;padding:0 20px}
body{background:#0f172a;color:#e2e8f0}
a{color:#60a5fa}
table{width:100%;border-collapse:collapse;margin-top:20px}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid #334155}
th{color:#94a3b8;font-size:.85em;text-transform:uppercase;letter-spacing:.05em}
td{font-family:monospace;font-size:.9em}
h1{font-size:1.5em;margin-bottom:0}
</style>
</head>
<body>
<h1>PyReport — test runs</h1>
<table>
<tr><th>Run</th><th>Date</th><th>Demo</th><th>Tests</th></tr>
""" + "\n".join(rows) + "\n</table>\n</body>\n</html>\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge reports and generate index")
    parser.add_argument("--site", required=True, help="_site directory with new reports")
    parser.add_argument("--gh-pages", required=True, help="gh-pages branch checkout")
    args = parser.parse_args()

    site = Path(args.site)
    gh_pages = Path(args.gh_pages)

    # Merge existing reports from gh-pages into site
    if gh_pages.is_dir():
        for item in gh_pages.iterdir():
            if item.name in (".git",):
                continue
            dst = site / item.name
            if not dst.exists():
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)

    # Discover all runs and generate index
    all_runs = _discover_runs(site / "reports")
    site.joinpath("index.html").write_text(_generate_index(all_runs))

    ids = [r[0] for r in all_runs]
    print(f"Deploying {len(all_runs)} run(s): {', '.join(ids) if ids else '(first run)'}")


if __name__ == "__main__":
    main()
