.PHONY: all check test coverage clean install install-zig zq zq-test zq-bench zig-plugins zig-plugins-test zig-libs zig-libs-test zig-libs-fmt zig-tools zig-tools-test

# Zig configuration
ZIG_VERSION := 0.15.2
ZIG_ARCHIVE := zig-x86_64-linux-$(ZIG_VERSION).tar.xz
ZIG_URL := https://ziglang.org/download/$(ZIG_VERSION)/$(ZIG_ARCHIVE)
ZIG_LOCAL := $(HOME)/.local/zig-x86_64-linux-$(ZIG_VERSION)
SYSTEM_ZIG := $(shell command -v zig 2>/dev/null)
SYSTEM_ZIG_VERSION := $(shell if [ -n "$(SYSTEM_ZIG)" ]; then $(SYSTEM_ZIG) version 2>/dev/null; fi)
ZIG := $(ZIG_LOCAL)/zig
OPENDAL_C_DIR := $(abspath vendor/opendal/bindings/c)
OPENDAL_INCLUDE := $(OPENDAL_C_DIR)/include
OPENDAL_LIB_DIR := $(OPENDAL_C_DIR)/target/debug
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
	mkdir -p plugins/zig/yaml/bin
	mkdir -p plugins/zig/toml/bin
	cd plugins/zig/csv && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/csv
	cd plugins/zig/json && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/json
	cd plugins/zig/jsonl && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/jsonl
	cd plugins/zig/gz && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/gz
	cd plugins/zig/yaml && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/yaml
	cd plugins/zig/toml && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/toml
	@echo "Zig plugins built successfully"

# Build OpenDAL C library (optional; requires vendor/opendal)
opendal-c:
	@if [ -d "$(OPENDAL_C_DIR)" ]; then \
		echo "Building OpenDAL C library..."; \
		cd $(OPENDAL_C_DIR) && mkdir -p build && cd build && cmake .. -DFEATURES="opendal/services-memory,opendal/services-fs,opendal/services-http,opendal/services-s3" && cmake --build . --target cargo_build -j4; \
	else \
		echo "OpenDAL source not found at $(OPENDAL_C_DIR); skip (clone into vendor/opendal to enable)"; \
	fi

# Build OpenDAL Zig plugin (optional; requires opendal-c artifacts)
zig-opendal: install-zig opendal-c
	@if [ -f "$(OPENDAL_LIB_DIR)/libopendal_c.a" ]; then \
		echo "Building OpenDAL plugin..."; \
		mkdir -p plugins/zig/opendal/bin; \
		cd plugins/zig/opendal && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) \
			-I$(OPENDAL_INCLUDE) -L$(OPENDAL_LIB_DIR) -lopendal_c -lc -femit-bin=bin/opendal; \
	else \
		echo "OpenDAL C library not built; skipping zig-opendal (run 'make opendal-c' once vendor/opendal is present)"; \
	fi

# Run Zig plugin tests
zig-plugins-test: zig-plugins
	@echo "Testing Zig plugins..."
	cd plugins/zig/csv && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/json && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/jsonl && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/gz && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/yaml && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/toml && $(ZIG) test -fllvm $(PLUGIN_MODULES)
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
	cd libs/zig/jn-address && $(ZIG) test src/root.zig -fllvm
	@echo "  jn-address: OK"
	cd libs/zig/jn-profile && $(ZIG) test src/root.zig -fllvm
	@echo "  jn-profile: OK"
	cd libs/zig/jn-discovery && $(ZIG) test src/root.zig -fllvm
	@echo "  jn-discovery: OK"
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
	$(ZIG) fmt libs/zig/jn-address/src/
	$(ZIG) fmt libs/zig/jn-profile/src/
	$(ZIG) fmt libs/zig/jn-discovery/src/
	$(ZIG) fmt libs/zig/examples/
	$(ZIG) fmt tools/zig/

# =============================================================================
# Zig CLI Tools (Phase 5)
# =============================================================================

# Module definitions for CLI tools (includes address library)
TOOL_MODULES := --dep jn-core --dep jn-cli --dep jn-address \
	-Mroot=main.zig \
	-Mjn-core=../../../libs/zig/jn-core/src/root.zig \
	-Mjn-cli=../../../libs/zig/jn-cli/src/root.zig \
	-Mjn-address=../../../libs/zig/jn-address/src/root.zig

# Module definitions for jn orchestrator (minimal deps)
JN_MODULES := --dep jn-core \
	-Mroot=main.zig \
	-Mjn-core=../../../libs/zig/jn-core/src/root.zig

# Build CLI tools
zig-tools: install-zig
	@echo "Building Zig CLI tools..."
	mkdir -p tools/zig/jn-cat/bin
	mkdir -p tools/zig/jn-put/bin
	mkdir -p tools/zig/jn-filter/bin
	mkdir -p tools/zig/jn-head/bin
	mkdir -p tools/zig/jn-tail/bin
	mkdir -p tools/zig/jn-analyze/bin
	mkdir -p tools/zig/jn-inspect/bin
	mkdir -p tools/zig/jn-join/bin
	mkdir -p tools/zig/jn-merge/bin
	mkdir -p tools/zig/jn-sh/bin
	mkdir -p tools/zig/jn/bin
	cd tools/zig/jn-cat && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-cat
	cd tools/zig/jn-put && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-put
	cd tools/zig/jn-filter && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-filter
	cd tools/zig/jn-head && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-head
	cd tools/zig/jn-tail && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-tail
	cd tools/zig/jn-analyze && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-analyze
	cd tools/zig/jn-inspect && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-inspect
	cd tools/zig/jn-join && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-join
	cd tools/zig/jn-merge && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-merge
	cd tools/zig/jn-sh && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-sh
	cd tools/zig/jn && $(ZIG) build-exe -fllvm -O ReleaseFast $(JN_MODULES) -femit-bin=bin/jn
	@echo "Zig CLI tools built successfully"

# Test CLI tools
zig-tools-test: zig-tools
	@echo "Testing Zig CLI tools..."
	cd tools/zig/jn-cat && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn-put && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn-filter && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn-head && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn-tail && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn-analyze && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn-inspect && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn-join && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn-merge && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn-sh && $(ZIG) test -fllvm $(TOOL_MODULES)
	cd tools/zig/jn && $(ZIG) test -fllvm $(JN_MODULES)
	@echo "All Zig CLI tool tests passed"
