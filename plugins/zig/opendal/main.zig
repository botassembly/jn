// OpenDAL Zig Binding Prototype
// Tests linking to the OpenDAL C library

const std = @import("std");
const c = @cImport({
    @cInclude("opendal.h");
});

pub fn main() !void {
    // Test 1: Create a memory-backed operator
    std.debug.print("Creating memory operator...\n", .{});

    const result = c.opendal_operator_new("memory", null);
    if (result.@"error" != null) {
        std.debug.print("Error creating operator\n", .{});
        c.opendal_error_free(result.@"error");
        return;
    }
    defer c.opendal_operator_free(result.op);

    const op = result.op;
    std.debug.print("Operator created successfully!\n", .{});

    // Test 2: Write some data
    const test_data = "Hello from JN OpenDAL prototype!";
    var bytes = c.opendal_bytes{
        .data = @constCast(@ptrCast(test_data.ptr)),
        .len = test_data.len,
        .capacity = test_data.len,
    };

    std.debug.print("Writing data to /test.txt...\n", .{});
    const write_err = c.opendal_operator_write(op, "/test.txt", &bytes);
    if (write_err != null) {
        std.debug.print("Error writing data\n", .{});
        c.opendal_error_free(write_err);
        return;
    }
    std.debug.print("Write successful!\n", .{});

    // Test 3: Read the data back (full read)
    std.debug.print("Reading data back...\n", .{});
    const read_result = c.opendal_operator_read(op, "/test.txt");
    if (read_result.@"error" != null) {
        std.debug.print("Error reading data\n", .{});
        c.opendal_error_free(read_result.@"error");
        return;
    }
    defer c.opendal_bytes_free(@constCast(&read_result.data));

    const read_data = read_result.data;
    std.debug.print("Read {d} bytes: {s}\n", .{ read_data.len, read_data.data[0..read_data.len] });

    // Test 4: Streaming read (most important for JN!)
    std.debug.print("\n--- Testing Streaming API ---\n", .{});

    const reader_result = c.opendal_operator_reader(op, "/test.txt");
    if (reader_result.@"error" != null) {
        std.debug.print("Error creating reader\n", .{});
        c.opendal_error_free(reader_result.@"error");
        return;
    }
    defer c.opendal_reader_free(reader_result.reader);

    const reader = reader_result.reader;
    std.debug.print("Streaming reader created!\n", .{});

    // Read in chunks (simulating streaming)
    var buf: [10]u8 = undefined;
    var total_read: usize = 0;

    std.debug.print("Reading in 10-byte chunks:\n", .{});
    while (true) {
        const chunk_result = c.opendal_reader_read(reader, &buf, buf.len);
        if (chunk_result.@"error" != null) {
            std.debug.print("Error in streaming read\n", .{});
            c.opendal_error_free(chunk_result.@"error");
            break;
        }

        const bytes_read = chunk_result.size;
        if (bytes_read == 0) {
            break; // EOF
        }

        total_read += bytes_read;
        std.debug.print("  Chunk: '{s}'\n", .{buf[0..bytes_read]});
    }

    std.debug.print("Total streamed: {d} bytes\n", .{total_read});
    std.debug.print("\n=== OpenDAL prototype SUCCESS ===\n", .{});
}
