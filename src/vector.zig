const std = @import("std");
const z2d = @import("z2d");
const canvas_mod = @import("canvas.zig");
const geometry = @import("geometry.zig");
const math = @import("math.zig");
const primitives = @import("primitives.zig");

const Canvas = canvas_mod.Canvas;
const Transform2D = math.Transform2D;
const Vec2 = math.Vec2;

/// One cubic vector path. `segments` stores 8 f64 per segment:
/// p0.x,p0.y,p1.x,p1.y,p2.x,p2.y,p3.x,p3.y.
/// `contour_ends` stores cumulative segment counts for each contour.
pub const WireVectorPath = extern struct {
    segment_count: u32,
    segments: ?[*]const f64,
    contour_count: u32,
    contour_ends: ?[*]const u32,
    contour_closed: ?[*]const u8,
    fill_present: u32,
    fill_rgba: u32,
    stroke_present: u32,
    stroke_rgba: u32,
    stroke_width: f64,
    group: u32,
};

pub const WireVectorObject = extern struct {
    path_count: u32,
    paths: ?[*]const WireVectorPath,
    group_count: u32,
    reveal: f64,
    xx: f64,
    xy: f64,
    yx: f64,
    yy: f64,
    tx: f64,
    ty: f64,
    opacity: f64,
};

fn decodeColor(rgba: u32) geometry.Color {
    return .{
        .r = @intCast((rgba >> 24) & 0xff),
        .g = @intCast((rgba >> 16) & 0xff),
        .b = @intCast((rgba >> 8) & 0xff),
        .a = @intCast(rgba & 0xff),
    };
}

fn scaledAlpha(color: geometry.Color, scale_raw: f64) geometry.Color {
    const scale = @max(0.0, @min(1.0, scale_raw));
    return .{
        .r = color.r,
        .g = color.g,
        .b = color.b,
        .a = @intFromFloat(@round(@as(f64, @floatFromInt(color.a)) * scale)),
    };
}

fn groupAlpha(reveal_raw: f64, group_count: u32, group: u32) f64 {
    if (group_count == 0) return 1.0;
    const reveal = @max(0.0, @min(1.0, reveal_raw));
    const position = reveal * @as(f64, @floatFromInt(group_count)) - @as(f64, @floatFromInt(group));
    return @max(0.0, @min(1.0, position));
}

fn point(raw: [*]const f64, base: usize) Vec2 {
    return .{ .x = raw[base], .y = raw[base + 1] };
}

fn transformed(t: Transform2D, p: Vec2) Vec2 {
    return t.applyPoint(p);
}

fn drawPath(
    ctx: *z2d.Context,
    wire: WireVectorPath,
    transform: Transform2D,
    alpha: f64,
) !void {
    if (alpha <= 0.0) return;
    if (wire.segment_count == 0 or wire.contour_count == 0) return;
    if (wire.segments == null or wire.contour_ends == null or wire.contour_closed == null)
        return error.InvalidVector;

    const raw = wire.segments.?;
    const ends = wire.contour_ends.?;
    const closed = wire.contour_closed.?;

    ctx.resetPath();
    var segment_start: usize = 0;
    for (0..wire.contour_count) |ci| {
        const segment_end: usize = ends[ci];
        if (segment_end <= segment_start or segment_end > wire.segment_count)
            return error.InvalidVector;

        const first_base = segment_start * 8;
        const p0 = transformed(transform, point(raw, first_base));
        try ctx.moveTo(p0.x, p0.y);

        var si = segment_start;
        while (si < segment_end) : (si += 1) {
            const base = si * 8;
            const p1 = transformed(transform, point(raw, base + 2));
            const p2 = transformed(transform, point(raw, base + 4));
            const p3 = transformed(transform, point(raw, base + 6));
            try ctx.curveTo(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
        }
        if (closed[ci] != 0) try ctx.closePath();
        segment_start = segment_end;
    }
    if (segment_start != wire.segment_count) return error.InvalidVector;

    if (wire.fill_present != 0) {
        primitives.setColor(ctx, scaledAlpha(decodeColor(wire.fill_rgba), alpha));
        try ctx.fill();
    }
    if (wire.stroke_present != 0 and wire.stroke_width > 0.0) {
        primitives.setColor(ctx, scaledAlpha(decodeColor(wire.stroke_rgba), alpha));
        ctx.setLineWidth(wire.stroke_width);
        try ctx.stroke();
    }
}

pub fn drawWireVector(ctx: *z2d.Context, canvas: Canvas, wire: WireVectorObject) !void {
    if (wire.path_count == 0) return;
    if (wire.paths == null) return error.InvalidVector;

    // As with Object2D, keep the object transform out of z2d's CTM so affine
    // singular transforms remain valid. Canvas is the only stable CTM here.
    canvas.apply(ctx, Transform2D.identity, Transform2D.identity);
    const transform = Transform2D.affine(wire.xx, wire.xy, wire.yx, wire.yy, wire.tx, wire.ty);
    const paths = wire.paths.?;
    for (0..wire.path_count) |i| {
        const path = paths[i];
        const alpha = groupAlpha(wire.reveal, wire.group_count, path.group) * @max(0.0, @min(1.0, wire.opacity));
        try drawPath(ctx, path, transform, alpha);
    }
}

test "reveal group alpha walks groups in order" {
    try std.testing.expectApproxEqAbs(@as(f64, 0.0), groupAlpha(0.0, 4, 0), 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 1.0), groupAlpha(0.25, 4, 0), 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 0.0), groupAlpha(0.25, 4, 1), 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 0.5), groupAlpha(0.625, 4, 2), 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 1.0), groupAlpha(1.0, 4, 3), 1e-12);
}
