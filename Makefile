.PHONY: all check test coverage clean install install-zig zq zq-test zq-bench zig-plugins zig-plugins-test zig-libs zig-libs-test zig-libs-fmt

# Zig configuration
ZIG_VERSION := 0.15.2
ZIG_ARCHIVE := zig-x86_64-linux-$(ZIG_VERSION).tar.xz
ZIG_URL := https://ziglang.org/download/$(ZIG_VERSION)/$(ZIG_ARCHIVE)
ZIG_LOCAL := $(HOME)/.local/zig-x86_64-linux-$(ZIG_VERSION)
SYSTEM_ZIG := $(shell command -v zig 2>/dev/null)
SYSTEM_ZIG_VERSION := $(shell if [ -n "$(SYSTEM_ZIG)" ]; then $(SYSTEM_ZIG) version 2>/dev/null; fi)
ZIG := $(ZIG_LOCAL)/zig
ifeq ($(SYSTEM_ZIG_VERSION),$(ZIG_VERSION))
ZIG := $(SYSTEM_ZIG)
endif
PLUGIN_MODULES := --dep jn-core --dep jn-cli --dep jn-plugin \
	-Mroot=main.zig \
	-Mjn-core=../../../libs/zig/jn-core/src/root.zig \
	-Mjn-cli=../../../libs/zig/jn-cli/src/root.zig \
	-Mjn-plugin=../../../libs/zig/jn-plugin/src/root.zig

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
	# Zig formatting check (if Zig is installed)
	@if command -v $(ZIG) >/dev/null 2>&1; then \
		echo "Checking Zig formatting..."; \
		$(ZIG) fmt --check zq/src/ zq/tests/ || (echo "Run 'make zq-fmt' to fix"; exit 1); \
	fi

# Format Zig code
zq-fmt: install-zig
	$(ZIG) fmt zq/src/ zq/tests/

test: install-zig
	$(MAKE) zig-libs-test
	$(MAKE) zig-plugins-test
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
	@echo "Building Zig plugins..."
	$(MAKE) zig-plugins

# Install Zig compiler
install-zig:
	@if [ -x "$(ZIG)" ]; then \
		echo "Using Zig $(ZIG_VERSION) at $(ZIG)"; \
	else \
		echo "Downloading Zig $(ZIG_VERSION)..."; \
		mkdir -p $(HOME)/.local/bin; \
		curl -L $(ZIG_URL) -o /tmp/$(ZIG_ARCHIVE); \
		tar -xf /tmp/$(ZIG_ARCHIVE) -C $(HOME)/.local; \
		ln -sf $(ZIG) $(HOME)/.local/bin/zig; \
		rm -f /tmp/$(ZIG_ARCHIVE); \
		echo "Zig installed to $(ZIG_LOCAL)"; \
	fi
	@$(ZIG) version

# Build ZQ (Zig-based jq replacement)
# Use -fllvm to use the mature LLVM backend (x86 backend has TODO panics in 0.15.2)
# Use build-exe directly to avoid build system issues
zq: install-zig
	mkdir -p zq/zig-out/bin
	cd zq && $(ZIG) build-exe src/main.zig -fllvm -O ReleaseFast -femit-bin=zig-out/bin/zq

# Run ZQ tests (unit + integration)
zq-test: zq
	cd zq && $(ZIG) test src/main.zig -fllvm
	@echo "Unit tests passed. Running integration tests..."
	cd zq && $(ZIG) test tests/integration.zig -fllvm

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

# Build Zig plugins
zig-plugins: install-zig
	@echo "Building Zig plugins..."
	mkdir -p plugins/zig/csv/bin
	mkdir -p plugins/zig/json/bin
	mkdir -p plugins/zig/jsonl/bin
	mkdir -p plugins/zig/gz/bin
	cd plugins/zig/csv && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/csv
	cd plugins/zig/json && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/json
	cd plugins/zig/jsonl && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/jsonl
	cd plugins/zig/gz && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/gz
	@echo "Zig plugins built successfully"

# Run Zig plugin tests
zig-plugins-test: zig-plugins
	@echo "Testing Zig plugins..."
	cd plugins/zig/csv && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/json && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/jsonl && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/gz && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	@echo "All Zig plugin tests passed"

publish:
	@uv build
	@uvx twine upload -r pypi dist/*

# =============================================================================
# Zig Foundation Libraries (Phase 1)
# =============================================================================

# Test Zig libraries (unit tests only, no build artifacts needed)
zig-libs-test: install-zig
	@echo "Testing Zig foundation libraries..."
	cd libs/zig/jn-core && $(ZIG) test src/root.zig -fllvm
	@echo "  jn-core: OK"
	cd libs/zig/jn-cli && $(ZIG) test src/root.zig -fllvm
	@echo "  jn-cli: OK"
	cd libs/zig/jn-plugin && $(ZIG) test src/root.zig -fllvm
	@echo "  jn-plugin: OK"
	@echo "All Zig library tests passed"

# Build example plugin to validate libraries work together
zig-libs: install-zig
	@echo "Building minimal plugin example..."
	mkdir -p libs/zig/examples/bin
	cd libs/zig/examples && $(ZIG) build-exe minimal-plugin.zig -fllvm -O ReleaseFast -femit-bin=bin/minimal
	@echo "Testing minimal plugin..."
	libs/zig/examples/bin/minimal --jn-meta | python3 -c "import sys,json; json.load(sys.stdin); print('  --jn-meta: OK')"
	echo '{"test":1}' | libs/zig/examples/bin/minimal --mode=read | python3 -c "import sys,json; json.load(sys.stdin); print('  read mode: OK')"
	@echo "Minimal plugin built and validated"

# Format Zig library code
zig-libs-fmt: install-zig
	$(ZIG) fmt libs/zig/jn-core/src/
	$(ZIG) fmt libs/zig/jn-cli/src/
	$(ZIG) fmt libs/zig/jn-plugin/src/
	$(ZIG) fmt libs/zig/examples/
