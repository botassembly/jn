.PHONY: all build test check py-test clean install-zig install-python-deps zq zq-test zig-plugins zig-plugins-test zig-libs zig-libs-test zig-tools zig-tools-test fmt dist download

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

# Module definitions
PLUGIN_MODULES := --dep jn-core --dep jn-cli --dep jn-plugin \
	-Mroot=main.zig \
	-Mjn-core=../../../libs/zig/jn-core/src/root.zig \
	-Mjn-cli=../../../libs/zig/jn-cli/src/root.zig \
	-Mjn-plugin=../../../libs/zig/jn-plugin/src/root.zig

TOOL_MODULES := --dep jn-core --dep jn-cli --dep jn-address --dep jn-profile \
	-Mroot=main.zig \
	-Mjn-core=../../../libs/zig/jn-core/src/root.zig \
	-Mjn-cli=../../../libs/zig/jn-cli/src/root.zig \
	-Mjn-address=../../../libs/zig/jn-address/src/root.zig \
	-Mjn-profile=../../../libs/zig/jn-profile/src/root.zig

JN_MODULES := --dep jn-core \
	-Mroot=main.zig \
	-Mjn-core=../../../libs/zig/jn-core/src/root.zig

# =============================================================================
# Main targets
# =============================================================================

all: build

build: dist
	@# build is an alias for dist

test: dist zig-libs-test zig-plugins-test zig-tools-test zq-test py-test
	@echo ""
	@echo "All tests passed!"

py-test:
	@echo "Running Python tests..."
	uv run pytest
	@echo "  pytest: OK"
check: build
	@echo "Running integration checks..."
	@export JN_HOME="$(PWD)" && export PATH="$(PWD)/tools/zig/jn/bin:$$PATH" && \
	echo "  Checking jn version..." && \
	./tools/zig/jn/bin/jn --version && \
	echo "  Checking CSV read..." && \
	echo 'name,age\nAlice,30\nBob,25' | ./tools/zig/jn-cat/bin/jn-cat -~csv > /dev/null && \
	echo "  Checking JSON output..." && \
	echo '{"test":1}' | ./tools/zig/jn-filter/bin/jn-filter '.' > /dev/null && \
	echo "  Checking head..." && \
	echo '{"n":1}\n{"n":2}\n{"n":3}' | ./tools/zig/jn-head/bin/jn-head --lines=2 > /dev/null && \
	echo "  Checking tail..." && \
	echo '{"n":1}\n{"n":2}\n{"n":3}' | ./tools/zig/jn-tail/bin/jn-tail --lines=2 > /dev/null && \
	echo "  Checking merge..." && \
	echo '{"a":1}' > /tmp/jn_check_a.jsonl && \
	echo '{"b":2}' > /tmp/jn_check_b.jsonl && \
	./tools/zig/jn-merge/bin/jn-merge /tmp/jn_check_a.jsonl /tmp/jn_check_b.jsonl > /dev/null && \
	rm -f /tmp/jn_check_a.jsonl /tmp/jn_check_b.jsonl && \
	echo "" && \
	echo "All integration checks passed!"

clean:
	rm -rf zq/zig-out
	rm -rf plugins/zig/*/bin
	rm -rf tools/zig/*/bin
	rm -rf libs/zig/examples/bin
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# Zig compiler installation
# =============================================================================

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

# =============================================================================
# Python dependencies (for jn-sh shell command parsing)
# =============================================================================

install-python-deps:
	@echo "Installing Python dependencies..."
	@if command -v uv >/dev/null 2>&1; then \
		uv pip install --system jc 2>/dev/null || uv pip install jc; \
	elif command -v pip3 >/dev/null 2>&1; then \
		pip3 install --user jc; \
	elif command -v pip >/dev/null 2>&1; then \
		pip install --user jc; \
	else \
		echo "Warning: No pip/uv found. Install jc manually: pip install jc"; \
	fi
	@echo "Python dependencies installed."

# =============================================================================
# ZQ filter engine
# =============================================================================

zq: install-zig
	@echo "Building ZQ..."
	mkdir -p zq/zig-out/bin
	cd zq && $(ZIG) build-exe src/main.zig -fllvm -O ReleaseFast -femit-bin=zig-out/bin/zq

zq-test: zq
	cd zq && $(ZIG) test src/main.zig -fllvm
	cd zq && $(ZIG) test tests/integration.zig -fllvm
	@echo "  zq: OK"

# =============================================================================
# Zig libraries
# =============================================================================

zig-libs-test: install-zig
	@echo "Testing Zig libraries..."
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

# =============================================================================
# Zig plugins (can build in parallel with make -j)
# =============================================================================

PLUGINS := csv json jsonl gz yaml toml

# Individual plugin targets for parallel builds
.PHONY: plugin-csv plugin-json plugin-jsonl plugin-gz plugin-yaml plugin-toml
plugin-csv: ; @mkdir -p plugins/zig/csv/bin && cd plugins/zig/csv && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/csv
plugin-json: ; @mkdir -p plugins/zig/json/bin && cd plugins/zig/json && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/json
plugin-jsonl: ; @mkdir -p plugins/zig/jsonl/bin && cd plugins/zig/jsonl && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/jsonl
plugin-gz: ; @mkdir -p plugins/zig/gz/bin && cd plugins/zig/gz && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/gz
plugin-yaml: ; @mkdir -p plugins/zig/yaml/bin && cd plugins/zig/yaml && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/yaml
plugin-toml: ; @mkdir -p plugins/zig/toml/bin && cd plugins/zig/toml && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/toml

zig-plugins: install-zig plugin-csv plugin-json plugin-jsonl plugin-gz plugin-yaml plugin-toml
	@echo "All plugins built."

zig-plugins-test: zig-plugins
	@echo "Testing Zig plugins..."
	@for p in $(PLUGINS); do \
		cd plugins/zig/$$p && $(ZIG) test -fllvm $(PLUGIN_MODULES) && cd ../../..; \
	done
	@echo "  plugins: OK"

# =============================================================================
# Zig CLI tools (can build in parallel with make -j)
# =============================================================================

TOOLS := jn-cat jn-put jn-filter jn-head jn-tail jn-analyze jn-inspect jn-join jn-merge jn-sh jn-edit

# Individual tool targets for parallel builds
.PHONY: tool-jn tool-jn-cat tool-jn-put tool-jn-filter tool-jn-head tool-jn-tail tool-jn-analyze tool-jn-inspect tool-jn-join tool-jn-merge tool-jn-sh tool-jn-edit
tool-jn: ; @mkdir -p tools/zig/jn/bin && cd tools/zig/jn && $(ZIG) build-exe -fllvm -O ReleaseFast $(JN_MODULES) -femit-bin=bin/jn
tool-jn-cat: ; @mkdir -p tools/zig/jn-cat/bin && cd tools/zig/jn-cat && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-cat
tool-jn-put: ; @mkdir -p tools/zig/jn-put/bin && cd tools/zig/jn-put && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-put
tool-jn-filter: ; @mkdir -p tools/zig/jn-filter/bin && cd tools/zig/jn-filter && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-filter
tool-jn-head: ; @mkdir -p tools/zig/jn-head/bin && cd tools/zig/jn-head && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-head
tool-jn-tail: ; @mkdir -p tools/zig/jn-tail/bin && cd tools/zig/jn-tail && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-tail
tool-jn-analyze: ; @mkdir -p tools/zig/jn-analyze/bin && cd tools/zig/jn-analyze && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-analyze
tool-jn-inspect: ; @mkdir -p tools/zig/jn-inspect/bin && cd tools/zig/jn-inspect && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-inspect
tool-jn-join: ; @mkdir -p tools/zig/jn-join/bin && cd tools/zig/jn-join && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-join
tool-jn-merge: ; @mkdir -p tools/zig/jn-merge/bin && cd tools/zig/jn-merge && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-merge
tool-jn-sh: ; @mkdir -p tools/zig/jn-sh/bin && cd tools/zig/jn-sh && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-sh
tool-jn-edit: ; @mkdir -p tools/zig/jn-edit/bin && cd tools/zig/jn-edit && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-edit

zig-tools: install-zig tool-jn tool-jn-cat tool-jn-put tool-jn-filter tool-jn-head tool-jn-tail tool-jn-analyze tool-jn-inspect tool-jn-join tool-jn-merge tool-jn-sh tool-jn-edit
	@echo "All tools built."

zig-tools-test: zig-tools
	@echo "Testing Zig CLI tools..."
	@for t in $(TOOLS); do \
		cd tools/zig/$$t && $(ZIG) test -fllvm $(TOOL_MODULES) && cd ../../..; \
	done
	cd tools/zig/jn && $(ZIG) test -fllvm $(JN_MODULES)
	@echo "  tools: OK"

# =============================================================================
# Formatting
# =============================================================================

fmt: install-zig
	$(ZIG) fmt zq/src/ zq/tests/
	$(ZIG) fmt libs/zig/
	$(ZIG) fmt tools/zig/
	$(ZIG) fmt plugins/zig/

# =============================================================================
# Distribution build (release layout in dist/)
# =============================================================================

dist: install-zig install-python-deps zq zig-plugins zig-tools
	@echo "Creating distribution in dist/..."
	@rm -rf dist
	@mkdir -p dist/bin
	@mkdir -p dist/libexec/jn
	@# Copy jn orchestrator to bin/ (only thing on PATH)
	@cp tools/zig/jn/bin/jn dist/bin/
	@# Copy internal tools to libexec/jn/ (not on PATH)
	@for t in $(TOOLS); do cp tools/zig/$$t/bin/$$t dist/libexec/jn/; done
	@# Copy ZQ to libexec/jn/
	@cp zq/zig-out/bin/zq dist/libexec/jn/
	@# Copy plugins to libexec/jn/
	@for p in $(PLUGINS); do cp plugins/zig/$$p/bin/$$p dist/libexec/jn/; done
	@# Copy jn_home (Python plugins, user tools, profiles) to libexec/jn/
	@cp -r jn_home dist/libexec/jn/
	@# Create activate script with PATH and tool functions
	@echo '#!/bin/bash' > dist/activate.sh
	@echo '# Source this file to add jn to your PATH and set up shortcuts' >> dist/activate.sh
	@echo '' >> dist/activate.sh
	@echo '# Add jn to PATH (only jn is exposed; internal tools are in libexec/)' >> dist/activate.sh
	@echo 'export PATH="$$(cd "$$(dirname "$${BASH_SOURCE[0]}")" && pwd)/bin:$$PATH"' >> dist/activate.sh
	@echo '' >> dist/activate.sh
	@echo '# Shortcut functions for jn tools (add new tools here)' >> dist/activate.sh
	@echo 'todo() { jn tool todo "$$@"; }' >> dist/activate.sh
	@chmod +x dist/activate.sh
	@echo ""
	@echo "=== Build Complete ==="
	@echo ""
	@echo "Distribution layout:"
	@echo "  dist/bin/jn           - Main command (on PATH)"
	@echo "  dist/libexec/jn/      - Internal tools, plugins, zq (not on PATH)"
	@echo ""
	@echo "To activate jn:"
	@echo "  source dist/activate.sh"

# =============================================================================
# Download pre-built release
# =============================================================================

download:
	@./scripts/bootstrap-release.sh /tmp/jn-release
	@echo ""
	@echo "To use:"
	@echo "  export PATH=\"/tmp/jn-release/bin:\$$PATH\""
	@echo "  alias todo=\"jn tool todo\""
