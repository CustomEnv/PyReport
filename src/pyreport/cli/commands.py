"""CLI commands for PyReport."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import typer

from pyreport.analyzers.flaky import detect_flaky
from pyreport.analyzers.trends import analyze_duration, get_slowest_tests
from pyreport.core import TestRun
from pyreport.history.store import HistoryStore
from pyreport.renderers.static.html_renderer import HTMLRenderer

app = typer.Typer(
    name="pyreport",
    help="Beautiful test report generator",
    no_args_is_help=True,
)


def _model_from_dict(data: dict) -> TestRun:
    """Reconstruct a TestRun from a dict (deserialized JSON)."""
    from pyreport.core import Attachment, RunStats, Status, TestCase, TestSuite

    suites_data = data.get("suites", [])
    suites = []
    for sd in suites_data:
        tests = []
        for td in sd.get("tests", []):
            atts = []
            for ad in td.get("attachments", []):
                atts.append(Attachment(
                    name=ad.get("name", ""),
                    path=ad.get("path", ""),
                    mime_type=ad.get("mime_type", ""),
                    size=ad.get("size", 0),
                ))
            tests.append(TestCase(
                id=td.get("id", ""),
                name=td.get("name", ""),
                full_name=td.get("full_name", ""),
                duration=td.get("duration", 0.0),
                status=Status(td.get("status", "passed")),
                message=td.get("message"),
                traceback=td.get("traceback"),
                parameters=td.get("parameters", {}),
                tags=td.get("tags", []),
                attachments=atts,
                test_id=td.get("test_id", ""),
                stdout=td.get("stdout"),
                stderr=td.get("stderr"),
                log=td.get("log"),
            ))
        suites.append(TestSuite(
            id=sd.get("id", ""),
            name=sd.get("name", ""),
            duration=sd.get("duration", 0.0),
            status=Status(sd.get("status", "passed")),
            tests=tests,
        ))

    stats_data = data.get("stats", {})
    # Strip extra fields (like pass_rate) that aren't part of RunStats
    stats_kwargs = {k: v for k, v in stats_data.items()
                    if k in ("total", "passed", "failed", "broken", "skipped")}
    run = TestRun(
        id=data.get("id", ""),
        project=data.get("project", ""),
        name=data.get("name", ""),
        duration=data.get("duration", 0.0),
        status=Status(data.get("status", "passed")),
        stats=RunStats(**stats_kwargs),
        suites=suites,
        environment=data.get("environment", {}),
    )
    return run


@app.command()
def generate(
    input_path: str = typer.Argument(
        ...,
        help="Path to report.json",
    ),
    output_dir: str = typer.Option(
        "pyreport-html",
        "--output", "-o",
        help="Output directory for HTML report",
    ),
    embed_attachments: bool = typer.Option(
        False,
        "--embed-attachments",
        help="Embed small attachments (<100KB) as base64 data URIs",
    ),
) -> None:
    """Generate an HTML report from a JSON report file."""
    src = Path(input_path)
    if not src.exists():
        typer.echo(f"Error: file not found: {src}", err=True)
        raise typer.Exit(code=1)

    data = json.loads(src.read_text(encoding="utf-8"))
    run = _model_from_dict(data)
    out = Path(output_dir)
    renderer = HTMLRenderer()
    index = renderer.render(run, out, embed_attachments=embed_attachments,
                            source_dir=src.parent)
    typer.echo(f"Report generated: {index}")


@app.command()
def merge(
    input_paths: list[str] = typer.Argument(
        ...,
        help="Paths to report.json files to merge",
    ),
    output_dir: str = typer.Option(
        "pyreport-merged",
        "--output", "-o",
        help="Output directory for merged HTML report",
    ),
) -> None:
    """Merge multiple reports into a single HTML summary."""
    from datetime import datetime


    runs: list[TestRun] = []
    for path_str in input_paths:
        src = Path(path_str)
        if not src.exists():
            typer.echo(f"Error: file not found: {src}", err=True)
            raise typer.Exit(code=1)
        data = json.loads(src.read_text(encoding="utf-8"))
        runs.append(_model_from_dict(data))

    if not runs:
        typer.echo("Error: no reports to merge", err=True)
        raise typer.Exit(code=1)

    # Combine all suites into one meta-run
    all_suites = []
    total_duration = 0.0
    for r in runs:
        all_suites.extend(r.suites)
        total_duration += r.duration

    merged = TestRun(
        id=f"merged-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        project=runs[0].project,
        name=f"Merged ({len(runs)} runs, {datetime.now().isoformat()})",
        duration=round(total_duration, 3),
        suites=all_suites,
    )
    merged.compute_stats()

    out = Path(output_dir)
    renderer = HTMLRenderer()
    index = renderer.render(merged, out)
    typer.echo(f"Merged report ({merged.stats.total} tests, {len(runs)} runs): {index}")


@app.command()
def serve(
    directory: str = typer.Argument(
        "pyreport-html",
        help="Directory containing the report",
    ),
    port: int = typer.Option(
        8080,
        "--port", "-p",
        help="Port to serve on",
    ),
) -> None:
    """Serve a generated report via HTTP."""
    import webbrowser
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    path = Path(directory).resolve()
    if not path.exists():
        typer.echo(f"Error: directory not found: {path}", err=True)
        raise typer.Exit(code=1)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(path), **kwargs)  # type: ignore[arg-type]

    server = HTTPServer(("0.0.0.0", port), Handler)
    url = f"http://localhost:{port}"
    typer.echo(f"Serving report at {url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


# ── deploy ─────────────────────────────────────────────────────────────────


def _discover_runs(
    reports_dir: Path,
) -> list[tuple[str, str, bool, bool, int | None, str | None, str | None]]:
    """Return sorted (run_id, ts, has_demo, has_tests, pr, repo, run) list."""
    if not reports_dir.is_dir():
        return []
    runs: list[tuple[str, str, bool, bool, int | None, str | None, str | None]] = []
    for child in sorted(reports_dir.iterdir()):
        if not child.is_dir():
            continue
        demo = (child / "demo" / "index.html").is_file()
        tests = (child / "test-report" / "index.html").is_file()
        if not (demo or tests):
            continue

        meta_file = child / ".meta.json"
        pr: int | None = None
        repo: str | None = None
        run: str | None = None
        ts: str | None = None
        if meta_file.is_file():
            try:
                meta = json.loads(meta_file.read_text())
                pr = meta.get("pr")
                repo = meta.get("repo")
                run = str(meta["run"]) if "run" in meta else None
                raw_ts = meta.get("ts")
                if raw_ts:
                    ts = raw_ts
            except Exception:
                pass

        if not ts:
            ts = datetime.fromtimestamp(
                child.stat().st_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M UTC")

        runs.append((child.name, ts, demo, tests, pr, repo, run))
    runs.sort(key=lambda r: r[1], reverse=True)
    return runs


def _generate_index(
    runs: list[tuple[str, str, bool, bool, int | None, str | None, str | None]],
) -> str:
    rows: list[str] = []
    for run_id, ts, has_demo, has_tests, pr, repo, run in runs:
        link = "class='text-blue-400 hover:text-blue-300'"

        run_cell: str
        if run and repo:
            run_cell = (
                f"<a href='https://github.com/{repo}/actions/runs/{run}' {link}>"
                f"{run}</a>"
            )
        elif run:
            run_cell = run
        else:
            run_cell = run_id

        pr_cell: str
        if pr and repo:
            pr_cell = f"<a href='https://github.com/{repo}/pull/{pr}' {link}>#{pr}</a>"
        elif pr:
            pr_cell = f"#{pr}"
        else:
            pr_cell = "<span class='text-gray-500'>\u2014</span>"

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
            f"<td class='py-2 px-3 font-mono text-sm'>{run_cell}</td>"
            f"<td class='py-2 px-3 text-sm text-gray-400'>{ts}</td>"
            f"<td class='py-2 px-3'>{pr_cell}</td>"
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
          <th class="py-3 px-3">PR</th>
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
</html>"""


@app.command()
def deploy(
    site: str = typer.Argument(
        ...,
        help="_site directory with new reports",
    ),
    gh_pages: str = typer.Argument(
        ...,
        help="gh-pages branch checkout directory",
    ),
) -> None:
    """Merge existing reports from gh-pages checkout into site and generate index."""
    site_path = Path(site)
    gh_path = Path(gh_pages)

    if gh_path.is_dir():
        for item in gh_path.iterdir():
            if item.name == ".git":
                continue
            dst = site_path / item.name
            if item.name == "reports":
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

    all_runs = _discover_runs(site_path / "reports")
    site_path.joinpath("index.html").write_text(_generate_index(all_runs))

    # ── Persist .pyreport_history ──────────────────────────────────────────
    history_dir = site_path / ".pyreport_history"
    reports_root = site_path / "reports"
    if reports_root.is_dir():
        for run_dir in sorted(reports_root.iterdir()):
            if not run_dir.is_dir():
                continue
            # history may be nested inside test-report/ or demo/ subdirs
            for hist_path in run_dir.rglob(".pyreport_history"):
                if not hist_path.is_dir():
                    continue
                for item in hist_path.iterdir():
                    if item.is_file() and item.suffix == ".json":
                        dst = history_dir / item.name
                        history_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dst)

    # Rebuild index.json from merged history
    if history_dir.is_dir():
        # Re-merge all run files into a clean index
        runs_in_history = sorted(
            history_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        index_path = history_dir / "index.json"
        entries = []
        for p in runs_in_history:
            if p.name == "index.json":
                continue
            try:
                data = json.loads(p.read_text())
                stats = data.get("stats", {})
                entries.append({
                    "id": data.get("id", p.stem),
                    "timestamp": data.get("timestamp", ""),
                    "total": stats.get("total", 0),
                    "passed": stats.get("passed", 0),
                    "failed": stats.get("failed", 0),
                    "broken": stats.get("broken", 0),
                    "skipped": stats.get("skipped", 0),
                    "pass_rate": stats.get("pass_rate", 0.0),
                    "duration": data.get("duration", 0.0),
                })
            except Exception:
                pass
        entries.sort(key=lambda r: r["timestamp"], reverse=True)
        index_path.write_text(json.dumps(entries, indent=2))
        typer.echo(f"History: {len(entries)} run(s) in {history_dir}")

    ids = [r[0] for r in all_runs]
    typer.echo(
        f"Deploying {len(all_runs)} run(s): {(', '.join(ids) if ids else '(first run)')}"
    )


@app.command()
def history(
    reports_dir: str = typer.Argument(
        ...,
        help="Directory containing a PyReport output with history",
    ),
    output_dir: str = typer.Option(
        "pyreport-history",
        "--output", "-o",
        help="Output directory for history HTML report",
    ),
) -> None:
    """Show history of test runs with flaky detection and duration trends."""
    reports_path = Path(reports_dir)
    if not reports_path.is_dir():
        typer.echo(f"Error: directory not found: {reports_path}", err=True)
        raise typer.Exit(code=1)

    # Discover the history directory — look for .pyreport_history/ subdir or reports_dir itself
    history_path = reports_path / ".pyreport_history"
    if not history_path.is_dir():
        typer.echo(
            f"Warning: no history found in {reports_path}. "
            "Generating empty history page.",
            err=True,
        )
        renderer = HTMLRenderer()
        out = Path(output_dir)
        history_index = renderer.render_history(output_dir=out)
        typer.echo(f"History report generated (empty): {history_index}")
        raise typer.Exit()

    store = HistoryStore(history_path)
    runs = store.list_runs()
    if not runs:
        typer.echo("Warning: no runs found in history. Generating empty history page.", err=True)
        renderer = HTMLRenderer()
        out = Path(output_dir)
        history_index = renderer.render_history(output_dir=out)
        typer.echo(f"History report generated (empty): {history_index}")
        raise typer.Exit()

    typer.echo(f"Found {len(runs)} run(s) in history.")

    # Flaky detection
    flaky_tests = detect_flaky(store)
    if flaky_tests:
        typer.echo(f"\nFlaky tests ({len(flaky_tests)} found):")
        for ft in flaky_tests[:5]:
            typer.echo(f"  {ft.name} — score: {ft.flaky_score}, "
                       f"changes: {ft.status_changes}/{ft.total_runs}")

    # Duration trends
    trends = analyze_duration(store)
    if trends:
        typer.echo(f"\nDuration trends ({len(trends)} tests tracked):")
        for t in trends[:5]:
            change = f" ({t.change_pct:+.1f}%)" if t.change_pct is not None else ""
            typer.echo(f"  {t.name} — latest: {t.latest_duration:.2f}s, "
                       f"avg: {t.avg_duration:.2f}s{change}")

    # Slowest tests in the latest run
    latest_run = store.load_run(runs[0]["id"])
    if latest_run:
        slowest = get_slowest_tests(latest_run, 5)
        typer.echo(f"\nSlowest tests in latest run ({runs[0]['id']}):")
        for t in slowest:
            typer.echo(f"  {t.name} — {t.duration:.2f}s [{t.status.value}]")

    # Generate history HTML
    out = Path(output_dir)
    renderer = HTMLRenderer()
    slowest = get_slowest_tests(latest_run, 5) if latest_run else []
    history_index = renderer.render_history(
        flaky_tests=flaky_tests,
        trends=trends,
        output_dir=out,
        run_meta_list=runs,
        slowest_tests=slowest,
    )
    typer.echo(f"\nHistory report generated: {history_index}")


if __name__ == "__main__":
    app()
