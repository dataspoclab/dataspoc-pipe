.PHONY: install test build clean

install:
	uv venv .venv
	. .venv/bin/activate && uv pip install -e ".[s3,dev]"

test:
	. .venv/bin/activate && pytest tests/ -v

build: test
	rm -rf dist/
	. .venv/bin/activate && uv build --wheel --out-dir dist/
	@echo ""
	@ls -lh dist/*.whl

clean:
	rm -rf dist/ build/
	find . -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
