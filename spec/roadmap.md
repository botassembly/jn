# JN Roadmap

## Completed (v4.0.0-alpha1)

- [x] Plugin-based architecture with regex discovery
- [x] Process-based streaming with automatic backpressure (Popen + pipes)
- [x] NDJSON as universal data format
- [x] File format readers (CSV, JSON, YAML, XML, XLSX)
- [x] File format writers (CSV, JSON, YAML, XML, XLSX)
- [x] Transport plugins (HTTP, S3, FTP)
- [x] Shell command plugins (ls, ps, find, etc.)
- [x] `jn cat` and `jn put` commands with auto-routing
- [x] Multi-transport XLSX support (HTTP, S3, FTP)
- [x] API/MCP integration design with profile system

## Next

### HTTP Plugin (v4.1.0)
- [ ] Generic HTTP plugin for REST APIs
- [ ] Profile system implementation
- [ ] Auth helpers (bearer, API key, basic)
- [ ] Pagination support (offset, cursor, link header)
- [ ] Example: GitHub API integration

### MCP Plugin (v4.2.0)
- [ ] Generic MCP plugin for MCP servers
- [ ] Profile system for MCP servers
- [ ] Server lifecycle management
- [ ] Example: GitHub MCP integration
- [ ] Example: Context7 integration

## Future

- Database plugins (PostgreSQL, MySQL, SQLite)
- Cloud storage (Azure, GCS)
- GraphQL support
- Profile templates and validation
- OpenAPI code generation
