.PHONY: all build test check clean install-zig install-python-deps zq zq-test zig-plugins zig-plugins-test zig-libs zig-libs-test zig-tools zig-tools-test fmt

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

build: install-zig install-python-deps zq zig-plugins zig-tools
	@echo ""
	@echo "Build complete! Add to PATH:"
	@echo "  export PATH=\"$(PWD)/tools/zig/jn/bin:\$$PATH\""

test: build zig-libs-test zig-plugins-test zig-tools-test zq-test
	@echo ""
	@echo "All tests passed!"

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
# Zig plugins
# =============================================================================

zig-plugins: install-zig
	@echo "Building Zig plugins..."
	mkdir -p plugins/zig/csv/bin plugins/zig/json/bin plugins/zig/jsonl/bin
	mkdir -p plugins/zig/gz/bin plugins/zig/yaml/bin plugins/zig/toml/bin
	cd plugins/zig/csv && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/csv
	cd plugins/zig/json && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/json
	cd plugins/zig/jsonl && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/jsonl
	cd plugins/zig/gz && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/gz
	cd plugins/zig/yaml && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/yaml
	cd plugins/zig/toml && $(ZIG) build-exe -fllvm -O ReleaseFast $(PLUGIN_MODULES) -femit-bin=bin/toml

zig-plugins-test: zig-plugins
	@echo "Testing Zig plugins..."
	cd plugins/zig/csv && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/json && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/jsonl && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/gz && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/yaml && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	cd plugins/zig/toml && $(ZIG) test -fllvm $(PLUGIN_MODULES)
	@echo "  plugins: OK"

# =============================================================================
# Zig CLI tools
# =============================================================================

zig-tools: install-zig
	@echo "Building Zig CLI tools..."
	mkdir -p tools/zig/jn/bin tools/zig/jn-cat/bin tools/zig/jn-put/bin
	mkdir -p tools/zig/jn-filter/bin tools/zig/jn-head/bin tools/zig/jn-tail/bin
	mkdir -p tools/zig/jn-analyze/bin tools/zig/jn-inspect/bin
	mkdir -p tools/zig/jn-join/bin tools/zig/jn-merge/bin tools/zig/jn-sh/bin
	mkdir -p tools/zig/jn-edit/bin
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
	cd tools/zig/jn-edit && $(ZIG) build-exe -fllvm -O ReleaseFast $(TOOL_MODULES) -femit-bin=bin/jn-edit
	cd tools/zig/jn && $(ZIG) build-exe -fllvm -O ReleaseFast $(JN_MODULES) -femit-bin=bin/jn

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
	cd tools/zig/jn-edit && $(ZIG) test -fllvm $(TOOL_MODULES)
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
