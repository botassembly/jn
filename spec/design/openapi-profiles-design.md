# OpenAPI Profile Generation & Large API Organization - Design

## What

Auto-generate JN profiles from OpenAPI/Swagger specifications, infer schemas from API responses, and organize large APIs with hierarchical subprofiles.

## Why

**Problem:** Large APIs have hundreds of endpoints. Manually creating profiles is tedious and error-prone.

**Solution:** Generate profiles automatically from API specs or examples, organize hierarchically for discoverability.

## Core Challenges

### 1. Large API Complexity
APIs like Stripe (300+ endpoints), AWS (1000+ endpoints), or Salesforce need organization beyond flat files.

### 2. Authentication Variety
OpenAPI supports: OAuth2, Bearer, API Key (header/query), Basic Auth, custom schemes.

### 3. Schema Validation
Validating requests/responses against schemas catches errors early.

### 4. Schema Inference
Not all APIs have OpenAPI specs. Need to infer structure from examples.

---

## Design 1: OpenAPI Profile Generation

### Auto-Generate from Swagger/OpenAPI

**Input:** OpenAPI 3.0 spec (JSON/YAML)
**Output:** Hierarchical JN profile structure

### Command
```bash
# Generate profile from OpenAPI spec
jn profile generate stripe --from-openapi https://stripe.com/api/openapi.json

# Generate from local file
jn profile generate myapi --from-openapi ./openapi.yaml

# Generate with custom auth
jn profile generate github \
  --from-openapi https://api.github.com/openapi.json \
  --auth-env GITHUB_TOKEN
```

### Generated Structure
```
~/.local/jn/profiles/http/stripe/
├── _profile.json          # Base config (auth, base_url)
├── customers.json         # Customer endpoints
├── charges.json           # Charge endpoints
├── subscriptions.json     # Subscription endpoints
└── invoices.json          # Invoice endpoints
```

### Base Profile (_profile.json)
```json
{
  "base_url": "https://api.stripe.com/v1",
  "auth": {
    "type": "bearer",
    "token": "${STRIPE_API_KEY}"
  },
  "headers": {
    "Stripe-Version": "2023-10-16"
  },
  "openapi_spec": "https://stripe.com/api/openapi.json",
  "generated_at": "2024-01-15T10:00:00Z"
}
```

### Subprofile (customers.json)
```json
{
  "extends": "_profile",
  "methods": {
    "list": {
      "path": "/customers",
      "method": "GET",
      "description": "List all customers",
      "parameters": {
        "limit": {"type": "integer", "default": 10},
        "starting_after": {"type": "string"}
      },
      "response_schema": "Customer[]"
    },
    "get": {
      "path": "/customers/{id}",
      "method": "GET",
      "description": "Retrieve customer by ID",
      "parameters": {
        "id": {"type": "string", "required": true}
      }
    },
    "create": {
      "path": "/customers",
      "method": "POST",
      "description": "Create new customer",
      "request_schema": {
        "email": {"type": "string", "required": true},
        "name": {"type": "string"},
        "metadata": {"type": "object"}
      }
    }
  }
}
```

### Usage
```bash
# List customers (uses stripe/customers.json)
jn cat @stripe/customers:list

# Get specific customer
jn cat @stripe/customers:get --id cus_123

# Create customer
echo '{"email":"user@example.com","name":"Alice"}' | \
  jn cat @stripe/customers:create --method POST

# Alternative path-based syntax
jn cat @stripe/customers/cus_123
```

---

## Design 2: Hierarchical Profile Organization

### Directory Structure

**Flat (current):** `~/.local/jn/profiles/http/github.json`

**Hierarchical (proposed):**
```
~/.local/jn/profiles/http/
├── github/
│   ├── _profile.json       # Base config
│   ├── repos.json          # Repo endpoints
│   ├── issues.json         # Issue endpoints
│   ├── pulls.json          # PR endpoints
│   └── users.json          # User endpoints
│
├── aws/
│   ├── _profile.json       # AWS base config
│   ├── s3/
│   │   ├── _profile.json   # S3-specific config
│   │   ├── buckets.json
│   │   └── objects.json
│   ├── ec2/
│   │   ├── instances.json
│   │   └── volumes.json
│   └── lambda/
│       └── functions.json
│
└── stripe/
    ├── _profile.json
    ├── customers.json
    ├── charges.json
    └── subscriptions.json
```

### Profile Inheritance

**Base profile** (`_profile.json`) provides shared config:
- `base_url`
- `auth`
- `headers`
- Common parameters

**Subprofiles** inherit and extend:
- Reference base: `"extends": "_profile"`
- Override specific fields
- Add endpoint-specific methods

### Resolution Algorithm

```
@stripe/customers:list
     ↓
1. Find: profiles/http/stripe/
2. Load: stripe/_profile.json (base config)
3. Load: stripe/customers.json (merge with base)
4. Resolve: customers:list method
5. Return: URL + headers + auth
```

### Syntax Options

**Subprofile method:**
```bash
@profile/subprofile:method
@stripe/customers:list
@aws/s3/buckets:list
```

**Path-based:**
```bash
@profile/subprofile/path
@stripe/customers/cus_123
@aws/s3/my-bucket/file.txt
```

**Shorthand (if unique):**
```bash
@stripe:list_customers  # Searches all subprofiles
```

---

## Design 3: Authentication Handling

### OpenAPI Auth Schemes → JN Config

#### 1. Bearer Token (OAuth2, JWT)
**OpenAPI:**
```yaml
securitySchemes:
  bearerAuth:
    type: http
    scheme: bearer
```

**Generated Profile:**
```json
{
  "auth": {
    "type": "bearer",
    "token": "${API_TOKEN}"
  }
}
```

#### 2. API Key (Header)
**OpenAPI:**
```yaml
securitySchemes:
  apiKey:
    type: apiKey
    in: header
    name: X-API-Key
```

**Generated Profile:**
```json
{
  "headers": {
    "X-API-Key": "${API_KEY}"
  }
}
```

#### 3. API Key (Query Parameter)
**OpenAPI:**
```yaml
securitySchemes:
  apiKey:
    type: apiKey
    in: query
    name: api_key
```

**Generated Profile:**
```json
{
  "auth": {
    "type": "query",
    "param": "api_key",
    "value": "${API_KEY}"
  }
}
```

#### 4. OAuth 2.0
**OpenAPI:**
```yaml
securitySchemes:
  oauth2:
    type: oauth2
    flows:
      authorizationCode:
        authorizationUrl: https://api.example.com/oauth/authorize
        tokenUrl: https://api.example.com/oauth/token
```

**Generated Profile:**
```json
{
  "auth": {
    "type": "oauth2",
    "flow": "authorization_code",
    "token_url": "https://api.example.com/oauth/token",
    "token": "${OAUTH_TOKEN}"
  }
}
```

**Note:** Phase 1 requires manual token fetch. Phase 2 auto-refresh.

#### 5. Basic Auth
**OpenAPI:**
```yaml
securitySchemes:
  basicAuth:
    type: http
    scheme: basic
```

**Generated Profile:**
```json
{
  "auth": {
    "type": "basic",
    "username": "${API_USERNAME}",
    "password": "${API_PASSWORD}"
  }
}
```

#### 6. Multiple Auth Schemes
Some APIs support multiple auth methods:

```json
{
  "auth": [
    {
      "type": "bearer",
      "token": "${BEARER_TOKEN}",
      "priority": 1
    },
    {
      "type": "apiKey",
      "header": "X-API-Key",
      "value": "${API_KEY}",
      "priority": 2
    }
  ]
}
```

Try in order of priority until one succeeds.

---

## Design 4: Schema Inference from Examples

### Use Cases

1. **API has no OpenAPI spec**
2. **Validate responses match expected structure**
3. **Generate documentation**
4. **Type hints for pipelines**

### Approach: Learn from Examples

```bash
# Fetch sample responses
jn cat @api/users/1 > example1.json
jn cat @api/users/2 > example2.json
jn cat @api/users/3 > example3.json

# Infer schema from examples
jn profile infer-schema users \
  --from-examples example*.json \
  --output schemas/user.json
```

### Generated Schema (JSON Schema)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string"},
    "email": {"type": "string", "format": "email"},
    "created_at": {"type": "string", "format": "date-time"},
    "metadata": {"type": "object"}
  },
  "required": ["id", "name", "email"]
}
```

### Schema Validation in Pipelines

```bash
# Validate response against schema
jn cat @api/users/123 --validate schemas/user.json

# Fail if schema mismatch
jn cat @api/users/123 --validate schemas/user.json --strict
```

### Schema Inference Tools

**Option 1: genson (Python)**
```bash
pip install genson
cat examples/*.json | genson
```

**Option 2: datamodel-code-generator (Pydantic)**
```bash
pip install datamodel-code-generator
datamodel-codegen --input examples.json --output models.py
```

**Option 3: json-schema-generator**
```bash
npm install -g json-schema-generator
json-schema-generator examples/*.json > schema.json
```

**JN Integration:**
Bundle `genson` in profile generator for automatic schema inference.

---

## Risks & Challenges

### 1. OpenAPI Spec Variations
**Risk:** OpenAPI 2.0 vs 3.0 vs 3.1 have different formats.

**Mitigation:**
- Support OpenAPI 3.0+ initially
- Use library (openapi-core, prance) for parsing
- Warn if unsupported version

### 2. Incomplete OpenAPI Specs
**Risk:** Specs missing auth details, examples, or schemas.

**Mitigation:**
- Allow manual override: `--auth-override`
- Generate partial profile, user fills gaps
- Document common gaps per API vendor

### 3. Schema Inference Accuracy
**Risk:** Inferred schema too loose (allows invalid data) or too strict (rejects valid data).

**Mitigation:**
- Require multiple examples (10+ recommended)
- Generate permissive schemas by default
- User reviews and tightens schema manually

### 4. Large API Performance
**Risk:** Loading 100+ subprofiles on every invocation.

**Mitigation:**
- Lazy load subprofiles (only load when accessed)
- Cache loaded profiles in memory
- Build index: `profile_index.json` maps methods to subprofiles

### 5. Profile Update Complexity
**Risk:** API changes, regenerated profile overwrites user customizations.

**Mitigation:**
- Never overwrite `_profile.json` without confirmation
- Store customizations separately: `_custom.json`
- Merge strategy: generated + custom

### 6. OAuth Token Refresh
**Risk:** OAuth tokens expire, require refresh flow.

**Mitigation:**
- Phase 1: User manually refreshes tokens
- Phase 2: Auto-refresh via refresh token
- Phase 3: Full OAuth flow (browser pop-up)

### 7. Subprofile Name Collisions
**Risk:** `@stripe/customers:list` vs `@customers:list` ambiguity.

**Mitigation:**
- Full path always works: `@stripe/customers:list`
- Shorthand only if unique across all profiles
- Error if ambiguous: "Did you mean @stripe/customers:list or @shopify/customers:list?"

### 8. API Versioning
**Risk:** API v1 vs v2 have different structures.

**Mitigation:**
- Profiles support version: `"api_version": "v2"`
- Generate separate profiles: `stripe-v1/`, `stripe-v2/`
- Base URL includes version: `https://api.stripe.com/v1`

---

## Open Questions

### 1. Should profiles cache responses?
- **Pro:** Reduce API calls, faster pipelines
- **Con:** Stale data, cache invalidation complexity
- **Decision:** Phase 1 no caching. Phase 2 optional cache with TTL.

### 2. Should schema validation be automatic?
- **Pro:** Catch errors early
- **Con:** Performance overhead, false positives
- **Decision:** Opt-in: `--validate schema.json`

### 3. Should we generate Pydantic models?
- **Pro:** Type safety in Python, better IDE support
- **Con:** Adds dependency, not all users need it
- **Decision:** Optional: `jn profile generate --output-pydantic`

### 4. How deep should hierarchy go?
- **Pro:** Unlimited depth matches API structure
- **Con:** Complex lookup, harder to navigate
- **Decision:** Max 3 levels: `profile/service/resource`

### 5. Should methods be separate files or inline?
- **Pro separate:** Better organization for large APIs
- **Con separate:** More files to manage
- **Decision:** Inline for <10 methods, separate for larger

---

## Implementation Phases

### Phase 1: Hierarchical Profiles (Manual)
- Support directory-based profiles
- Implement `_profile.json` inheritance
- Subprofile resolution: `@profile/sub:method`

### Phase 2: OpenAPI Generator
- Parse OpenAPI 3.0 specs
- Generate hierarchical profile structure
- Map auth schemes to JN config

### Phase 3: Schema Inference
- Bundle `genson` for schema generation
- `jn profile infer-schema` command
- Optional validation: `--validate`

### Phase 4: Advanced Auth
- OAuth 2.0 token refresh
- Multi-auth fallback
- Custom auth plugins

---

## Example: Stripe API

### Before (Manual, Flat)
```
~/.local/jn/profiles/http/stripe.json  # 500+ endpoints in one file
```

### After (Generated, Hierarchical)
```
~/.local/jn/profiles/http/stripe/
├── _profile.json           # Base: auth, base_url
├── customers.json          # 15 endpoints
├── charges.json            # 12 endpoints
├── subscriptions.json      # 20 endpoints
├── invoices.json           # 18 endpoints
├── payment_intents.json    # 14 endpoints
└── schemas/
    ├── customer.json       # Schema for Customer object
    ├── charge.json
    └── subscription.json
```

### Usage
```bash
# List customers
jn cat @stripe/customers:list --limit 10

# Get customer
jn cat @stripe/customers:get --id cus_123

# Create customer (validated against schema)
echo '{"email":"user@example.com"}' | \
  jn cat @stripe/customers:create \
    --validate stripe/schemas/customer.json
```

---

## Success Criteria

- ✅ Generate profiles from OpenAPI 3.0 specs
- ✅ Support 3-level hierarchical profiles
- ✅ Map all OpenAPI auth schemes to JN config
- ✅ Infer schemas from 10+ examples
- ✅ Validate responses against schemas (opt-in)
- ✅ Lazy load subprofiles for performance
- ✅ Handle API versioning in profiles
- ✅ Clear errors for ambiguous references

---

## Related Documents

- [REST API Profile Design](rest-api-profile-design.md) - Base profile system
- [HTTP Plugin Design](http-plugin-design.md) - HTTP transport layer
