.PHONY: all check test coverage clean install

all: check test

# Run all checks (format, lint, type check)
check:
	@uv sync --extra dev
	@uv run black src/jn tests
	@uv run ruff check --select I --fix src/jn tests
	@uv run ruff check --fix src/jn tests
	@uv run ruff check src/jn tests
	# Run mypy on a high-signal subset for now (expand over time)
	@uv run mypy src/jn/core/streaming.py src/jn/addressing/types.py src/jn/addressing/parser.py
	@uv run lint-imports --config importlinter.ini
	@echo "Validating plugins and core with 'jn check'"
	@uv run python -m jn.cli.main check plugins --format summary
	@uv run python -m jn.cli.main check core --format summary

test:
	uv run pytest -q

coverage:
	uv run coverage erase
	COVERAGE_PROCESS_START=$(PWD)/.coveragerc uv run coverage run -m pytest -q
	uv run coverage combine -q
	# Remove per-process coverage artifacts to reduce noise
	find . -maxdepth 1 -name ".coverage.*" -delete || true
	uv run coverage html -q
	uv run coverage xml -q
	uv run coverage json -q
	# Single, authoritative coverage report (core only per .coveragerc)
	uv run coverage report --fail-under=70

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf src/*.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf coverage-html/
	rm -rf coverage.xml
	rm -rf coverage.json
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

install:
	uv sync --all-extras

publish:
	@uv build
	@uvx twine upload -r pypi dist/*
