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

# Add to shell config (bash)
echo 'export JN_HOME="$HOME/.local/jn"' >> ~/.bashrc
echo 'export PATH="$JN_HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Or for zsh
echo 'export JN_HOME="$HOME/.local/jn"' >> ~/.zshrc
echo 'export PATH="$JN_HOME/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

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

# Convert CSV to JSON array
echo 'name,age
Alice,30' | jn cat -~csv | jn put output.json~json
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
    └── plugins/            # Python plugins (xlsx, gmail, duckdb, etc.)
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

# Build everything (downloads Zig automatically if needed)
make build

# Run tests
make test

# Add development build to PATH
export JN_HOME="$(pwd)"
export PATH="$(pwd)/tools/zig/jn/bin:$PATH"
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
# Edit ~/.bashrc or ~/.zshrc and remove the JN_HOME and PATH lines
```

## Troubleshooting

**Command not found**
- Ensure `$JN_HOME/bin` is in your PATH
- Run `source ~/.bashrc` or start a new terminal

**Plugin not found**
- Check that `$JN_HOME` is set correctly: `echo $JN_HOME`
- Verify plugins exist: `ls $JN_HOME/bin/csv`

**Python plugin errors**
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Check Python is available: `python3 --version`
