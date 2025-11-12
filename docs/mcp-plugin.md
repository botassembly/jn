# MCP Plugin for JN

The MCP (Model Context Protocol) plugin enables JN to read from and write to MCP servers, providing access to resources and tools through the standard MCP protocol.

## Overview

MCP is a protocol that allows applications to provide context for LLMs in a standardized way. This plugin allows JN to:

- **List resources** from MCP servers (documentation, files, data)
- **Read resources** and convert to NDJSON
- **List tools** available on MCP servers
- **Call tools** with parameters and get results
- **Write data** to MCP tools via NDJSON pipeline

## Installation

The plugin uses the official MCP Python SDK. It will be automatically installed via UV when the plugin runs.

## Configuration

Create an MCP server configuration file at one of these locations:

- `$JN_HOME/mcp-servers.json` (if JN_HOME is set)
- `~/.jn/mcp-servers.json` (default)
- `./mcp-servers.json` (current directory)

### Configuration Format

```json
{
  "server-name": {
    "command": "command-to-run",
    "args": ["arg1", "arg2"],
    "env": {
      "ENV_VAR": "value"
    }
  }
}
```

### Example Configuration

See `mcp-servers.example.json` for a complete example with BioMCP, Context7, and Desktop Commander.

```json
{
  "biomcp": {
    "command": "uv",
    "args": ["run", "--with", "biomcp-python", "biomcp", "run"],
    "description": "Biomedical data access"
  },
  "context7": {
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp@latest"],
    "description": "Code documentation"
  }
}
```

## Usage

### URL Format

MCP URLs follow this pattern:

```
mcp://server-name?param=value&param2=value2
```

Supported URL schemes:
- `mcp://` - Default stdio transport
- `mcp+stdio://` - Explicit stdio transport
- `mcp+http://` - HTTP transport (planned)

### Read Mode Operations

#### List Resources

List all available resources from an MCP server:

```bash
jn cat "mcp://biomcp?list=resources"
```

Output:
```json
{"type": "resource", "uri": "resource://trials", "name": "Clinical Trials", "description": "..."}
{"type": "resource", "uri": "resource://articles", "name": "Articles", "description": "..."}
```

#### Read a Resource

Read content from a specific resource:

```bash
jn cat "mcp://biomcp?resource=resource://trials/NCT12345"
```

Output:
```json
{"type": "resource_content", "uri": "resource://trials/NCT12345", "text": "...", "mimeType": "text/plain"}
```

#### List Tools

List all available tools from an MCP server:

```bash
jn cat "mcp://biomcp?list=tools"
```

Output:
```json
{"type": "tool", "name": "search", "description": "Search clinical trials", "inputSchema": {...}}
{"type": "tool", "name": "variant_search", "description": "Search genomic variants", "inputSchema": {...}}
```

#### Call a Tool

Call a tool with parameters:

```bash
jn cat "mcp://biomcp?tool=search&gene=BRAF&disease=Melanoma"
```

Output:
```json
{"type": "tool_result", "tool": "search", "text": "Found 42 trials...", "mimeType": "text/plain"}
```

### Write Mode Operations

Write mode allows you to pipe NDJSON data to MCP tools:

```bash
# Prepare search queries as NDJSON
echo '{"gene": "BRAF", "disease": "Melanoma"}' > queries.jsonl
echo '{"gene": "TP53", "disease": "Lung Cancer"}' >> queries.jsonl

# Call tool with each record
jn cat queries.jsonl | jn put "mcp://biomcp?tool=search"
```

Output (one result per input):
```json
{"type": "tool_result", "tool": "search", "text": "Found 42 trials for BRAF/Melanoma..."}
{"type": "tool_result", "tool": "search", "text": "Found 128 trials for TP53/Lung Cancer..."}
```

### Pipeline Examples

#### Search and Filter

```bash
# Search for trials and filter by phase
jn cat "mcp://biomcp?tool=search&condition=Cancer" | \
  jn filter '.text | contains("Phase 3")'
```

#### Convert Documentation to CSV

```bash
# Get documentation from Context7 and convert to table
jn cat "mcp://context7?tool=search&library=requests" | \
  jn filter '.text' | \
  jn put output.csv
```

#### Batch Processing

```bash
# Process multiple genes through BioMCP
jn cat genes.csv | \
  jn filter '{gene: .name, disease: "Cancer"}' | \
  jn put "mcp://biomcp?tool=search" | \
  jn put results.json
```

## Error Handling

Errors are returned as NDJSON records with `_error: true`:

```json
{
  "_error": true,
  "type": "config_not_found",
  "message": "MCP server 'unknown' not found in config",
  "server_name": "unknown"
}
```

Common error types:
- `config_not_found` - Server not configured
- `unsupported_transport` - Transport not supported yet
- `mcp_error` - General MCP protocol error
- `json_decode_error` - Invalid JSON in input

## Architecture

The plugin bridges JN's synchronous subprocess model with MCP's async protocol:

1. **Plugin Discovery**: Matches `mcp://` URLs via regex patterns
2. **Configuration Loading**: Reads server config from JSON file
3. **Transport**: Currently supports stdio (HTTP planned)
4. **Async Bridge**: Uses `asyncio.run()` to execute async MCP operations
5. **NDJSON Conversion**: Converts MCP responses to NDJSON records

### Transports

**Stdio (Current)**:
- Launches MCP server as subprocess
- Communicates via stdin/stdout
- Most common for local servers

**HTTP (Planned)**:
- Connects to remote MCP servers
- Uses SSE or WebSocket transports
- For cloud-hosted MCP services

## Testing

### With Desktop Commander (File System)

Desktop Commander provides a good test environment for write operations:

```bash
# Configure desktop-commander in mcp-servers.json
# List available tools
jn cat "mcp://desktop-commander?list=tools"

# Execute a command
jn cat "mcp://desktop-commander?tool=execute_command&command=ls"
```

### With BioMCP (Biomedical Data)

```bash
# Install BioMCP
uv tool install biomcp-python

# Test resource listing
jn cat "mcp://biomcp?list=resources"

# Search clinical trials
jn cat "mcp://biomcp?tool=search&condition=Melanoma&phase=PHASE3"
```

### With Context7 (Documentation)

```bash
# Install Context7 (requires Node.js)
npm install -g @upstash/context7-mcp

# Get documentation
jn cat "mcp://context7?tool=search&library=mcp"
```

## Implementation Details

### File Structure

```
jn_home/plugins/protocols/mcp_.py    # Main plugin implementation
mcp-servers.example.json             # Example configuration
docs/mcp-plugin.md                   # This documentation
```

### Dependencies

- `mcp>=1.1.0` - Official MCP Python SDK (installed via PEP 723)

### Plugin Interface

The plugin implements JN's standard interface:

- `reads(url, **params) -> Iterator[dict]` - Read from MCP server
- `writes(**config) -> None` - Write NDJSON to MCP tools
- `--mode read|write` CLI flag for operation mode

## Known Limitations

1. **HTTP Transport**: Not yet implemented (stdio only)
2. **Async Performance**: Each operation creates new event loop (could be optimized)
3. **Connection Pooling**: No connection reuse across calls
4. **Streaming**: Large responses loaded in memory (not streamed)

## Future Enhancements

1. **HTTP/SSE Transport**: Support remote MCP servers
2. **Connection Pooling**: Reuse sessions for multiple operations
3. **Streaming**: True streaming for large resources
4. **Caching**: Cache resource metadata and tool schemas
5. **MCP Profiles**: JN profiles for common MCP operations

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [BioMCP](https://biomcp.org/)
- [Context7](https://github.com/upstash/context7)
- [Desktop Commander](https://github.com/wonderwhy-er/DesktopCommanderMCP)

## Contributing

To add support for new transports or improve performance:

1. Follow JN plugin conventions (PEP 723, duck typing)
2. Maintain NDJSON as universal format
3. Use subprocess.Popen for pipeline compatibility
4. Add tests in `tests/plugins/test_mcp.py`

## Support

For issues or questions:
- JN Framework: Check `spec/` directory
- MCP Protocol: See [modelcontextprotocol.io](https://modelcontextprotocol.io/)
- Plugin-specific: Open issue in JN repository
