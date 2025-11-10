# JN Roadmap - From Alpha to Production

**Current Version:** 4.0.0-alpha1 (78% coverage, 105 tests)
**Target:** Production-ready agent-native ETL framework

---

## Release Timeline

| Version | Target Date | Focus | Status |
|---------|------------|-------|--------|
| **4.0.0-alpha1** | 2025-11-09 | Core framework + 19 plugins | ✅ **COMPLETE** |
| **4.0.0-beta1** | Week +2 | Polish + advanced features | 📋 PLANNED |
| **4.0.0-rc1** | Week +4 | Production hardening | 📋 PLANNED |
| **4.0.0** | Week +6 | Public release | 📋 PLANNED |
| **4.1.0** | Week +10 | Database + Excel | 📋 PLANNED |
| **4.2.0** | Week +14 | Cloud + MCP | 📋 PLANNED |

---

## ✅ Completed (v4.0.0-alpha1)

### Core Framework
- [x] Function-based plugin system
- [x] Regex-based discovery (no imports)
- [x] Extension/URL/command registry
- [x] Pipeline auto-detection
- [x] Unix pipe execution
- [x] UV dependency management
- [x] PEP 723 inline dependencies

### CLI Commands (10)
- [x] `jn discover` - List all plugins
- [x] `jn show <plugin>` - Plugin details
- [x] `jn which <ext>` - Find plugin for extension
- [x] `jn run <input> <output>` - Auto pipeline
- [x] `jn paths` - Show plugin search paths
- [x] `jn cat <source>` - Read source, output NDJSON
- [x] `jn put <target>` - Write NDJSON to target
- [x] `jn create <type> <name>` - Scaffold plugin
- [x] `jn test <plugin>` - Run plugin tests
- [x] `jn validate <file>` - Check plugin structure

### Plugins (19)
- [x] **Readers (8):** CSV, JSON, YAML, XML, TOML, HTTP, ls, ps
- [x] **Writers (6):** CSV, JSON, YAML, XML, NDJSON, stdout
- [x] **Filters (1):** jq
- [x] **Shell (7):** ls, ps, df, env, find, ping, netstat, dig

### Testing
- [x] 105 tests passing (100%)
- [x] 78% coverage
- [x] Outside-in CLI testing
- [x] Plugin self-tests
- [x] Integration tests

### Documentation
- [x] README with examples
- [x] Architecture documentation
- [x] Plugin development guide
- [x] Coverage review
- [x] Implementation plan

---

## 📋 v4.0.0-beta1 (Week +2)

**Goal:** Production-ready CLI with polish and advanced features

### CLI Improvements
- [ ] `jn --version` - Show version info
- [ ] `jn config` - Manage configuration
- [ ] `jn config set <key> <value>` - Set config values
- [ ] `jn config get <key>` - Get config values
- [ ] `jn plugins install <url>` - Install plugin from URL
- [ ] `jn plugins update` - Update all plugins
- [ ] `jn plugins search <query>` - Search plugin registry

### Error Handling
- [ ] Detailed error messages with context
- [ ] Suggestion system ("Did you mean...?")
- [ ] Error codes for automation
- [ ] Debug mode (`--debug` flag)
- [ ] Trace mode (`--trace` flag)

### Performance
- [ ] Plugin discovery caching
- [ ] Parallel plugin execution (where safe)
- [ ] Streaming optimization
- [ ] Memory profiling

### Quality
- [ ] Increase coverage to 85%+
- [ ] Add error path tests
- [ ] Add performance benchmarks
- [ ] CI/CD pipeline (GitHub Actions)

**Target:** Beta-quality framework with great UX

---

## 📋 v4.0.0-rc1 (Week +4)

**Goal:** Production hardening and ecosystem

### Stability
- [ ] Comprehensive error handling
- [ ] Input validation everywhere
- [ ] Rate limiting for HTTP
- [ ] Retry logic for network errors
- [ ] Timeout handling

### Security
- [ ] Input sanitization
- [ ] Path traversal prevention
- [ ] Command injection prevention
- [ ] Safe defaults everywhere
- [ ] Security audit

### Documentation
- [ ] Complete API documentation
- [ ] Tutorial series
- [ ] Best practices guide
- [ ] Troubleshooting guide
- [ ] FAQ

### Distribution
- [ ] PyPI package
- [ ] Docker image
- [ ] Homebrew formula
- [ ] apt/yum packages
- [ ] Windows installer

**Target:** Production-ready release candidate

---

## 📋 v4.0.0 (Week +6)

**Goal:** Public release with complete documentation

### Release Prep
- [ ] Final bug fixes
- [ ] Performance tuning
- [ ] Documentation review
- [ ] Example gallery
- [ ] Release notes

### Community
- [ ] GitHub releases
- [ ] Website launch
- [ ] Blog post
- [ ] Twitter announcement
- [ ] Hacker News post

### Support
- [ ] Issue templates
- [ ] PR templates
- [ ] Contributing guide
- [ ] Code of conduct
- [ ] Discussion forum

**Target:** Public v4.0.0 release

---

## 📋 v4.1.0 - Database & Excel (Week +10)

**Goal:** Enterprise data sources

### Database Readers
- [ ] PostgreSQL reader
- [ ] MySQL reader
- [ ] SQLite reader
- [ ] Query builder helper

### Database Writers
- [ ] PostgreSQL writer (INSERT)
- [ ] MySQL writer (INSERT)
- [ ] SQLite writer (INSERT)
- [ ] Bulk insert optimization

### Excel Support
- [ ] Excel reader (.xlsx)
- [ ] Excel writer (.xlsx)
- [ ] Sheet selection
- [ ] Formula evaluation

### Advanced Features
- [ ] Schema inference
- [ ] Type conversion
- [ ] Batch operations
- [ ] Connection pooling

**Target:** Enterprise data integration

---

## 📋 v4.2.0 - Cloud & MCP (Week +14)

**Goal:** Cloud and agent integration

### Cloud Storage
- [ ] S3 reader/writer
- [ ] Azure Blob reader/writer
- [ ] Google Cloud Storage reader/writer
- [ ] Credential management

### HTTP Advanced
- [ ] Authentication (OAuth, JWT, API keys)
- [ ] Request signing
- [ ] Rate limiting
- [ ] Retry with backoff

### MCP Integration
- [ ] MCP protocol support
- [ ] Expose plugins as MCP tools
- [ ] MCP tool discovery
- [ ] Agent SDK

### APIs
- [ ] REST API client generator
- [ ] GraphQL support
- [ ] Webhook receiver
- [ ] API documentation

**Target:** Cloud-native and agent-ready

---

## 📋 Future (v5.0+)

### Advanced Filters
- [ ] Aggregations (sum, avg, count, etc.)
- [ ] Group-by operations
- [ ] Join operations
- [ ] Window functions
- [ ] SQL-like query language

### Streaming Protocol
- [ ] Binary protocol (faster than JSON)
- [ ] Compression support
- [ ] Incremental processing
- [ ] Checkpoint/resume

### Remote Execution
- [ ] HTTP-based plugin execution
- [ ] Distributed pipelines
- [ ] Worker pools
- [ ] Load balancing

### Developer Experience
- [ ] Visual pipeline builder
- [ ] Interactive mode (REPL)
- [ ] Live reload
- [ ] Hot plugin updates
- [ ] Debugger integration

### Plugin Marketplace
- [ ] Community plugin registry
- [ ] Plugin ratings/reviews
- [ ] Automatic updates
- [ ] Dependency resolution
- [ ] Security scanning

### Enterprise Features
- [ ] Multi-tenancy
- [ ] Access control
- [ ] Audit logging
- [ ] Monitoring/metrics
- [ ] High availability

---

## Versioning Strategy

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (4.0.0 → 5.0.0): Breaking changes
- **MINOR** (4.0.0 → 4.1.0): New features, backward compatible
- **PATCH** (4.0.0 → 4.0.1): Bug fixes, backward compatible

### Stability Promise

Starting with v4.0.0:
- **Plugin API:** Stable, no breaking changes in 4.x
- **CLI:** Stable, new commands only (no removals)
- **Registry format:** Versioned, migrations provided
- **Config format:** Versioned, backward compatible

---

## Development Priorities

### Always
1. **Tests first** - Write tests before implementation
2. **Coverage >75%** - Maintain high coverage
3. **Documentation** - Update docs with code
4. **Outside-in** - Test from CLI down

### Never
1. **Breaking changes** - After v4.0.0 without major version bump
2. **Untested code** - Every feature has tests
3. **Undocumented features** - Every feature is documented
4. **Technical debt** - Clean as you go

---

## Success Metrics

### v4.0.0 (Alpha → Production)
- ✅ 78% coverage → Target: 85%
- ✅ 19 plugins → Target: 30 plugins
- ✅ 105 tests → Target: 200+ tests
- ✅ 10 commands → Target: 15 commands

### v4.1.0 (Database & Excel)
- Target: 5+ database plugins
- Target: Excel read/write
- Target: 250+ tests
- Target: 90% coverage

### v4.2.0 (Cloud & MCP)
- Target: S3/Azure/GCS support
- Target: MCP protocol integration
- Target: 300+ tests
- Target: Production deployments

### Long-term Goals
- **Downloads:** 10,000+ per month
- **Stars:** 1,000+ on GitHub
- **Contributors:** 20+ active
- **Plugins:** 100+ community plugins

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](../docs/CONTRIBUTING.md) for details.

**Priority areas for contributors:**
1. New plugins (especially databases, APIs)
2. Documentation improvements
3. Bug reports and fixes
4. Performance optimizations
5. New features from roadmap

---

## Questions?

- **Issues:** https://github.com/yourusername/jn/issues
- **Discussions:** https://github.com/yourusername/jn/discussions
- **Email:** jn-dev@example.com

**Let's build the best agent-native ETL framework together!**
