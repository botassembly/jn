#!/bin/bash
set -e

echo "Building for all platforms..."

mkdir -p zig-out

# Linux x86_64
echo "→ Linux x86_64"
zig build -Dtarget=x86_64-linux -Doptimize=ReleaseSmall
cp zig-out/bin/hello zig-out/hello-linux-x86_64

# Linux aarch64 (ARM64)
echo "→ Linux aarch64"
zig build -Dtarget=aarch64-linux -Doptimize=ReleaseSmall
cp zig-out/bin/hello zig-out/hello-linux-aarch64

# macOS x86_64
echo "→ macOS x86_64"
zig build -Dtarget=x86_64-macos -Doptimize=ReleaseSmall
cp zig-out/bin/hello zig-out/hello-macos-x86_64

# macOS aarch64 (Apple Silicon)
echo "→ macOS aarch64"
zig build -Dtarget=aarch64-macos -Doptimize=ReleaseSmall
cp zig-out/bin/hello zig-out/hello-macos-aarch64

# Windows x86_64
echo "→ Windows x86_64"
zig build -Dtarget=x86_64-windows -Doptimize=ReleaseSmall
cp zig-out/bin/hello.exe zig-out/hello-windows-x86_64.exe

echo ""
echo "Built artifacts:"
ls -lh zig-out/hello-*

echo ""
echo "Verifying formats:"
file zig-out/hello-*
