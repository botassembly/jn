# REST API Profile System - Design

## What

Reusable API configurations that provide clean `@profile/path` syntax for accessing endpoints with built-in authentication and base URLs.

## Why

Eliminate repetition in API calls. Users shouldn't type the same base URL and auth headers for every request. Profiles enable:
- **One-time setup:** Configure API once, use everywhere
- **Clean syntax:** `@github/repos/owner/repo` vs full URL + headers
- **Credential safety:** Tokens in profiles, not command history
- **Team sharing:** Commit profiles to `.jn/profiles/` for team use

## Core Architecture

### Profile Structure

Profiles are JSON files defining API configuration:

```json
{
  "base_url": "https://api.github.com",
  "headers": {
    "Authorization": "Bearer ${GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
  },
  "timeout": 30
}
```

**Location hierarchy (first found wins):**
1. Project: `.jn/profiles/http/`
2. User: `~/.local/jn/profiles/http/`
3. Bundled: `jn_home/profiles/http/`

### Key Design Decisions

**1. Profile Syntax**

Two modes:

**Path-based:** `@profile/path/to/resource`
```bash
@github/repos/microsoft/vscode/issues
# Resolves to: https://api.github.com/repos/microsoft/vscode/issues
```

**Method-based:** `@profile:method_name`
```bash
@restful-api:list_objects
# Uses predefined method from profile
```

**Why:** Path-based is intuitive for REST APIs. Method-based enables complex operations without exposing implementation details.

**2. Environment Variable Substitution**

Headers support `${VAR}` syntax:
```json
"Authorization": "Bearer ${GITHUB_TOKEN}"
```

**Why:** Keeps secrets out of profiles. Profiles can be committed to git safely.

**3. Hierarchical Discovery**

Project → User → Bundled search order.

**Why:** Project profiles override user profiles. Teams can standardize APIs while individuals customize.

**4. Path Variable Substitution**

Templates support `{variable}` placeholders:
```json
"paths": {
  "user": "/users/{id}"
}
```

Used as: `@api/users/123` → resolves `{id}` to `123`

**Why:** RESTful URLs often have ID parameters. Templates make this explicit and type-safe.

## Profile Types

### Simple Profile
Basic URL + auth:
```json
{
  "base_url": "https://api.example.com",
  "headers": {"X-API-Key": "${API_KEY}"}
}
```

### Advanced Profile
With path templates and methods:
```json
{
  "base_url": "https://api.restful-api.dev",
  "paths": {
    "objects": "/objects",
    "object": "/objects/{id}"
  },
  "methods": {
    "create_object": {
      "path": "/objects",
      "method": "POST",
      "description": "Create new device"
    }
  }
}
```

## Usage Examples

### Direct URL vs Profile
```bash
# Without profile - repetitive
jn cat https://api.github.com/repos/microsoft/vscode/issues \
  --headers '{"Authorization": "Bearer ghp_..."}'

# With profile - clean
jn cat @github/repos/microsoft/vscode/issues
```

### Path Variables
```bash
# Profile defines: "/users/{id}"
jn cat @api/users/123  # Substitutes {id} with 123
```

### Named Methods
```bash
# Profile defines POST method
echo '{"name": "Test"}' | jn cat @restful-api:create_object
```

## Risks & Challenges

### 1. **Profile Name Collisions**
**Risk:** Two profiles with same name in different locations.

**Mitigation:**
- Clear precedence: project > user > bundled
- Warning message if profile overridden
- `jn profile info <name>` shows which file loaded

### 2. **Environment Variable Missing**
**Risk:** `${GITHUB_TOKEN}` undefined, silent substitution to empty string.

**Mitigation:**
- Check for undefined variables at runtime
- Error message: "Environment variable GITHUB_TOKEN not set"
- Document required env vars in profile

### 3. **Path Variable Ambiguity**
**Risk:** URL like `/users/123/posts` - is `123` the user ID or part of path?

**Mitigation:**
- Explicit templates: `/users/{user_id}/posts`
- Greedy matching: `/users/{id}` matches `/users/123/posts`
- Document pattern matching rules

### 4. **Authentication Token Exposure**
**Risk:** Tokens leaked in logs, error messages, or shell history.

**Mitigation:**
- Never log token values
- Mask tokens in error messages: `Bearer ghp_***`
- Environment variables, not command-line args

### 5. **Profile Portability**
**Risk:** Profiles with absolute paths or machine-specific config.

**Mitigation:**
- Encourage relative paths
- Environment variables for machine-specific values
- Document portability best practices

### 6. **Method vs Path Confusion**
**Risk:** Users unsure when to use `@profile/path` vs `@profile:method`

**Mitigation:**
- Default to path-based (simpler, more RESTful)
- Methods for complex operations (multi-step, non-standard)
- Clear examples in documentation

### 7. **Credential Rotation**
**Risk:** API keys change, break all pipelines using profile.

**Mitigation:**
- Environment variables make rotation easy (update once)
- Profile versioning for breaking changes
- Document rotation procedures

### 8. **Profile Validation**
**Risk:** Typos in profile JSON break at runtime.

**Mitigation:**
- `jn profile validate <name>` command
- JSON schema validation
- Check profile on first use, cache validation

## Open Questions

1. **Profile Namespacing:** Should profiles support nested directories?
   - Pro: Better organization (`http/github/`, `http/stripe/`)
   - Con: More complex lookup logic
   - Decision: Phase 1 flat, Phase 2 nested if needed

2. **Profile Inheritance:** Should profiles extend other profiles?
   - Pro: Reduce duplication (base + environment-specific)
   - Con: Complexity, harder to debug
   - Decision: Phase 1 no inheritance, document copy-paste patterns

3. **Dynamic Base URLs:** Should base URL support env vars?
   - Pro: Dev vs prod environments
   - Con: More complexity
   - Decision: Yes, `"base_url": "https://${ENV}.api.com"`

4. **Profile Caching:** Should resolved profiles be cached?
   - Pro: Faster repeated lookups
   - Con: Stale cache if profile changes
   - Decision: Cache with file mtime checking (like plugin cache)

5. **Method Parameters:** Should methods support parameters?
   - Pro: More flexible (pagination, filters)
   - Con: Complex syntax
   - Decision: Phase 1 no, use path variables instead

## Integration Points

### With HTTP Plugin
Profile resolution happens before HTTP plugin invocation:
```
User input: @github/repos/owner/repo
     ↓
Profile system: Load github.json, resolve base_url + headers
     ↓
HTTP plugin: Fetch resolved URL with resolved headers
```

### With CLI
Extend `jn cat` to detect `@` prefix and delegate to profile resolver.

### Profile Management
New `jn profile` subcommands:
- `jn profile list` - Show all profiles
- `jn profile info <name>` - Show profile details
- `jn profile test <name>` - Test connection
- `jn profile validate <name>` - Check JSON syntax

## Success Criteria

- ✅ Load profiles from hierarchical search paths
- ✅ Resolve `@profile/path` to full URL
- ✅ Substitute environment variables in headers
- ✅ Support path variables (`{id}`)
- ✅ Clear error if profile not found
- ✅ Profile overriding (project > user > bundled)
- ✅ Integration with HTTP plugin

## Bundled Profiles

Include common APIs for testing and examples:

**`jn_home/profiles/http/httpbin.json`** - HTTP testing service
**`jn_home/profiles/http/jsonplaceholder.json`** - Fake REST API
**`jn_home/profiles/http/restful-api.json`** - Device API demo

**Why:** Users can experiment immediately without setup.

## Future Enhancements

- **OpenAPI Integration:** Generate profiles from OpenAPI/Swagger specs
- **Rate Limiting:** Profile-based rate limit config
- **OAuth Flows:** Automated OAuth 2.0 token refresh
- **Profile Encryption:** Encrypt sensitive profiles at rest
- **Profile Sharing:** Publish/subscribe profile registry
- **Versioning:** Profile schema versions for breaking changes

## Related Documents

- [HTTP Plugin Design](http-plugin-design.md) - HTTP protocol implementation
- [HTTP Usage Examples](http-usage-examples.md) - Real-world patterns
