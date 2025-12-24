//! JN Core Library
//!
//! Provides streaming I/O primitives and JSON handling for JN plugins and tools.
//! All components are designed for zero-allocation line-by-line processing with
//! constant memory usage regardless of input size.

pub const reader = @import("reader.zig");
pub const writer = @import("writer.zig");
pub const json = @import("json.zig");
pub const errors = @import("errors.zig");
pub const shell = @import("shell.zig");

// Re-export main functions for convenience
pub const readLine = reader.readLine;
pub const readLineOrError = reader.readLineOrError;
pub const ReadError = reader.ReadError;
pub const stripCR = reader.stripCR;
pub const handleWriteError = writer.handleWriteError;
pub const flushWriter = writer.flushWriter;
pub const exitWithError = errors.exitWithError;
pub const exitClean = errors.exitClean;
pub const ExitCode = errors.ExitCode;
pub const warn = errors.warn;

// JSON helpers
pub const parseJsonLine = json.parseJsonLine;
pub const writeJsonString = json.writeJsonString;
pub const writeJsonValue = json.writeJsonValue;
pub const writeJsonLine = json.writeJsonLine;

// Buffer size constants
pub const STDIN_BUFFER_SIZE = reader.DEFAULT_BUFFER_SIZE;
pub const STDOUT_BUFFER_SIZE = writer.DEFAULT_BUFFER_SIZE;

// Shell utilities
pub const escapeForShellSingleQuote = shell.escapeForShellSingleQuote;
pub const isSafeForShellSingleQuote = shell.isSafeForShellSingleQuote;
pub const isGlobPatternSafe = shell.isGlobPatternSafe;
pub const EscapedString = shell.EscapedString;
pub const escapeForShell = shell.escapeForShell;

test {
    @import("std").testing.refAllDecls(@This());
}
