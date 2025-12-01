const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    // Library module that plugins can import
    const lib_mod = b.addModule("jn-plugin", .{
        .root_source_file = b.path("src/lib.zig"),
        .target = target,
        .optimize = optimize,
    });

    // Unit tests
    const lib_unit_tests = b.addTest(.{
        .root_source_file = b.path("src/lib.zig"),
        .target = target,
        .optimize = optimize,
    });

    const run_lib_unit_tests = b.addRunArtifact(lib_unit_tests);

    const test_step = b.step("test", "Run unit tests");
    test_step.dependOn(&run_lib_unit_tests.step);

    // Example plugin (jsonl)
    const jsonl_exe = b.addExecutable(.{
        .name = "jsonl",
        .root_source_file = b.path("examples/jsonl/main.zig"),
        .target = target,
        .optimize = optimize,
    });
    jsonl_exe.root_module.addImport("jn-plugin", lib_mod);

    b.installArtifact(jsonl_exe);

    const run_jsonl = b.addRunArtifact(jsonl_exe);
    run_jsonl.step.dependOn(b.getInstallStep());
    if (b.args) |args| {
        run_jsonl.addArgs(args);
    }

    const run_step = b.step("run-jsonl", "Run the jsonl example plugin");
    run_step.dependOn(&run_jsonl.step);
}
