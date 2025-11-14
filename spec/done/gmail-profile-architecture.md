# Gmail Profile Architecture: Why Profiles vs Baking Into Plugin

**Status:** Implemented (as of Nov 2025)
**Related:** `spec/design/addressability.md`, `spec/design/profile-usage.md`

---

## Overview

Gmail in JN has a **two-layer architecture**:

1. **Plugin layer** (`jn_home/plugins/protocols/gmail_.py`) - Handles OAuth, API calls, message parsing
2. **Profile layer** (`jn_home/profiles/gmail/`) - Provides curated sources with memorable names

This document explains why we chose this architecture instead of baking everything into the plugin.

---

## The Alternative: Plugin-Only Design

We *could* have built Gmail as a single plugin where users write:

```bash
# Plugin-only approach (NOT what we did)
jn cat gmail://me/messages?in=inbox
jn cat gmail://me/messages?is=starred
jn cat gmail://me/messages?in=sent
jn cat gmail://me/messages?is=unread&from=boss@company.com
```

**Problems with this approach:**

1. **Cognitive load** - Users must remember Gmail query syntax (`in:`, `is:`, `has:`, etc.)
2. **No curation** - Common patterns (inbox, starred, sent) not elevated
3. **Verbose** - Every query requires full protocol URL
4. **Less discoverable** - Agents must know Gmail API structure
5. **No defaults** - Can't pre-fill common values (e.g., inbox always has `in=inbox`)

---

## The Chosen Design: Plugin + Profiles

### Architecture Layers

**Layer 1: Protocol Plugin** (`gmail_.py`)

- Handles `gmail://` URL protocol
- OAuth2 authentication and token refresh
- Gmail API client setup
- Message fetching and parsing to NDJSON
- Converts Gmail query params to API calls

**Layer 2: Profile Resolver** (`src/jn/profiles/gmail.py`)

- Converts `@gmail/source` → `gmail://` URLs
- Loads profile definitions from `jn_home/profiles/gmail/`
- Merges defaults from profile with user params
- Passes resolved URL to plugin layer

**Layer 3: Profile Definitions** (`jn_home/profiles/gmail/*.json`)

- `inbox.json` - Pre-filled with `{"in": "inbox"}`
- `starred.json` - Pre-filled with `{"is": "starred"}`
- `sent.json` - Pre-filled with `{"in": "sent"}`
- `unread.json` - Pre-filled with `{"is": "unread"}`
- `messages.json` - No defaults (full query flexibility)

### User Experience

```bash
# Profile layer provides memorable names
jn cat @gmail/inbox                           # → gmail://me/messages?in=inbox
jn cat @gmail/starred                         # → gmail://me/messages?is=starred
jn cat @gmail/sent                            # → gmail://me/messages?in=sent

# Profiles merge defaults + user params
jn cat @gmail/inbox?from=boss                 # → gmail://me/messages?in=inbox&from=boss
jn cat @gmail/starred?after=2024/01/01        # → gmail://me/messages?is=starred&after=2024/01/01

# Power users can bypass profiles
jn cat gmail://me/messages?is=unread&has=attachment   # Direct protocol URL
```

---

## Why This Design Works

### 1. **Enum Differentiation via Pre-filled Defaults**

The Gmail API has query parameters like:
- `in` → inbox, sent, trash, spam
- `is` → starred, unread, read, important

Instead of users remembering these enums and syntax, profiles differentiate them:

```json
// inbox.json
{
  "defaults": {"in": "inbox"},
  "params": ["from", "to", "subject", "after", "before"]
}

// starred.json
{
  "defaults": {"is": "starred"},
  "params": ["from", "to", "subject", "after", "before"]
}
```

**Result:** `@gmail/inbox` and `@gmail/starred` are different sources from the same API, curated for common use cases.

### 2. **Memorable Names Over Protocol Syntax**

Users think in terms of:
- "My inbox"
- "Starred messages"
- "Sent mail"

NOT in terms of:
- `gmail://me/messages?in=inbox`
- `gmail://me/messages?is=starred`
- `gmail://me/messages?in=sent`

Profiles map natural language to protocol syntax.

### 3. **OAuth Configuration Stays Central**

OAuth requires configuration:
- Token paths
- Credentials paths
- Scopes
- Client ID/secret

This belongs in `_meta.json`, not scattered across profile definitions:

```json
// jn_home/profiles/gmail/_meta.json
{
  "auth_type": "oauth2",
  "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
  "token_path": "~/.jn/gmail-token.json",
  "credentials_path": "~/.jn/gmail-credentials.json"
}
```

Every source (`inbox`, `starred`, etc.) inherits this OAuth config.

### 4. **Plugin Stays Protocol-Focused**

The plugin (`gmail_.py`) has one job:

- Match `gmail://` URLs
- Handle OAuth flow
- Call Gmail API
- Parse messages to NDJSON

It doesn't need to know about "inbox" vs "starred" - those are just different query params. The plugin is reusable for any Gmail query pattern.

### 5. **Profiles Enable Future Extensions**

Profiles can evolve without changing the plugin:

**Current:**
- Sources: inbox, starred, sent, unread, messages, attachments

**Future:**
- **Adapters**: `@gmail/inbox | @gmail/filters/summary` (extract just subject + sender)
- **Targets**: `@gmail/drafts` for creating draft emails
- **Pre-filled queries**: `@gmail/meetings` (all messages with calendar invites)
- **User customization**: Users add their own profiles to `~/.local/jn/profiles/gmail/`

The plugin stays unchanged; all extensions happen at the profile layer.

---

## Example: Resolution Flow

```bash
jn cat @gmail/inbox?from=boss
```

**Step 1: Profile resolution** (`src/jn/profiles/gmail.py`)
- Parse: `@gmail/inbox?from=boss`
- Load: `jn_home/profiles/gmail/inbox.json`
- Defaults: `{"in": "inbox"}`
- Merge: `{"in": "inbox", "from": "boss"}`
- Build URL: `gmail://me/messages?in=inbox&from=boss`

**Step 2: Plugin matching** (plugin registry)
- Pattern: `^gmail://.*` matches `gmail://me/messages?in=inbox&from=boss`
- Select: `gmail_.py`

**Step 3: Plugin execution** (`gmail_.py`)
- Authenticate: OAuth flow with token refresh
- Query: Gmail API with `q="in:inbox from:boss"`
- Parse: Messages → NDJSON records
- Output: Stream to stdout

**Result:** User gets curated experience (`@gmail/inbox`) but plugin handles protocol details (`gmail://`).

---

## Comparison: Other Protocols

### HTTP (No Profiles Needed)

HTTP URLs are already intuitive:

```bash
jn cat https://api.example.com/data.json
```

No profile needed - the URL is self-documenting.

### HTTP + REST API (Profiles Make Sense)

For complex REST APIs with many endpoints:

```bash
# Without profiles (verbose, non-intuitive)
jn cat https://your-org.genomoncology.com/api/alterations?gene=BRAF

# With profiles (curated, memorable)
jn cat @genomoncology/alterations?gene=BRAF
```

Profiles provide:
- Base URL hiding (`https://your-org.genomoncology.com/api`)
- Auth header injection (`Authorization: Token ${API_KEY}`)
- Pre-filled defaults (e.g., `limit=100`)
- Memorable source names

### MCP (Always Uses Profiles)

MCP servers have no standard URL scheme, so profiles are required:

```bash
jn cat @biomcp/search?gene=BRAF
```

The profile defines how to launch the MCP server (`uv run biomcp run`) and what tools it provides (`search`, `variant_search`, etc.).

---

## Key Takeaways

1. **Plugin layer** handles protocol-level concerns (OAuth, API calls, parsing)
2. **Profile layer** handles curation (memorable names, defaults, common patterns)
3. **Two layers together** provide both flexibility and usability
4. **Power users** can bypass profiles and use protocol URLs directly
5. **Casual users** get curated experience with `@gmail/inbox`
6. **Future extensions** (adapters, targets, custom sources) happen at profile layer

---

## Related Documents

- `spec/design/addressability.md` - Universal addressing syntax
- `spec/design/profile-usage.md` - How to declare and use profiles
- `src/jn/profiles/gmail.py` - Gmail profile resolver implementation
- `jn_home/plugins/protocols/gmail_.py` - Gmail protocol plugin
- `jn_home/profiles/gmail/` - Gmail profile definitions
