# Installing JN

JN is a universal data transformation tool built in Zig with Python plugin extensibility.

## Quick Install (Recommended)

The easiest way to install JN:

```bash
curl -sSfL https://raw.githubusercontent.com/botassembly/jn/main/install.sh | sh
```

This will:
- Detect your OS and architecture
- Download the latest release
- Install to `~/.local/jn`
- Add to your PATH

### Install Options

```bash
# Install specific version
JN_VERSION=0.1.0 curl -sSfL https://raw.githubusercontent.com/botassembly/jn/main/install.sh | sh

# Install to custom location
JN_INSTALL_DIR=/opt/jn curl -sSfL https://raw.githubusercontent.com/botassembly/jn/main/install.sh | sh

# Skip PATH modification
JN_NO_MODIFY_PATH=1 curl -sSfL https://raw.githubusercontent.com/botassembly/jn/main/install.sh | sh
```

## Supported Platforms

| Platform | Architecture | Status |
|----------|--------------|--------|
| Linux | x86_64 (amd64) | ✅ |
| Linux | aarch64 (arm64) | ✅ |
| macOS | x86_64 (Intel) | ✅ |
| macOS | aarch64 (Apple Silicon) | ✅ |

## Alternative Installation Methods

### Manual Download

Download from [GitHub Releases](https://github.com/botassembly/jn/releases):

```bash
# Linux x86_64
curl -LO https://github.com/botassembly/jn/releases/latest/download/jn-x86_64-linux.tar.gz
mkdir -p ~/.local/jn && tar -xzf jn-x86_64-linux.tar.gz -C ~/.local/jn --strip-components=1

# Linux ARM64
curl -LO https://github.com/botassembly/jn/releases/latest/download/jn-aarch64-linux.tar.gz
mkdir -p ~/.local/jn && tar -xzf jn-aarch64-linux.tar.gz -C ~/.local/jn --strip-components=1

# macOS Intel
curl -LO https://github.com/botassembly/jn/releases/latest/download/jn-x86_64-darwin.tar.gz
mkdir -p ~/.local/jn && tar -xzf jn-x86_64-darwin.tar.gz -C ~/.local/jn --strip-components=1

# macOS Apple Silicon
curl -LO https://github.com/botassembly/jn/releases/latest/download/jn-aarch64-darwin.tar.gz
mkdir -p ~/.local/jn && tar -xzf jn-aarch64-darwin.tar.gz -C ~/.local/jn --strip-components=1
```

Add to PATH:

```bash
# bash
echo 'export PATH="$HOME/.local/jn/bin:$PATH"' >> ~/.bashrc

# zsh
echo 'export PATH="$HOME/.local/jn/bin:$PATH"' >> ~/.zshrc

# fish
echo 'set -gx PATH "$HOME/.local/jn/bin" $PATH' >> ~/.config/fish/config.fish
```

### Docker

```bash
# Run directly
docker run --rm -i ghcr.io/botassembly/jn cat -~csv < data.csv

# Use in pipelines
cat data.json | docker run --rm -i ghcr.io/botassembly/jn filter '.items[]'

# Interactive
docker run --rm -it ghcr.io/botassembly/jn --help
```

Available tags:
- `latest` - Latest stable release
- `0.1.0` - Specific version
- `0.1` - Latest patch for minor version

### Nix

```bash
# Run without installing
nix run github:botassembly/jn -- --help

# Install to profile
nix profile install github:botassembly/jn

# Use in flake
{
  inputs.jn.url = "github:botassembly/jn";
}
```

### Build from Source

```bash
git clone https://github.com/botassembly/jn.git
cd jn
make build
source dist/activate.sh
```

See [CLAUDE.md](CLAUDE.md) for development details.

## Verify Installation

```bash
# Check version
jn --version

# Test basic functionality
echo '{"hello":"world"}' | jn filter '.'

# Read CSV
echo 'name,age
Alice,30
Bob,25' | jn cat -~csv

# Use the todo tool
jn tool todo add "My first task"
jn tool todo list
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

## What's Included

```
jn/
├── bin/                    # Main binary (only jn on PATH)
│   └── jn                  # Main orchestrator
├── libexec/jn/             # Internal tools (discovered automatically)
│   ├── jn-cat              # Universal reader
│   ├── jn-put              # Universal writer
│   ├── jn-filter           # JQ-like filtering
│   ├── jn-head, jn-tail    # Stream head/tail
│   ├── jn-join             # Hash join
│   ├── jn-merge            # Concatenate sources
│   ├── jn-analyze          # NDJSON statistics
│   ├── jn-inspect          # Schema inference
│   ├── jn-sh               # Shell commands as JSON
│   ├── jn-edit             # Surgical JSON editing
│   ├── zq                  # Filter engine
│   └── csv, json, yaml...  # Format plugins
└── jn_home/
    ├── tools/              # Utility tools (todo, etc.)
    ├── plugins/            # Python plugins (xlsx, gmail, etc.)
    └── profiles/           # Profile definitions
```

## Upgrading

Using the install script:

```bash
curl -sSfL https://raw.githubusercontent.com/botassembly/jn/main/install.sh | sh
```

Or manually:

```bash
curl -LO https://github.com/botassembly/jn/releases/latest/download/jn-x86_64-linux.tar.gz
tar -xzf jn-x86_64-linux.tar.gz -C ~/.local/jn --strip-components=1
```

## Uninstalling

```bash
# Remove installation
rm -rf ~/.local/jn

# Remove PATH from shell config
# Edit ~/.bashrc, ~/.zshrc, or ~/.config/fish/config.fish
```

## Troubleshooting

**Command not found**
- Ensure `~/.local/jn/bin` is in your PATH
- Run `source ~/.bashrc` (or your shell's config) or start a new terminal

**Plugin not found**
- Plugins are discovered relative to the `jn` binary
- Verify: `ls ~/.local/jn/bin/csv` or `ls ~/.local/jn/libexec/jn/csv`

**Python plugin errors**
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Check Python: `python3 --version`

**macOS Gatekeeper issues**
- If you see "cannot be opened because the developer cannot be verified":
  ```bash
  xattr -d com.apple.quarantine ~/.local/jn/bin/*
  ```
