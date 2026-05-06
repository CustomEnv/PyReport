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
        ts = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        link = "class='text-blue-400 hover:text-blue-300'"
        if has_demo:
            demo = f"<a href='reports/{run_id}/demo/' {link}>demo</a>"
        else:
            demo = "<span class='text-gray-600'>\u2014</span>"
        if has_tests:
            tests = f"<a href='reports/{run_id}/test-report/' {link}>tests</a>"
        else:
            tests = "<span class='text-gray-600'>\u2014</span>"

        rows.append(
            f"<tr class='border-b border-gray-700 hover:bg-gray-750'>"
            f"<td class='py-2 px-3 font-mono text-sm'>{run_id}</td>"
            f"<td class='py-2 px-3 text-sm text-gray-400'>{ts}</td>"
            f"<td class='py-2 px-3'>{demo}</td>"
            f"<td class='py-2 px-3'>{tests}</td>"
            f"</tr>"
        )

    return """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PyReport \u2014 test runs</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.bg-gray-750{background-color:#2d2d3a}
</style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen">
<div class="max-w-4xl mx-auto p-6">
  <div class="bg-gray-800 rounded-lg p-5 mb-6 border border-gray-700">
    <h1 class="text-xl font-bold">PyReport</h1>
    <p class="text-sm text-gray-400 mt-1">test run history</p>
  </div>
  <div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <table class="w-full">
      <thead>
        <tr class="text-left text-xs text-gray-400 uppercase tracking-wider
                 border-b border-gray-700">
          <th class="py-3 px-3">Run</th>
          <th class="py-3 px-3">Date</th>
          <th class="py-3 px-3">Demo</th>
          <th class="py-3 px-3">Tests</th>
        </tr>
      </thead>
      <tbody>
""" + "\n".join(rows) + """      </tbody>
    </table>
  </div>
</div>
</body>
</html>
"""


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
            if item.name == ".git":
                continue
            dst = site / item.name
            if item.name == "reports":
                # Merge individual runs inside reports/, not the whole dir
                dst.mkdir(parents=True, exist_ok=True)
                for run_dir in item.iterdir():
                    run_dst = dst / run_dir.name
                    if not run_dst.exists():
                        shutil.copytree(run_dir, run_dst)
            elif not dst.exists():
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
