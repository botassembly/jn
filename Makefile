.PHONY: all check test coverage clean install

all: check test

# Run all checks (format, lint, type check)
check:
	@uv sync --extra dev
	@uv run black src/jn tests
	@uv run ruff check --select I --fix src/jn tests
	@uv run ruff check --fix src/jn tests
	@uv run ruff check src/jn tests
	@uv run lint-imports --config importlinter.ini || true

test:
	uv run pytest -q

coverage:
	uv run coverage erase
	uv run pytest --cov-report=term-missing
	uv run coverage html
	uv run coverage xml
	uv run coverage report --fail-under=70

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf src/*.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

install:
	uv sync --all-extras
