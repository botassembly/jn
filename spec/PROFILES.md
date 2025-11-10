# JN Profiles - Configuration Management

## Overview

**Profiles** are JSON configuration files that store connection information, authentication, and settings for APIs, MCP servers, and other data sources. Instead of one monolithic config file, JN uses **one file per profile** for modularity and ease of management.

---

## Profile Locations

Profiles are discovered in priority order (same as plugins):

```
~/.jn/profiles/           # User profiles (personal, gitignored)
  ├─ github.json          # GitHub API
  ├─ work-s3.json         # AWS S3 (work account)
  ├─ openai.json          # OpenAI API
  └─ mcp/                 # MCP server profiles
     ├─ github.json
     └─ slack.json

./.jn/profiles/           # Project profiles (committed to git)
  ├─ dev-api.json         # Development environment
  ├─ staging-api.json     # Staging
  └─ prod-api.json        # Production
```

**Key Principles:**
- User profiles in `~/.jn/` (personal credentials)
- Project profiles in `./.jn/` (shared with team)
- Profile name = relative path without `.json`
- Subdirectories for organization (optional)

---

## Profile Types

Each profile has a `type` field that determines its schema.

### API Profile

Used for REST APIs with authentication, pagination, rate limiting.

**Schema:**
```json
{
  "type": "api",
  "base_url": "https://api.example.com",
  "auth": {
    "type": "bearer|basic|api_key|oauth",
    "token_env": "API_TOKEN",      // For bearer
    "username_env": "API_USER",    // For basic
    "password_env": "API_PASS",    // For basic
    "key_env": "API_KEY",          // For api_key
    "key_location": "header|query",  // Where to put API key
    "key_name": "X-API-Key"        // Header/query param name
  },
  "headers": {
    "Accept": "application/json",
    "User-Agent": "JN-ETL/4.0"
  },
  "pagination": {
    "type": "offset|cursor|link_header|none",
    "page_param": "page",          // For offset
    "per_page_param": "per_page",  // For offset
    "per_page": 100,
    "cursor_param": "cursor",      // For cursor
    "next_key": "next_cursor"      // Response field
  },
  "rate_limit": {
    "requests_per_second": 10,
    "requests_per_minute": 600,
    "requests_per_hour": 5000
  },
  "retry": {
    "max_attempts": 3,
    "backoff": "exponential|linear",
    "initial_delay": 1.0,
    "max_delay": 60.0
  },
  "timeout": 30
}
```

**Example (GitHub):**
```json
{
  "type": "api",
  "base_url": "https://api.github.com",
  "auth": {
    "type": "bearer",
    "token_env": "GITHUB_TOKEN"
  },
  "headers": {
    "Accept": "application/vnd.github.v3+json"
  },
  "pagination": {
    "type": "link_header",
    "per_page": 100
  },
  "rate_limit": {
    "requests_per_hour": 5000
  }
}
```

### MCP Profile

Used for Model Context Protocol servers.

**Schema:**
```json
{
  "type": "mcp",
  "server_command": "command to launch MCP server",
  "env": {
    "ENV_VAR": "${ENV_VAR}"  // Env vars for server
  },
  "timeout": 30,
  "description": "Human-readable description"
}
```

**Example (GitHub MCP):**
```json
{
  "type": "mcp",
  "server_command": "npx -y @modelcontextprotocol/server-github",
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
  },
  "timeout": 60,
  "description": "GitHub MCP server for issues, PRs, repos"
}
```

### Transport Profile

Used for cloud storage (S3, Azure, GCS).

**Schema:**
```json
{
  "type": "transport",
  "service": "s3|azure|gcs|ftp",
  "aws_profile": "profile-name",     // For S3
  "region": "us-east-1",             // For S3
  "endpoint_url": "https://...",     // For S3-compatible
  "account_name": "storage-account", // For Azure
  "container": "default-container",  // For Azure
  "project_id": "project-id",        // For GCS
  "ftp_username": "${FTP_USER}",     // For FTP
  "ftp_password": "${FTP_PASS}"      // For FTP
}
```

**Example (Work S3):**
```json
{
  "type": "transport",
  "service": "s3",
  "aws_profile": "work-account",
  "region": "us-east-1"
}
```

### OpenAPI Profile

Used for APIs with OpenAPI/Swagger specs.

**Schema:**
```json
{
  "type": "openapi",
  "spec_url": "https://example.com/openapi.json",
  "spec_file": "./openapi.yaml",  // Alternative to spec_url
  "base_url": "https://api.example.com",
  "auth": {
    "type": "bearer|api_key",
    "token_env": "API_TOKEN"
  },
  "operations": ["listUsers", "createUser"]  // Optional filter
}
```

---

## Profile Inheritance

Profiles can extend a base profile using `extends`:

**Base profile (`~/.jn/profiles/base-api.json`):**
```json
{
  "type": "api",
  "timeout": 30,
  "retry": {
    "max_attempts": 3,
    "backoff": "exponential"
  },
  "headers": {
    "User-Agent": "JN-ETL/4.0"
  }
}
```

**Child profile (`~/.jn/profiles/github.json`):**
```json
{
  "extends": "base-api",
  "base_url": "https://api.github.com",
  "auth": {
    "type": "bearer",
    "token_env": "GITHUB_TOKEN"
  },
  "headers": {
    "Accept": "application/vnd.github.v3+json"
  }
}
```

**Merged result:**
```json
{
  "type": "api",
  "base_url": "https://api.github.com",
  "timeout": 30,
  "retry": {
    "max_attempts": 3,
    "backoff": "exponential"
  },
  "auth": {
    "type": "bearer",
    "token_env": "GITHUB_TOKEN"
  },
  "headers": {
    "User-Agent": "JN-ETL/4.0",
    "Accept": "application/vnd.github.v3+json"
  }
}
```

**Merge rules:**
- Child overrides parent (shallow merge for simple values)
- Objects are deep merged (headers, auth, etc.)
- Arrays are replaced (not merged)

---

## CLI Usage

### Option 1: `--profile` flag (explicit)

```bash
# Use profile with jn cat
jn cat github://repos/anthropics/claude-code/issues --profile github

# Use profile with S3
jn cat s3://bucket/file.xlsx --profile work-s3

# Use profile with MCP filter
jn cat data.ndjson | jn filter mcp --profile github-mcp --tool create_issue

# Override profile settings
jn cat github://repos/user/repo/issues --profile github --timeout 60
```

### Option 2: `@profile` syntax (shorthand)

```bash
# Shorthand: @profile:resource
jn cat @github:repos/anthropics/claude-code/issues

# S3 with profile
jn cat @work-s3:bucket/file.xlsx

# MCP with profile
jn filter @github-mcp:create_issue < data.ndjson
```

**How `@profile` is parsed:**
```python
url = "@github:repos/anthropics/claude-code/issues"
profile_name, resource = url.split(':', 1)
profile = load_profile(profile_name.lstrip('@'))
# Build full URL from profile.base_url + resource
```

**Both syntaxes are supported!** Use `--profile` in scripts, `@profile` for interactive use.

---

## Profile Discovery

Profiles are discovered at runtime:

```python
# src/jn/profiles.py
def discover_profiles() -> dict[str, Path]:
    """Find all profiles in search paths."""
    paths = [
        Path.home() / '.jn' / 'profiles',  # User
        Path('.jn') / 'profiles',          # Project
    ]

    profiles = {}
    for base_path in paths:
        if not base_path.exists():
            continue

        # Find all .json files recursively
        for profile_path in base_path.rglob('*.json'):
            # Profile name: relative path without .json
            # Example: mcp/github.json → "mcp/github"
            rel_path = profile_path.relative_to(base_path)
            name = str(rel_path).replace('.json', '')

            # User profiles override project profiles
            if name not in profiles:
                profiles[name] = profile_path

    return profiles
```

**Profile resolution:**
1. Check `~/.jn/profiles/<name>.json` (user)
2. Check `./.jn/profiles/<name>.json` (project)
3. Raise `ProfileNotFoundError` if not found

---

## Profile Loading

```python
def load_profile(name: str) -> dict:
    """Load and validate profile."""
    profiles = discover_profiles()

    if name not in profiles:
        raise ProfileNotFoundError(
            f"Profile '{name}' not found. "
            f"Available: {', '.join(profiles.keys())}"
        )

    # Load JSON
    with open(profiles[name]) as f:
        profile = json.load(f)

    # Handle inheritance
    if 'extends' in profile:
        base = load_profile(profile['extends'])
        profile = deep_merge(base, profile)
        del profile['extends']

    # Validate schema
    validate_profile_schema(profile)

    # Resolve environment variables
    profile = resolve_env_vars(profile)

    return profile
```

**Environment variable resolution:**
```python
def resolve_env_vars(obj):
    """Replace ${VAR_NAME} with environment values."""
    if isinstance(obj, str):
        # ${VAR_NAME} → os.environ['VAR_NAME']
        # ${VAR_NAME:-default} → os.environ.get('VAR_NAME', 'default')
        return expand_env_var(obj)
    elif isinstance(obj, dict):
        return {k: resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_env_vars(v) for v in obj]
    else:
        return obj
```

---

## Profile Commands

New CLI commands for profile management:

### `jn profile list`

List all available profiles:

```bash
$ jn profile list
Available profiles:

User profiles (~/.jn/profiles/):
  - github (api)
  - work-s3 (transport)
  - openai (api)
  - mcp/github (mcp)
  - mcp/slack (mcp)

Project profiles (./.jn/profiles/):
  - dev-api (api)
  - staging-api (api)
  - prod-api (api)
```

### `jn profile show <name>`

Show profile details:

```bash
$ jn profile show github
Profile: github
Location: ~/.jn/profiles/github.json
Type: api

Configuration:
{
  "type": "api",
  "base_url": "https://api.github.com",
  "auth": {
    "type": "bearer",
    "token_env": "GITHUB_TOKEN"
  },
  ...
}

Environment variables:
  ✓ GITHUB_TOKEN (set)
```

### `jn profile validate <name>`

Validate profile schema:

```bash
$ jn profile validate github
✓ Profile 'github' is valid
✓ Schema validation passed
✓ All environment variables are set
```

### `jn profile create <name>`

Create new profile from template:

```bash
$ jn profile create myapi --type api
Created profile: ~/.jn/profiles/myapi.json
Edit with: jn profile edit myapi

$ jn profile create mymcp --type mcp
Created profile: ~/.jn/profiles/mymcp.json
```

### `jn profile edit <name>`

Open profile in `$EDITOR`:

```bash
$ jn profile edit github
# Opens ~/.jn/profiles/github.json in $EDITOR
```

### `jn profile test <name>`

Test profile connectivity:

```bash
$ jn profile test github --resource repos/anthropics/claude-code
Testing profile 'github' with resource 'repos/anthropics/claude-code'...
✓ Authentication successful
✓ Request successful (200 OK)
✓ Response valid JSON
✓ Profile is working correctly
```

---

## Plugin Integration

Plugins receive merged configuration:

```python
def run(config: dict) -> Iterator[dict]:
    """Config priority (highest to lowest):
    1. CLI flags (--timeout 60)
    2. Profile config (~/.jn/profiles/github.json)
    3. Plugin defaults
    """

    # Access profile settings
    base_url = config['base_url']
    headers = config.get('headers', {})
    auth = config.get('auth', {})
    timeout = config.get('timeout', 30)

    # Use auth helper
    from jn.api_helpers import AuthHelper
    headers.update(AuthHelper.apply(auth))

    # Make request
    url = f"{base_url}/{config['resource']}"
    response = requests.get(url, headers=headers, timeout=timeout)

    for item in response.json():
        yield item
```

**Config merging:**
```python
def merge_config(profile: dict, cli_args: dict, defaults: dict) -> dict:
    """Merge configs with priority."""
    config = {}
    config.update(defaults)      # Lowest priority
    config.update(profile)        # Medium priority
    config.update(cli_args)       # Highest priority
    return config
```

---

## Security Best Practices

### Never hardcode secrets

❌ **BAD:**
```json
{
  "auth": {
    "token": "ghp_abc123..."  // NEVER do this!
  }
}
```

✅ **GOOD:**
```json
{
  "auth": {
    "token_env": "GITHUB_TOKEN"  // Reference env var
  }
}
```

### Gitignore user profiles

```bash
# .gitignore
.jn/profiles/  # Project profiles are gitignored by default
```

**Exception:** Commit project profiles with env var references:
```json
{
  "auth": {
    "token_env": "PROJECT_API_TOKEN"  // OK to commit
  }
}
```

### Use different profiles per environment

```
./.jn/profiles/
  ├─ dev-api.json      # Points to dev environment
  ├─ staging-api.json  # Points to staging
  └─ prod-api.json     # Points to production
```

Usage:
```bash
# Development
jn cat @dev-api:users

# Production
jn cat @prod-api:users
```

---

## Migration from Old Config

If you have an old `~/.jn/config.json`:

```bash
$ jn profile migrate
Migrating ~/.jn/config.json to profiles...
  ✓ Created ~/.jn/profiles/github.json
  ✓ Created ~/.jn/profiles/slack.json
  ✓ Created ~/.jn/profiles/aws.json
  ✓ Backed up old config to ~/.jn/config.json.bak

Migration complete! Profiles created: 3
```

**Migration script:**
```python
def migrate_old_config():
    """Convert monolithic config.json to individual profiles."""
    old_config_path = Path.home() / '.jn' / 'config.json'
    if not old_config_path.exists():
        return

    old_config = json.loads(old_config_path.read_text())
    profiles_dir = Path.home() / '.jn' / 'profiles'
    profiles_dir.mkdir(exist_ok=True)

    # Split into individual profiles
    for name, profile in old_config.items():
        profile_path = profiles_dir / f'{name}.json'
        profile_path.write_text(json.dumps(profile, indent=2))
        print(f"  ✓ Created {profile_path}")

    # Backup old config
    backup_path = old_config_path.with_suffix('.json.bak')
    old_config_path.rename(backup_path)
    print(f"  ✓ Backed up old config to {backup_path}")
```

---

## Implementation Plan

### Phase 1: Profile Infrastructure
- [ ] `src/jn/profiles.py` - Profile discovery, loading, validation
- [ ] `src/jn/schemas.py` - JSON schemas for each profile type
- [ ] `tests/test_profiles.py` - Profile tests

### Phase 2: CLI Integration
- [ ] Update `src/jn/cli.py` - Add `--profile` flag
- [ ] Parse `@profile:resource` syntax
- [ ] Merge profile config with CLI args

### Phase 3: Profile Commands
- [ ] `jn profile list`
- [ ] `jn profile show <name>`
- [ ] `jn profile validate <name>`
- [ ] `jn profile create <name>`
- [ ] `jn profile edit <name>`
- [ ] `jn profile test <name>`

### Phase 4: Plugin Updates
- [ ] Update `plugins/http/rest_source.py` to use profiles
- [ ] Update `plugins/api/github/` to use profiles
- [ ] Update `plugins/mcp/` to use profiles

### Phase 5: Documentation
- [ ] User guide for profiles
- [ ] Profile examples
- [ ] Migration guide

---

## Examples

### GitHub Issues

**Profile (`~/.jn/profiles/github.json`):**
```json
{
  "type": "api",
  "base_url": "https://api.github.com",
  "auth": {
    "type": "bearer",
    "token_env": "GITHUB_TOKEN"
  },
  "headers": {
    "Accept": "application/vnd.github.v3+json"
  }
}
```

**Usage:**
```bash
# Get issues from repo
jn cat @github:repos/anthropics/claude-code/issues

# Filter open issues
jn cat @github:repos/anthropics/claude-code/issues | jq 'select(.state == "open")'

# Create new issue (target)
echo '{"title": "Bug report", "body": "..."}' | \
  jn write @github:repos/myuser/myrepo/issues
```

### S3 with Multiple Accounts

**Profiles:**
```bash
~/.jn/profiles/
  ├─ personal-s3.json  # Personal AWS account
  └─ work-s3.json      # Work AWS account
```

**personal-s3.json:**
```json
{
  "type": "transport",
  "service": "s3",
  "aws_profile": "personal",
  "region": "us-west-2"
}
```

**work-s3.json:**
```json
{
  "type": "transport",
  "service": "s3",
  "aws_profile": "work-account",
  "region": "us-east-1"
}
```

**Usage:**
```bash
# Personal bucket
jn cat @personal-s3:my-bucket/data.xlsx

# Work bucket
jn cat @work-s3:company-bucket/report.csv
```

### MCP Servers

**Profile (`~/.jn/profiles/mcp/github.json`):**
```json
{
  "type": "mcp",
  "server_command": "npx -y @modelcontextprotocol/server-github",
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
  },
  "description": "GitHub MCP server"
}
```

**Usage:**
```bash
# Execute MCP tool
jn filter @mcp/github:create_issue < issue-data.ndjson

# Or with --profile
jn filter mcp --profile mcp/github --tool create_issue < data.ndjson
```

---

## Summary

**Profiles provide:**
- ✅ Modular config (one file per profile)
- ✅ Easy sharing (commit project profiles)
- ✅ Type-safe (validated schemas)
- ✅ Hierarchical (inheritance via `extends`)
- ✅ Secure (secrets in env vars)
- ✅ Discoverable (`jn profile list`)
- ✅ Unix-like (similar to ~/.aws/config)

**This design scales from simple use cases to complex enterprise deployments.**
