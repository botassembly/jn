const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const exe = b.addExecutable(.{
        .name = "opendal-test",
        .root_source_file = b.path("main.zig"),
        .target = target,
        .optimize = optimize,
    });

    // Add OpenDAL C header path
    exe.addIncludePath(.{ .cwd_relative = "../../../vendor/opendal/bindings/c/include" });

    // Link the OpenDAL C library
    exe.addLibraryPath(.{ .cwd_relative = "../../../vendor/opendal/bindings/c/target/debug" });
    exe.linkSystemLibrary("opendal_c");

    // Link C library (needed for C interop)
    exe.linkLibC();

    b.installArtifact(exe);

    // Run step
    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());
    if (b.args) |args| {
        run_cmd.addArgs(args);
    }
    const run_step = b.step("run", "Run the OpenDAL test");
    run_step.dependOn(&run_cmd.step);
}
