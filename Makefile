.PHONY: test demo lint clean

OUTPUT_DIR = .venv/output
PYTHON = .venv/bin/python

test:
	$(PYTHON) -m pytest tests/

demo:
	$(PYTHON) scripts/generate_demo.py --output $(OUTPUT_DIR)/demo
	$(PYTHON) -m pyreport serve $(OUTPUT_DIR)/demo

lint:
	$(PYTHON) -m ruff check src/pyreport/ tests/ scripts/

clean:
	rm -rf $(OUTPUT_DIR)
	rm -rf pyreport-html pyreport-merged
	rm -rf .pytest_cache __pycache__
	rm -rf tests/__pycache__ src/**/__pycache__
