.PHONY: all check test coverage clean install install-zig zq zq-test zq-bench

# Zig configuration
ZIG_VERSION := 0.11.0
ZIG_ARCHIVE := zig-linux-x86_64-$(ZIG_VERSION).tar.xz
ZIG_URL := https://ziglang.org/download/$(ZIG_VERSION)/$(ZIG_ARCHIVE)
ZIG_LOCAL := $(HOME)/.local/zig-linux-x86_64-$(ZIG_VERSION)
ZIG := $(ZIG_LOCAL)/zig

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
	uv run coverage lcov -q
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

install: install-zig
	uv sync --all-extras
	@echo "Building ZQ..."
	$(MAKE) zq

# Install Zig compiler
install-zig:
	@if [ ! -f "$(ZIG)" ]; then \
		echo "Downloading Zig $(ZIG_VERSION)..."; \
		mkdir -p $(HOME)/.local/bin; \
		curl -L $(ZIG_URL) -o /tmp/$(ZIG_ARCHIVE); \
		tar -xf /tmp/$(ZIG_ARCHIVE) -C $(HOME)/.local; \
		ln -sf $(ZIG) $(HOME)/.local/bin/zig; \
		rm -f /tmp/$(ZIG_ARCHIVE); \
		echo "Zig installed to $(ZIG_LOCAL)"; \
	else \
		echo "Zig $(ZIG_VERSION) already installed"; \
	fi
	@$(ZIG) version

# Build ZQ (Zig-based jq replacement)
zq: install-zig
	cd zq && $(ZIG) build -Doptimize=ReleaseFast

# Run ZQ tests (unit + integration)
zq-test: zq
	cd zq && $(ZIG) build test
	cd zq && $(ZIG) build test-integration

# Run ZQ benchmarks (requires jq installed)
zq-bench: zq
	@echo "Running ZQ benchmarks..."
	@if command -v jq >/dev/null 2>&1; then \
		cd zq && ./benchmark.sh "." 100000; \
		cd zq && ./benchmark.sh ".field" 100000; \
		cd zq && ./benchmark.sh "select(.x > 50000)" 100000; \
	else \
		echo "jq not found - skipping comparative benchmarks"; \
	fi

publish:
	@uv build
	@uvx twine upload -r pypi dist/*
