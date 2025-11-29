# Experiment: Zig Cross-Compilation

**Risk:** Distribution requires binaries for Linux, macOS, and Windows from single build machine.

**Goal:** Validate Zig cross-compilation works for all target platforms.

## Test Case

Build a minimal binary for all three platforms from Linux.

## Steps

```bash
cd spec/polyglot/experiments/zig-cross-compile

# Build for current platform
zig build

# Cross-compile for all platforms
./build-all.sh

# Check outputs
ls -la zig-out/
# Expected:
#   hello-linux-x86_64
#   hello-linux-aarch64
#   hello-macos-x86_64
#   hello-macos-aarch64
#   hello-windows-x86_64.exe

# Verify Linux binary works
./zig-out/hello-linux-x86_64
# Expected: Hello from Zig!

# Check binary sizes
ls -lh zig-out/
# Expected: <100KB each (static, no libc)
```

## Success Criteria

- [ ] All 5 targets build without errors
- [ ] Linux binaries run on current machine
- [ ] Binary sizes under 100KB (minimal hello world)
- [ ] No external dependencies (static linking)

## Notes

- macOS/Windows binaries can't be tested without those OSes
- Use `file` command to verify binary format
- Zig handles cross-compilation natively, no extra toolchains

## Files

- `build.zig` - Build configuration
- `src/main.zig` - Minimal hello world
- `build-all.sh` - Cross-compile script
