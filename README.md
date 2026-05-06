# PyReport

pytest test report generator. Produces standalone HTML with charts, filters, error grouping, and CI info.

```bash
pip install -e .
pytest --pyreport
# → report.json + index.html
```

## Quick start

```bash
# From GitHub
pip install git+https://github.com/CustomEnv/PyReport.git

# Run tests with report
pytest --pyreport --pyreport-output reports/run-1
open reports/run-1/index.html

# Build report from existing JSON
pyreport generate reports/run-1/report.json -o reports/run-1-html

# Merge multiple reports
pyreport merge a.json b.json -o reports/merged

# Local preview
pyreport serve reports/run-1
```

## GitHub Pages deploy

```yaml
- run: pytest --pyreport --pyreport-output "reports/${{ github.run_id }}"
- uses: actions/upload-pages-artifact@v3
  with: { path: reports }
- uses: actions/deploy-pages@v4
```

Each run gets a unique URL: `https://<user>.github.io/<repo>/reports/<run-id>/` — no overwrites.

## Demo

```bash
python scripts/generate_demo.py --output demo
# or: make demo
```

## Requirements

Python 3.11+, pytest 8.0+

## License

MIT
