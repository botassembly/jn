# JN Design Documents

This directory contains detailed design specifications for JN features before implementation.

## Design Philosophy

Designs focus on **why** and **what**, not **how**. Include:
1. **Overview** - What the feature does and why it's needed
2. **Core Concepts** - Key architectural decisions
3. **Examples** - Real-world usage patterns
4. **Risks & Challenges** - What could go wrong
5. **Open Questions** - Trade-offs and decisions needed

**Avoid:** Implementation details, code samples, step-by-step instructions

---

## Phase 0 (Completed ✅)

### Implemented
- **Markdown Format Plugin** - `jn_home/plugins/formats/markdown_.py`
- **TOML Format Plugin** - `jn_home/plugins/formats/toml_.py`
- **JQ Profile System** - `jn_home/profiles/jq/builtin/` (pivot, group, stats, etc.)
- **HTTP Protocol Plugin** - `jn_home/plugins/protocols/http_.py`
- **Tabulate Display Plugin** - `jn_home/plugins/formats/tabulate_.py`
- **REST API Profiles** - GenomOncology, GitHub, JSONPlaceholder

---

## Phase 1 (Design Complete 📋)

### Core Architecture Documents

#### [http-design.md](http-design.md)
HTTP protocol plugin for fetching data from web APIs and remote files.

**Concepts:**
- Sources (endpoints that emit data)
- Streaming architecture (constant memory)
- Format auto-detection
- Profile integration

**Examples:**
```bash
jn cat https://api.example.com/data.json
jn cat @github/repos/owner/repo/issues
```

#### [rest-api-profiles.md](rest-api-profiles.md)
Profile system for REST APIs with clean `@profile/path` syntax.

**Concepts:**
- Sources (endpoints + method + filters)
- Hierarchical profiles (`_profile.json` + subfiles)
- Environment variable substitution
- OpenAPI/Swagger auto-generation

**Examples:**
```bash
jn cat @genomoncology/alterations?gene=BRAF
jn cat @genomoncology/annotations | \
  jn filter '@genomoncology/annotations:pivot-transcripts'
```

#### [format-design.md](format-design.md)
Format plugin architecture for bidirectional and display-only formats.

**Concepts:**
- Bidirectional formats (CSV, JSON, YAML, TOML)
- Display formats (tabulate, HTML tables)
- Streaming vs buffering trade-offs
- Table reading (future)

**Examples:**
```bash
jn cat data.csv | jn put output.json
jn cat data.json | jn put --plugin tabulate --tablefmt grid -
```

#### [genomoncology-api.md](genomoncology-api.md)
Real-world example: GenomOncology Precision Medicine API integration.

**Concepts:**
- Sources (alterations, annotations, clinical trials)
- Source-specific filters (pivot transcripts, extract HGVS)
- API parameter filtering vs JN filtering
- POST sources for batch operations

**Examples:**
```bash
jn cat @genomoncology/alterations?gene=BRAF
jn cat @genomoncology/annotations | \
  jn filter '@genomoncology/annotations:pivot-transcripts' | \
  jn put annotations.csv
```

#### [openapi-integration-ideas.md](openapi-integration-ideas.md)
20 ideas for enhancing JN with OpenAPI/Swagger specs and reverse-engineering techniques.

**Concepts:**
- Automatic profile generation from OpenAPI
- Parameter validation and auto-completion
- Response schema validation
- Reverse-engineering OpenAPI for non-spec APIs
- Agent and human benefits

**Key Ideas:**
- Generate profiles: `jn profile generate --from-openapi`
- Validate parameters before API calls
- Auto-complete parameter names
- Infer schemas from examples (GenSON library)
- LLM-powered documentation scraping

**Examples:**
```bash
# Generate profile from OpenAPI spec
jn profile generate genomoncology --from-openapi https://api.genomoncology.io/schema

# Reverse-engineer from samples
jn profile reverse-engineer example-api --from-samples data/*.json

# Use auto-completed parameters
jn cat @genomoncology/alterations -p <TAB>  # Shows: gene, mutation_type, ...
```

---

## Implementation Status

| Feature | Design | Implementation | Tests | Notes |
|---------|--------|----------------|-------|-------|
| **Phase 0** |
| TOML Format | ✅ | ✅ | ✅ | Complete |
| Markdown Format | ✅ | ✅ | ✅ | Complete |
| JQ Profiles | ✅ | ✅ | ✅ | Complete |
| HTTP Protocol | ✅ | ✅ | ✅ | Complete |
| Tabulate Display | ✅ | ✅ | ✅ | Complete |
| REST API Profiles | ✅ | ✅ | ✅ | Complete |
| **Phase 1** |
| OpenAPI Generation | ✅ | 🔲 | 🔲 | Design complete |
| Hierarchical Profiles | ✅ | 🔲 | 🔲 | Design complete |
| Source-Specific Filters | ✅ | 🔲 | 🔲 | Design complete |
| Table Reading | ✅ | 🔲 | 🔲 | Added to roadmap |

Legend: ✅ Complete | 🔲 Not Started | ⏳ In Progress

---

## Sources / Filters / Targets Architecture

### Core Concept

JN pipelines follow a simple model:

```
SOURCE → filter → filter → filter → TARGET
```

**Source:** Emits NDJSON data
- Files: `jn cat data.csv`
- URLs: `jn cat https://api.example.com/data`
- Profiles: `jn cat @genomoncology/alterations`

**Filter:** Transforms NDJSON stream
- JQ filters: `jn filter '.field > 100'`
- Named filters: `jn filter '@genomoncology/annotations:pivot-transcripts'`
- Chaining: Multiple filters compose

**Target:** Consumes NDJSON, produces output
- Files: `jn put output.csv`
- Stdout: `jn put -`
- Display: `jn put --plugin tabulate --tablefmt grid -`

### Chaining

Source + Filter = Still a source (conceptually):

```bash
# These are equivalent "sources" from a pipeline perspective:
jn cat @genomoncology/alterations
jn cat @genomoncology/alterations | jn filter '.gene == "BRAF"'
```

Both emit NDJSON and can pipe to more filters or a target.

---

## Design Documents

### By Topic

**HTTP & APIs:**
- `http-design.md` - HTTP plugin architecture
- `rest-api-profiles.md` - Profile system for APIs
- `genomoncology-api.md` - Real-world API example

**Formats:**
- `format-design.md` - Format plugin architecture

---

## Next Steps

### Phase 1 Implementation Priorities

1. **Hierarchical Profiles**
   - Implement `_profile.json` inheritance
   - Subprofile loading and merging
   - Profile discovery across multiple files

2. **Source-Specific Filters**
   - Implement pivot-transcripts.jq for GenomOncology
   - Add filter discovery from profile config
   - Document filter authoring patterns

3. **OpenAPI Generator**
   - Parse OpenAPI 3.0 specs
   - Generate profile structure
   - Map auth schemes to JN config

4. **Table Reading Plugin**
   - HTML table parsing (BeautifulSoup)
   - Markdown table parsing
   - ASCII table detection (best-effort)

### Phase 2 Exploration

1. **Profile Validation**
   - Lint profiles for security issues (hardcoded tokens)
   - JSON schema validation
   - Required env var detection

2. **Response Caching**
   - Optional HTTP response caching
   - Cache invalidation strategies
   - Profile-based cache config

3. **OAuth Token Refresh**
   - Automatic token refresh for OAuth2
   - Token storage and rotation
   - Security best practices

---

## Design Guidelines

### Focus on Why/What, Not How

**Good:**
> **Why:** Users shouldn't type the same base URL and auth headers for every request.
>
> **What:** Profiles centralize API configuration. Users reference endpoints with `@profile/path`.

**Bad:**
> ```python
> def resolve_profile(name):
>     path = Path(f"{JN_HOME}/profiles/{name}.json")
>     with open(path) as f:
>         return json.load(f)
> ```

### Include Risks & Trade-offs

Every design decision has risks. Document them:

**Example:**
> **Risk:** Profile name collisions between project/user/bundled.
>
> **Mitigation:** Clear precedence (project > user > bundled). Show which loaded with `jn profile info <name>`.

### Provide Real-World Examples

Abstract concepts need concrete usage:

**Bad:**
> Profiles support environment variable substitution.

**Good:**
> ```json
> {
>   "headers": {
>     "Authorization": "Token ${GENOMONCOLOGY_API_KEY}"
>   }
> }
> ```
>
> ```bash
> export GENOMONCOLOGY_API_KEY="abc123"
> jn cat @genomoncology/alterations  # Resolves to "Token abc123"
> ```

### Ask Open Questions

Designs aren't final. Capture uncertainty:

> **Open Question:** Should profiles cache responses?
>
> **Options:**
> - No caching (simple, predictable)
> - Optional `--cache` flag
> - Profile-based cache config
>
> **Trade-off:** Convenience vs. stale data risk.
>
> **Recommendation:** No caching initially. Add if users request.

---

## Document Organization

**By Scope:**
- **Core architecture:** http-design.md, format-design.md, rest-api-profiles.md
- **Real-world examples:** genomoncology-api.md
- **Feature-specific:** (future docs for specific plugins/profiles)

**Naming Convention:**
- Broad topics: `{topic}-design.md` (e.g., `http-design.md`)
- Specific APIs: `{api-name}-api.md` (e.g., `genomoncology-api.md`)
- Features: `{feature}-{aspect}.md` (e.g., `profile-validation.md`)

---

## Related Documentation

- **Implementation:** See `src/` for code
- **Roadmap:** See `spec/roadmap.md` for feature timeline
- **Architecture:** See `spec/arch/` for system design

