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

Commits reports to the `gh-pages` branch. Each new PR adds a row to the root index page listing all runs. Old reports are never removed.

> Setup: Settings → Pages → Source → **"Deploy from a branch"** → Branch: `gh-pages` / `/(root)`

```yaml
- run: |
    pytest --pyreport --pyreport-output "_site/reports/${{ github.run_id }}/test-report"
    python scripts/generate_demo.py --output "_site/reports/${{ github.run_id }}/demo"
- run: pyreport deploy _site _gh-pages
- uses: peaceiris/actions-gh-pages@v4
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./_site
    publish_branch: gh-pages
```

After deploy:

```
https://<user>.github.io/<repo/>                         ← all runs index
https://<user>.github.io/<repo>/reports/<run-id>/demo/
https://<user>.github.io/<repo>/reports/<run-id>/test-report/
```

## Demo

```bash
python scripts/generate_demo.py --output demo
# or: make demo
```

## Requirements

Python 3.11+, pytest 8.0+

## License

MIT
