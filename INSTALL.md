# Installing JN

JN is a universal data transformation tool built in Zig with Python plugin extensibility.

## Quick Install (Linux x86_64)

Download the latest release and add to your PATH:

```bash
# Download latest release
curl -LO https://github.com/botassembly/jn/releases/latest/download/jn-linux-x86_64.tar.gz

# Extract to ~/.local/jn
mkdir -p ~/.local/jn
tar -xzf jn-linux-x86_64.tar.gz -C ~/.local/jn --strip-components=1

# Add to PATH (bash)
echo 'export PATH="$HOME/.local/jn/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Or for zsh
echo 'export PATH="$HOME/.local/jn/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Note:** `JN_HOME` is not required. JN automatically discovers tools and plugins relative to the executable.

## Verify Installation

```bash
# Check version
jn --version

# Test basic functionality
echo '{"hello":"world"}' | jn filter '.'

# Read a CSV file
echo 'name,age
Alice,30
Bob,25' | jn cat -~csv

# Use the todo tool
jn tool todo add "My first task"
jn tool todo list
```

## What's Included

The release package contains:

```
jn/
├── bin/                    # All executables
│   ├── jn                  # Main orchestrator
│   ├── jn-cat              # Universal reader (CSV, JSON, YAML, etc.)
│   ├── jn-put              # Universal writer
│   ├── jn-filter           # JQ-like filtering
│   ├── jn-head, jn-tail    # Stream head/tail
│   ├── jn-join             # Hash join two sources
│   ├── jn-merge            # Concatenate sources
│   ├── jn-analyze          # Statistics on NDJSON
│   ├── jn-inspect          # Schema inference
│   ├── jn-sh               # Shell commands as JSON
│   ├── jn-edit             # Surgical JSON editing
│   ├── zq                  # Filter engine
│   └── csv, json, jsonl, gz, yaml, toml  # Format plugins
└── jn_home/
    ├── tools/              # Utility tools (todo, etc.)
    ├── plugins/            # Python plugins (xlsx, gmail, duckdb, etc.)
    └── profiles/           # Profile definitions
```

## Python Plugins (Optional)

Some plugins require Python with `uv` for dependency management:

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Python plugins work automatically when uv is available
jn cat spreadsheet.xlsx    # Uses xlsx_ plugin
jn cat data.xml            # Uses xml_ plugin
```

## Building from Source

For development or building from source:

```bash
# Clone the repository
git clone https://github.com/botassembly/jn.git
cd jn

# Build and create distribution (downloads Zig automatically)
make bootstrap

# Activate jn in your current shell
source dist/activate.sh

# Verify
jn --version
jn tool todo --help
```

The `make bootstrap` command:
1. Downloads Zig if needed
2. Builds all tools and plugins
3. Creates a `dist/` directory with release layout
4. Generates `dist/activate.sh` for easy PATH setup

For development, you can also run individual targets:
```bash
make build    # Build tools/plugins in development layout
make test     # Run all tests
make dist     # Create release layout in dist/
```

## Upgrading

To upgrade to a new version:

```bash
# Download new release
curl -LO https://github.com/botassembly/jn/releases/latest/download/jn-linux-x86_64.tar.gz

# Extract over existing installation
tar -xzf jn-linux-x86_64.tar.gz -C ~/.local/jn --strip-components=1

# Verify
jn --version
```

## Uninstalling

```bash
# Remove installation
rm -rf ~/.local/jn

# Remove from shell config
# Edit ~/.bashrc or ~/.zshrc and remove the PATH line
```

## Troubleshooting

**Command not found**
- Ensure `~/.local/jn/bin` is in your PATH
- Run `source ~/.bashrc` or start a new terminal

**Plugin not found**
- Plugins are discovered relative to the `jn` binary
- Verify the installation: `ls ~/.local/jn/bin/csv`

**Python plugin errors**
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Check Python is available: `python3 --version`

**Tool not found (jn tool ...)**
- Tools are in `jn_home/tools/` relative to the binary
- Verify: `ls ~/.local/jn/jn_home/tools/`
