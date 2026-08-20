const std = @import("std");
const z2d = @import("z2d");

const batch = @import("batch.zig");
const canvas = @import("canvas.zig");
const geometry = @import("geometry.zig");
const interpolation = @import("interpolation.zig");
const math = @import("math.zig");
const scene_wire = @import("scene_wire.zig");
const se2 = @import("se2.zig");
const vector = @import("vector.zig");

fn validSurface(width: u32, height: u32, unit_size: f64) bool {
    return width > 0 and height > 0 and
        width <= std.math.maxInt(i32) and height <= std.math.maxInt(i32) and
        std.math.isFinite(unit_size) and unit_size > 0;
}

/// Render one fully evaluated Python Scene snapshot to PNG.
export fn zanim_render_scene_frame(
    path: [*:0]const u8,
    width: u32,
    height: u32,
    unit_size: f64,
    draw_items: ?[*]const scene_wire.WireDrawItem,
    draw_item_count: u32,
    objects: ?[*]const scene_wire.WireObject,
    object_count: u32,
    batches: ?[*]const batch.WireBatch,
    batch_count: u32,
    vectors: ?[*]const vector.WireVectorObject,
    vector_count: u32,
    interpolations: ?[*]const scene_wire.WireInterpolation,
    interpolation_count: u32,
) i32 {
    if (!validSurface(width, height, unit_size)) return 2;
    if (draw_item_count > 0 and draw_items == null) return 2;
    if (object_count > 0 and objects == null) return 2;
    if (batch_count > 0 and batches == null) return 2;
    if (vector_count > 0 and vectors == null) return 2;
    if (interpolation_count > 0 and interpolations == null) return 2;

    const draw_slice = if (draw_item_count == 0) &.{} else draw_items.?[0..draw_item_count];
    const object_slice = if (object_count == 0) &.{} else objects.?[0..object_count];
    const batch_slice = if (batch_count == 0) &.{} else batches.?[0..batch_count];
    const vector_slice = if (vector_count == 0) &.{} else vectors.?[0..vector_count];
    const interpolation_slice = if (interpolation_count == 0) &.{} else interpolations.?[0..interpolation_count];

    scene_wire.renderFrame(
        std.mem.span(path),
        @intCast(width),
        @intCast(height),
        unit_size,
        draw_slice,
        object_slice,
        batch_slice,
        vector_slice,
        interpolation_slice,
    ) catch |err| {
        std.debug.print("zanim scene render error: {s}\n", .{@errorName(err)});
        return 1;
    };
    return 0;
}

/// Render one evaluated Scene snapshot into caller-owned RGB0/RGBx pixels.
export fn zanim_render_scene_rgb0(
    width: u32,
    height: u32,
    unit_size: f64,
    draw_items: ?[*]const scene_wire.WireDrawItem,
    draw_item_count: u32,
    objects: ?[*]const scene_wire.WireObject,
    object_count: u32,
    batches: ?[*]const batch.WireBatch,
    batch_count: u32,
    vectors: ?[*]const vector.WireVectorObject,
    vector_count: u32,
    interpolations: ?[*]const scene_wire.WireInterpolation,
    interpolation_count: u32,
    out_pixels: ?[*]u32,
    out_pixel_count: usize,
) i32 {
    if (!validSurface(width, height, unit_size)) return 2;
    if (draw_item_count > 0 and draw_items == null) return 2;
    if (object_count > 0 and objects == null) return 2;
    if (batch_count > 0 and batches == null) return 2;
    if (vector_count > 0 and vectors == null) return 2;
    if (interpolation_count > 0 and interpolations == null) return 2;
    if (out_pixels == null) return 2;

    const pixel_count: usize = @as(usize, width) * @as(usize, height);
    if (out_pixel_count < pixel_count) return 2;

    const draw_slice = if (draw_item_count == 0) &.{} else draw_items.?[0..draw_item_count];
    const object_slice = if (object_count == 0) &.{} else objects.?[0..object_count];
    const batch_slice = if (batch_count == 0) &.{} else batches.?[0..batch_count];
    const vector_slice = if (vector_count == 0) &.{} else vectors.?[0..vector_count];
    const interpolation_slice = if (interpolation_count == 0) &.{} else interpolations.?[0..interpolation_count];
    const rgb_ptr: [*]z2d.pixel.RGB = @ptrCast(out_pixels.?);

    scene_wire.renderRgb0(
        @intCast(width),
        @intCast(height),
        unit_size,
        draw_slice,
        object_slice,
        batch_slice,
        vector_slice,
        interpolation_slice,
        rgb_ptr[0..pixel_count],
    ) catch |err| {
        std.debug.print("zanim scene rgb0 render error: {s}\n", .{@errorName(err)});
        return 1;
    };
    return 0;
}

test {
    std.testing.refAllDecls(math);
    std.testing.refAllDecls(se2);
    std.testing.refAllDecls(geometry);
    std.testing.refAllDecls(interpolation);
    std.testing.refAllDecls(canvas);
    std.testing.refAllDecls(batch);
    std.testing.refAllDecls(vector);
    std.testing.refAllDecls(scene_wire);
}
