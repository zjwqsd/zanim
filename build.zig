const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const z2d_dep = b.dependency("z2d", .{
        .target = target,
        .optimize = optimize,
    });

    const core_mod = b.createModule(.{
        .root_source_file = b.path("src/core.zig"),
        .target = target,
        .optimize = optimize,
        .imports = &.{
            .{ .name = "z2d", .module = z2d_dep.module("z2d") },
        },
    });

    const lib = b.addLibrary(.{
        .name = "zanim_core",
        .linkage = .dynamic,
        .root_module = core_mod,
    });
    b.installArtifact(lib);

    const core_tests = b.addTest(.{ .root_module = core_mod });
    const run_core_tests = b.addRunArtifact(core_tests);

    // The browser/WASM boundary is deliberately renderer-independent and can
    // therefore be unit-tested on the host together with the native core.
    const web_core_mod = b.createModule(.{
        .root_source_file = b.path("src/web_core.zig"),
        .target = target,
        .optimize = optimize,
    });
    const web_core_tests = b.addTest(.{ .root_module = web_core_mod });
    const run_web_core_tests = b.addRunArtifact(web_core_tests);

    const test_step = b.step("test", "Run Zig core tests");
    test_step.dependOn(&run_core_tests.step);
    test_step.dependOn(&run_web_core_tests.step);
}
