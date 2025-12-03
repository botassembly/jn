//! JN CLI Library
//!
//! Provides argument parsing utilities for JN plugins and tools.
//! Simple, zero-allocation argument parsing using the same patterns
//! as existing JN plugins.

pub const args = @import("args.zig");

// Re-export main types and functions
pub const ArgParser = args.ArgParser;
pub const parseArgs = args.parseArgs;
pub const getArg = args.getArg;
pub const hasFlag = args.hasFlag;

test {
    @import("std").testing.refAllDecls(@This());
}
