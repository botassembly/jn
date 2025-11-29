const std = @import("std");

// Import PCRE2 8-bit API
const pcre2 = @cImport({
    @cDefine("PCRE2_CODE_UNIT_WIDTH", "8");
    @cInclude("pcre2.h");
});

/// Compiled regex pattern
const Regex = struct {
    code: *pcre2.pcre2_code_8,
    match_data: *pcre2.pcre2_match_data_8,

    pub fn compile(pattern: []const u8) !Regex {
        var error_code: c_int = undefined;
        var error_offset: usize = undefined;

        const code = pcre2.pcre2_compile_8(
            pattern.ptr,
            pattern.len,
            0, // options
            &error_code,
            &error_offset,
            null, // context
        ) orelse return error.CompileFailed;

        const match_data = pcre2.pcre2_match_data_create_from_pattern_8(
            code,
            null, // context
        ) orelse {
            pcre2.pcre2_code_free_8(code);
            return error.MatchDataFailed;
        };

        return Regex{
            .code = code,
            .match_data = match_data,
        };
    }

    pub fn deinit(self: *Regex) void {
        pcre2.pcre2_match_data_free_8(self.match_data);
        pcre2.pcre2_code_free_8(self.code);
    }

    pub fn matches(self: *const Regex, subject: []const u8) bool {
        const rc = pcre2.pcre2_match_8(
            self.code,
            subject.ptr,
            subject.len,
            0, // start offset
            0, // options
            self.match_data,
            null, // context
        );
        return rc >= 0;
    }
};

pub fn main() !void {
    const allocator = std.heap.page_allocator;
    const args = try std.process.argsAlloc(allocator);
    defer std.process.argsFree(allocator, args);

    if (args.len < 2) {
        std.debug.print("Usage: regex-test <pattern>\n", .{});
        std.debug.print("Reads lines from stdin, prints matches\n", .{});
        std.process.exit(1);
    }

    const pattern = args[1];

    var regex = Regex.compile(pattern) catch |err| {
        std.debug.print("Failed to compile pattern '{s}': {}\n", .{ pattern, err });
        std.process.exit(1);
    };
    defer regex.deinit();

    // Read lines from stdin
    const stdin = std.io.getStdIn().reader();
    const stdout = std.io.getStdOut().writer();

    var buf: [4096]u8 = undefined;
    while (stdin.readUntilDelimiterOrEof(&buf, '\n')) |maybe_line| {
        const line = maybe_line orelse break;
        if (regex.matches(line)) {
            try stdout.print("match: {s}\n", .{line});
        } else {
            try stdout.print("no match: {s}\n", .{line});
        }
    } else |err| {
        std.debug.print("Read error: {}\n", .{err});
        std.process.exit(1);
    }
}

test "regex matches csv extension" {
    var regex = try Regex.compile(".*\\.csv$");
    defer regex.deinit();

    try std.testing.expect(regex.matches("test.csv"));
    try std.testing.expect(regex.matches("path/to/file.csv"));
    try std.testing.expect(!regex.matches("test.json"));
    try std.testing.expect(!regex.matches("test.csv.gz"));
}

test "regex matches multiple patterns" {
    var regex = try Regex.compile(".*\\.(csv|tsv)$");
    defer regex.deinit();

    try std.testing.expect(regex.matches("data.csv"));
    try std.testing.expect(regex.matches("data.tsv"));
    try std.testing.expect(!regex.matches("data.json"));
}
