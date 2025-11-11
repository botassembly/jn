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

### OpenAPI Profile Generation
**Design:** [openapi-profiles-design.md](openapi-profiles-design.md)

Auto-generate JN profiles from OpenAPI/Swagger specifications with hierarchical organization for large APIs.

**Key Features:**
- Auto-generate profiles from OpenAPI 3.0 specs
- Hierarchical subprofile organization (3-level max)
- Complete auth scheme mapping (Bearer, OAuth2, API Key, Basic)
- Schema inference from API response examples
- Profile inheritance with `_profile.json` base config
- Lazy loading for performance with large APIs

**Examples:**
```bash
# Generate from OpenAPI spec
jn profile generate stripe --from-openapi https://stripe.com/api/openapi.json

# Use generated hierarchical profile
jn cat @stripe/customers:list --limit 10

# Infer schema from examples
jn profile infer-schema users --from-examples example*.json
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
| OpenAPI Profiles | ✅ | 🔲 | 🔲 | 🔲 |

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
3. **Implement OpenAPI Profile Generation** - Follow openapi-profiles-design.md
   - OpenAPI 3.0 spec parser
   - Hierarchical profile generator
   - Auth scheme mapping
   - Schema inference with genson
4. **Create Bundled Profiles** - Add common API profiles (GitHub, Stripe, JSONPlaceholder)
5. **Write Tests** - Comprehensive test coverage
6. **Update Documentation** - User-facing docs and examples
