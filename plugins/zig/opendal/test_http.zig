// OpenDAL HTTP Backend Test
// Tests streaming read from an HTTP endpoint

const std = @import("std");
const c = @cImport({
    @cInclude("opendal.h");
});

pub fn main() !void {
    std.debug.print("=== OpenDAL HTTP Test ===\n\n", .{});

    // Create HTTP operator pointing to httpbin.org
    std.debug.print("Creating HTTP operator (endpoint: https://httpbin.org)...\n", .{});

    const options = c.opendal_operator_options_new();
    defer c.opendal_operator_options_free(options);
    c.opendal_operator_options_set(options, "endpoint", "https://httpbin.org");

    const result = c.opendal_operator_new("http", options);
    if (result.@"error" != null) {
        const err = result.@"error";
        std.debug.print("Error creating HTTP operator: code={d}\n", .{err.*.code});
        if (err.*.message.len > 0) {
            std.debug.print("Message: {s}\n", .{err.*.message.data[0..err.*.message.len]});
        }
        c.opendal_error_free(err);
        return;
    }
    defer c.opendal_operator_free(result.op);

    const op = result.op;
    std.debug.print("HTTP operator created!\n\n", .{});

    // Test 1: Full read from /get endpoint
    std.debug.print("--- Test 1: Full Read /get ---\n", .{});
    const read_result = c.opendal_operator_read(op, "/get");
    if (read_result.@"error" != null) {
        const err = read_result.@"error";
        std.debug.print("Error reading /get: code={d}\n", .{err.*.code});
        if (err.*.message.len > 0) {
            std.debug.print("Message: {s}\n", .{err.*.message.data[0..err.*.message.len]});
        }
        c.opendal_error_free(err);
    } else {
        defer c.opendal_bytes_free(@constCast(&read_result.data));
        const data = read_result.data;
        std.debug.print("Received {d} bytes\n", .{data.len});
        // Print first 200 chars
        const preview_len = @min(data.len, 200);
        std.debug.print("Preview: {s}...\n\n", .{data.data[0..preview_len]});
    }

    // Test 2: Streaming read with larger response
    std.debug.print("--- Test 2: Streaming Read /bytes/1000 ---\n", .{});
    const reader_result = c.opendal_operator_reader(op, "/bytes/1000");
    if (reader_result.@"error" != null) {
        const err = reader_result.@"error";
        std.debug.print("Error creating reader: code={d}\n", .{err.*.code});
        if (err.*.message.len > 0) {
            std.debug.print("Message: {s}\n", .{err.*.message.data[0..err.*.message.len]});
        }
        c.opendal_error_free(err);
    } else {
        defer c.opendal_reader_free(reader_result.reader);
        const reader = reader_result.reader;

        var buf: [100]u8 = undefined;
        var chunk_num: usize = 0;
        var total_read: usize = 0;

        std.debug.print("Reading in 100-byte chunks:\n", .{});
        while (true) {
            const chunk_result = c.opendal_reader_read(reader, &buf, buf.len);
            if (chunk_result.@"error" != null) {
                std.debug.print("Error reading chunk\n", .{});
                c.opendal_error_free(chunk_result.@"error");
                break;
            }

            const bytes_read = chunk_result.size;
            if (bytes_read == 0) break;

            chunk_num += 1;
            total_read += bytes_read;
            std.debug.print("  Chunk {d}: {d} bytes\n", .{ chunk_num, bytes_read });
        }

        std.debug.print("\nTotal: {d} bytes in {d} chunks\n\n", .{ total_read, chunk_num });
    }

    std.debug.print("=== HTTP Test COMPLETE ===\n", .{});
}
