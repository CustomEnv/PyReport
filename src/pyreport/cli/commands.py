"""CLI commands for PyReport."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from pyreport.core import TestRun
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
    index = renderer.render(run, out)
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


if __name__ == "__main__":
    app()
