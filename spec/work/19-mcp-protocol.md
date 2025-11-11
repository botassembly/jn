# MCP Protocol Plugin

## What
Model Context Protocol (MCP) plugin for reading from and writing to AI tools and agents. Enable JN as data source/sink for AI workflows.

## Why
AI agents need structured data access. MCP provides standard protocol for tools to expose data to language models. Make JN data available to Claude, GPT, and other AI agents.

## Key Features
- MCP server implementation (expose JN data to AI agents)
- MCP client implementation (read data from MCP servers)
- Resource exposure (files, databases, APIs via MCP)
- Tool invocation (allow AI to trigger JN pipelines)
- Streaming support (real-time data to agents)

## Dependencies
- `mcp` (Model Context Protocol Python SDK)
- Server and client implementations

## Server Mode
Expose JN data sources to AI agents:

**Profile:** `profiles/mcp/data-server.json`
```json
{
  "driver": "mcp_server",
  "port": 3000,
  "resources": {
    "database": "@mydb/active-users.sql",
    "api": "@restful-api-dev/objects",
    "files": "folder:///data/reports"
  }
}
```

Start server:
```bash
jn mcp serve --profile data-server
```

AI agent can now query:
```
Human: Get active users from the database
Claude: [Uses MCP to call jn cat @mydb/active-users.sql]
```

## Client Mode
Read data from other MCP servers:

```bash
# Read from MCP resource
jn cat mcp://localhost:3000/database/users | jn filter '.active == true' | jn jtbl

# Invoke MCP tool
jn cat mcp://localhost:3000/tool/fetch_sales_data --year 2024 | jn put sales.csv
```

## Use Cases
1. **Data Access for AI**: Expose databases, APIs, files to Claude/GPT
2. **AI-Triggered Pipelines**: Let AI agents invoke JN pipelines
3. **Tool Integration**: JN as data backend for AI tools
4. **Agent Collaboration**: Multiple agents sharing data via MCP

## Examples
```bash
# Expose database to AI
jn mcp serve --resource "users=@mydb/active-users.sql" --resource "sales=@mydb/sales.sql"

# Read from another MCP server
jn cat mcp://api-server:3000/resources/customer_data | jn filter '.tier == "premium"' | jn jtbl

# AI agent workflow
# Agent 1: Fetch data via MCP
# Agent 2: Process with JN pipeline
# Agent 3: Send results via MCP
```

## MCP Protocol Overview
- **Resources**: Static or dynamic data sources (files, DB queries, APIs)
- **Tools**: Invokable functions (trigger pipelines, transformations)
- **Prompts**: Template queries with parameters
- **Sampling**: Request completions from LLMs

## Out of Scope
- Complex tool orchestration - basic invocation only
- LLM inference - JN provides data, not completions
- Authentication/authorization - basic server only
- WebSocket transport - HTTP first
