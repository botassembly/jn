// OpenDAL Filesystem Backend Test
// Tests streaming read of a local file

const std = @import("std");
const c = @cImport({
    @cInclude("opendal.h");
});

pub fn main() !void {
    std.debug.print("=== OpenDAL Filesystem Test ===\n\n", .{});

    // Create filesystem operator with root at /tmp
    std.debug.print("Creating filesystem operator (root: /tmp)...\n", .{});

    const options = c.opendal_operator_options_new();
    defer c.opendal_operator_options_free(options);
    c.opendal_operator_options_set(options, "root", "/tmp");

    const result = c.opendal_operator_new("fs", options);
    if (result.@"error" != null) {
        const err = result.@"error";
        std.debug.print("Error creating operator: code={d}\n", .{err.*.code});
        c.opendal_error_free(err);
        return;
    }
    defer c.opendal_operator_free(result.op);

    const op = result.op;
    std.debug.print("Filesystem operator created!\n\n", .{});

    // Write a test file
    const test_content = "Line 1: Hello from OpenDAL!\nLine 2: Streaming works!\nLine 3: JN can use this!\n";
    var bytes = c.opendal_bytes{
        .data = @constCast(@ptrCast(test_content.ptr)),
        .len = test_content.len,
        .capacity = test_content.len,
    };

    std.debug.print("Writing test file: opendal_test.txt\n", .{});
    const write_err = c.opendal_operator_write(op, "opendal_test.txt", &bytes);
    if (write_err != null) {
        std.debug.print("Error writing file\n", .{});
        c.opendal_error_free(write_err);
        return;
    }
    std.debug.print("Write successful!\n\n", .{});

    // Check file stats
    std.debug.print("Checking file stats...\n", .{});
    const stat_result = c.opendal_operator_stat(op, "opendal_test.txt");
    if (stat_result.@"error" != null) {
        std.debug.print("Error getting stats\n", .{});
        c.opendal_error_free(stat_result.@"error");
        return;
    }
    defer c.opendal_metadata_free(stat_result.meta);

    const size = c.opendal_metadata_content_length(stat_result.meta);
    const is_file = c.opendal_metadata_is_file(stat_result.meta);
    std.debug.print("  Size: {d} bytes\n", .{size});
    std.debug.print("  Is file: {}\n\n", .{is_file});

    // Streaming read
    std.debug.print("--- Streaming Read (20-byte chunks) ---\n", .{});

    const reader_result = c.opendal_operator_reader(op, "opendal_test.txt");
    if (reader_result.@"error" != null) {
        std.debug.print("Error creating reader\n", .{});
        c.opendal_error_free(reader_result.@"error");
        return;
    }
    defer c.opendal_reader_free(reader_result.reader);

    const reader = reader_result.reader;
    var buf: [20]u8 = undefined;
    var chunk_num: usize = 0;
    var total_read: usize = 0;

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

        // Show chunk with escapes for newlines
        std.debug.print("Chunk {d}: ", .{chunk_num});
        for (buf[0..bytes_read]) |byte| {
            if (byte == '\n') {
                std.debug.print("\\n", .{});
            } else {
                std.debug.print("{c}", .{byte});
            }
        }
        std.debug.print("\n", .{});
    }

    std.debug.print("\nTotal: {d} bytes in {d} chunks\n", .{ total_read, chunk_num });

    // Clean up test file
    std.debug.print("\nCleaning up test file...\n", .{});
    const del_err = c.opendal_operator_delete(op, "opendal_test.txt");
    if (del_err != null) {
        std.debug.print("Warning: could not delete test file\n", .{});
        c.opendal_error_free(del_err);
    } else {
        std.debug.print("Test file deleted.\n", .{});
    }

    std.debug.print("\n=== Filesystem Test SUCCESS ===\n", .{});
}
