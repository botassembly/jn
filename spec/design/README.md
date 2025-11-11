# JN Design Documents

This directory contains detailed design specifications for JN features before implementation.

## Phase 0 (Completed ✅)
- Markdown Format Plugin - Implemented in `jn_home/plugins/formats/markdown_.py`
- TOML Format Plugin - Implemented in `jn_home/plugins/formats/toml_.py`
- JQ Profile System - Implemented with built-in filters in `jn_home/profiles/jq/builtin/`

## Phase 1 (Design Complete 📋)

### HTTP Protocol Plugin
**Design:** [http-plugin-design.md](http-plugin-design.md)

HTTP protocol plugin for fetching data from HTTP/HTTPS endpoints with automatic format detection.

**Key Features:**
- GET/POST/PUT/DELETE support
- Automatic content-type detection (JSON, CSV, NDJSON)
- Custom headers and authentication
- Streaming for large responses
- Integration with profile system

**Examples:**
```bash
# Simple GET
jn cat https://opencode.ai/config.json

# With headers
jn cat https://api.example.com/data --headers '{"Authorization": "Bearer token"}'

# POST request
echo '{"query": "test"}' | jn cat https://api.example.com/search --method POST
```

### REST API Profile System
**Design:** [rest-api-profile-design.md](rest-api-profile-design.md)

Profile system for REST APIs providing reusable configs and clean `@profile/path` syntax.

**Key Features:**
- Base URL and authentication config
- Path templates with variables
- Environment variable substitution
- Method-based and path-based references
- Profile discovery and resolution

**Examples:**
```bash
# Path-based reference
jn cat @github/repos/microsoft/vscode/issues

# Method-based reference
jn cat @restful-api:list_objects

# With parameters
jn cat @api/users/{id} --id 123
```

### Usage Examples
**Document:** [http-usage-examples.md](http-usage-examples.md)

Comprehensive real-world examples covering:
- OpenCode.ai config processing
- RESTful API Dev workflows
- GitHub API integration
- Multi-API pipelines
- Authentication methods
- Error handling and debugging
- Pagination patterns
- Performance optimization

## Implementation Status

| Feature | Design | Implementation | Tests | Docs |
|---------|--------|----------------|-------|------|
| TOML Format | ✅ | ✅ | ✅ | Partial |
| Markdown Format | ✅ | ✅ | ✅ | Partial |
| JQ Profiles | ✅ | ✅ | ✅ | Partial |
| HTTP Protocol | ✅ | 🔲 | 🔲 | 🔲 |
| REST API Profiles | ✅ | 🔲 | 🔲 | 🔲 |

Legend: ✅ Complete | 🔲 Not Started | ⏳ In Progress

## Design Guidelines

When creating new design documents, include:

1. **Overview** - What the feature does and why it's needed
2. **Core Design** - Technical architecture and key decisions
3. **API/Interface** - How users interact with the feature
4. **Examples** - Real-world usage patterns
5. **Implementation Details** - Code structure and algorithms
6. **Testing Strategy** - How to validate the feature
7. **Integration** - How it works with existing features
8. **Future Enhancements** - Possible extensions

## Next Steps

1. **Implement HTTP Plugin** - Follow http-plugin-design.md
2. **Implement REST API Profiles** - Follow rest-api-profile-design.md
3. **Create Bundled Profiles** - Add common API profiles
4. **Write Tests** - Comprehensive test coverage
5. **Update Documentation** - User-facing docs and examples
