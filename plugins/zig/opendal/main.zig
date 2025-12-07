const std = @import("std");
const jn_core = @import("jn-core");
const jn_cli = @import("jn-cli");
const jn_plugin = @import("jn-plugin");

// TODO: Replace with native OpenDAL Zig bindings when they mature
// See: https://github.com/apache/opendal/tree/main/bindings/zig
// Currently using C bindings for stability (Zig bindings are WIP/0.0.0)
const c = @cImport({
    @cInclude("opendal.h");
});

const plugin_meta = jn_plugin.PluginMeta{
    .name = "opendal",
    .version = "0.4.0",
    .matches = &.{
        "^https?://.*",
        "^file://.*",
        "^s3://.*",
        "^gs://.*",
        "^gcs://.*",
        "^gdrive://.*",
    },
    .role = .protocol,
    .modes = &.{.raw},
    .supports_raw = true,
};

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const args = jn_cli.parseArgs();
    if (args.has("jn-meta")) {
        try jn_plugin.outputManifestToStdout(plugin_meta);
        return;
    }

    // Allow --url=value or first positional argument
    const url_arg = args.get("url", null) orelse findPositionalUrl() orelse
        jn_core.exitWithError("opendal: missing URL (pass --url=<address> or positional)", .{});

    const uri = std.Uri.parse(url_arg) catch
        jn_core.exitWithError("opendal: invalid URL '{s}'", .{url_arg});

    streamUrl(allocator, uri, args);
}

fn findPositionalUrl() ?[]const u8 {
    var iter = std.process.args();
    _ = iter.skip(); // skip program name
    while (iter.next()) |arg| {
        if (!std.mem.startsWith(u8, arg, "--")) {
            return arg;
        }
    }
    return null;
}

fn streamUrl(allocator: std.mem.Allocator, uri: std.Uri, args: jn_cli.ArgParser) void {
    const scheme = uri.scheme;
    const service: [:0]const u8 = if (std.mem.eql(u8, scheme, "http") or std.mem.eql(u8, scheme, "https"))
        "http"
    else if (std.mem.eql(u8, scheme, "file"))
        "fs"
    else if (std.mem.eql(u8, scheme, "s3"))
        "s3"
    else if (std.mem.eql(u8, scheme, "gs") or std.mem.eql(u8, scheme, "gcs"))
        "gcs"
    else
        jn_core.exitWithError("opendal: unsupported scheme '{s}'", .{scheme});

    const options = c.opendal_operator_options_new();
    defer c.opendal_operator_options_free(options);

    const endpoint = buildEndpointZ(allocator, uri) catch
        jn_core.exitWithError("opendal: failed to build endpoint", .{});
    defer allocator.free(endpoint);

    const path = buildObjectPathZ(allocator, uri) catch
        jn_core.exitWithError("opendal: failed to build path", .{});
    defer allocator.free(path);
    var object_path: [:0]const u8 = path;

    if (std.mem.eql(u8, service, "http")) {
        c.opendal_operator_options_set(options, "endpoint", endpoint);
        applyDefaultHeaders(allocator, options, args) catch {};
    } else if (std.mem.eql(u8, service, "fs")) {
        const trimmed = trimLeadingSlash(path);
        c.opendal_operator_options_set(options, "root", "/");
        object_path = trimmed;
    } else if (std.mem.eql(u8, service, "s3")) {
        const bucket_comp = uri.host orelse jn_core.exitWithError("opendal: missing bucket in s3 URL", .{});
        const bucket = componentToRawAlloc(allocator, bucket_comp) catch
            jn_core.exitWithError("opendal: failed to parse bucket", .{});
        c.opendal_operator_options_set(options, "bucket", toZ(allocator, bucket) catch
            jn_core.exitWithError("opendal: alloc bucket", .{}));
        c.opendal_operator_options_set(options, "region", getenvOrFallback(allocator, "AWS_REGION", "us-east-1") catch
            jn_core.exitWithError("opendal: alloc region", .{}));
        if (std.process.getEnvVarOwned(allocator, "AWS_ENDPOINT_URL")) |endpoint_url| {
            defer allocator.free(endpoint_url);
            c.opendal_operator_options_set(options, "endpoint", toZ(allocator, endpoint_url) catch
                jn_core.exitWithError("opendal: alloc endpoint", .{}));
        } else |_| {}
        if (std.process.getEnvVarOwned(allocator, "AWS_ACCESS_KEY_ID")) |ak| {
            defer allocator.free(ak);
            c.opendal_operator_options_set(options, "access_key_id", toZ(allocator, ak) catch
                jn_core.exitWithError("opendal: alloc access_key", .{}));
        } else |_| {}
        if (std.process.getEnvVarOwned(allocator, "AWS_SECRET_ACCESS_KEY")) |sk| {
            defer allocator.free(sk);
            c.opendal_operator_options_set(options, "secret_access_key", toZ(allocator, sk) catch
                jn_core.exitWithError("opendal: alloc secret_key", .{}));
        } else |_| {}
        object_path = trimLeadingSlash(path);
    } else if (std.mem.eql(u8, service, "gcs")) {
        const bucket_comp = uri.host orelse jn_core.exitWithError("opendal: missing bucket in gcs URL", .{});
        const bucket = componentToRawAlloc(allocator, bucket_comp) catch
            jn_core.exitWithError("opendal: failed to parse bucket", .{});
        c.opendal_operator_options_set(options, "bucket", toZ(allocator, bucket) catch
            jn_core.exitWithError("opendal: alloc bucket", .{}));
        if (std.process.getEnvVarOwned(allocator, "GOOGLE_APPLICATION_CREDENTIALS")) |cred_path| {
            defer allocator.free(cred_path);
            c.opendal_operator_options_set(options, "credential_path", toZ(allocator, cred_path) catch
                jn_core.exitWithError("opendal: alloc credential path", .{}));
        } else |_| {}
        object_path = trimLeadingSlash(path);
    }

    const op_res = c.opendal_operator_new(service.ptr, options);
    if (op_res.@"error" != null) {
        reportErrorAndExit("opendal: operator error", op_res.@"error");
    }
    defer c.opendal_operator_free(op_res.op);

    const reader_res = c.opendal_operator_reader(op_res.op, object_path.ptr);
    if (reader_res.@"error" != null) {
        reportErrorAndExit("opendal: reader error", reader_res.@"error");
    }
    defer c.opendal_reader_free(reader_res.reader);

    var buf: [jn_core.STDOUT_BUFFER_SIZE]u8 = undefined;
    const stdout = std.fs.File.stdout();

    while (true) {
        const chunk = c.opendal_reader_read(reader_res.reader, &buf, buf.len);
        if (chunk.@"error" != null) {
            reportErrorAndExit("opendal: read error", chunk.@"error");
        }
        if (chunk.size == 0) break;
        _ = stdout.write(buf[0..chunk.size]) catch |err| jn_core.handleWriteError(err);
    }
}

fn buildEndpointZ(allocator: std.mem.Allocator, uri: std.Uri) ![:0]u8 {
    // For http(s): scheme://host[:port]
    if (uri.host) |host_comp| {
        const host = try componentToRawAlloc(allocator, host_comp);
        if (uri.port) |port| {
            return try toZ(allocator, try std.fmt.allocPrint(allocator, "{s}://{s}:{d}", .{ uri.scheme, host, port }));
        }
        return try toZ(allocator, try std.fmt.allocPrint(allocator, "{s}://{s}", .{ uri.scheme, host }));
    }
    // For file: endpoint unused; return empty string
    return try toZ(allocator, try std.fmt.allocPrint(allocator, "", .{}));
}

fn buildObjectPathZ(allocator: std.mem.Allocator, uri: std.Uri) ![:0]u8 {
    const path_part = try componentToRawAlloc(allocator, uri.path);
    if (uri.query) |q_comp| {
        const query = try componentToRawAlloc(allocator, q_comp);
        return try toZ(allocator, try std.fmt.allocPrint(allocator, "{s}?{s}", .{ path_part, query }));
    }
    return try toZ(allocator, try std.fmt.allocPrint(allocator, "{s}", .{path_part}));
}

fn toZ(allocator: std.mem.Allocator, bytes: []const u8) ![:0]u8 {
    return try std.mem.concatWithSentinel(allocator, u8, &.{bytes}, 0);
}

fn componentToRawAlloc(allocator: std.mem.Allocator, comp: std.Uri.Component) ![]const u8 {
    return try comp.toRawMaybeAlloc(allocator);
}

fn trimLeadingSlash(path: [:0]const u8) [:0]const u8 {
    if (path.len > 0 and path[0] == '/') {
        return path[1..];
    }
    return path;
}

fn getenvOrFallback(allocator: std.mem.Allocator, key: []const u8, fallback: []const u8) ![:0]u8 {
    if (std.process.getEnvVarOwned(allocator, key)) |val| {
        return toZ(allocator, val);
    } else |_| {
        return toZ(allocator, fallback);
    }
}

fn applyDefaultHeaders(allocator: std.mem.Allocator, options: [*c]c.struct_opendal_operator_options, args: jn_cli.ArgParser) !void {
    if (args.get("headers", null)) |raw| {
        // Expect JSON object from CLI
        // NOTE: Strings passed to opendal_operator_options_set must outlive the
        // operator, so we intentionally don't free them (they live until process exit).
        const parsed = std.json.parseFromSlice(std.json.Value, allocator, raw, .{}) catch return;
        // Don't defer deinit - the parsed strings need to stay alive
        if (parsed.value != .object) return;
        var iter = parsed.value.object.iterator();
        while (iter.next()) |entry| {
            const key = try std.fmt.allocPrint(allocator, "default_headers.{s}", .{entry.key_ptr.*});
            const key_z = try toZ(allocator, key);
            switch (entry.value_ptr.*) {
                .string => |v| {
                    const val_z = try toZ(allocator, v);
                    c.opendal_operator_options_set(options, key_z, val_z);
                },
                else => {},
            }
        }
    }
}

fn reportErrorAndExit(prefix: []const u8, err: *c.struct_opendal_error) noreturn {
    const msg = err.message;
    const msg_slice = msg.data[0..msg.len];
    std.debug.print("{s}: code={d} msg={s}\n", .{ prefix, err.code, msg_slice });
    c.opendal_error_free(err);
    std.process.exit(1);
}
