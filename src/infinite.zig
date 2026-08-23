const std = @import("std");
const z2d = @import("z2d");
const canvas_mod = @import("canvas.zig");
const complex_grid = @import("complex_grid.zig");
const fractal = @import("fractal.zig");
const geometry = @import("geometry.zig");
const math = @import("math.zig");
const primitives = @import("primitives.zig");

const Canvas = canvas_mod.Canvas;
const Transform2D = math.Transform2D;
const Vec2 = math.Vec2;

pub const Kind = enum(u32) {
    line = 0,
    grid = 1,
    complex_grid = 2,
    fractal = 3,
};

/// Native description of one mathematically unbounded 2D primitive.
///
/// line: p0,p1 = point; p2,p3 = direction
/// grid: p0,p1 = origin; p2,p3 = x/y spacing
///
/// `transform` is already local -> current camera/view coordinates. No finite
/// source extent is ever sent by Python.
pub const WireInfinite2D = extern struct {
    kind: u32,
    p0: f64,
    p1: f64,
    p2: f64,
    p3: f64,
    map_kind: u32,
    progress: f64,
    q0: f64,
    q1: f64,
    q2: f64,
    q3: f64,
    q4: f64,
    q5: f64,
    q6: f64,
    q7: f64,
    xx: f64,
    xy: f64,
    yx: f64,
    yy: f64,
    tx: f64,
    ty: f64,
    rgba: u32,
    rgba_secondary: u32,
    stroke_width: f64,
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

fn withOpacity(color: geometry.Color, opacity_raw: f64) geometry.Color {
    const opacity = @max(0.0, @min(1.0, opacity_raw));
    var out = color;
    out.a = @intFromFloat(@round(@as(f64, @floatFromInt(color.a)) * opacity));
    return out;
}

fn cross(a: Vec2, b: Vec2) f64 {
    return a.x * b.y - a.y * b.x;
}

fn length(v: Vec2) f64 {
    return @sqrt(v.x * v.x + v.y * v.y);
}

const Segment = struct { a: Vec2, b: Vec2 };

/// Analytically clip p + t*d, t∈R, against the current logical viewport.
fn clipInfiniteLine(canvas: Canvas, p: Vec2, d: Vec2) ?Segment {
    if (!std.math.isFinite(p.x) or !std.math.isFinite(p.y) or
        !std.math.isFinite(d.x) or !std.math.isFinite(d.y)) return null;
    if (length(d) <= 1e-14) return null;

    const half = canvas.visibleHalfExtents();
    var t0 = -std.math.inf(f64);
    var t1 = std.math.inf(f64);

    const axes = [_]struct { p: f64, d: f64, lo: f64, hi: f64 }{
        .{ .p = p.x, .d = d.x, .lo = -half.x, .hi = half.x },
        .{ .p = p.y, .d = d.y, .lo = -half.y, .hi = half.y },
    };
    for (axes) |axis| {
        if (@abs(axis.d) <= 1e-14) {
            if (axis.p < axis.lo or axis.p > axis.hi) return null;
            continue;
        }
        var a = (axis.lo - axis.p) / axis.d;
        var b = (axis.hi - axis.p) / axis.d;
        if (a > b) std.mem.swap(f64, &a, &b);
        t0 = @max(t0, a);
        t1 = @min(t1, b);
        if (t0 > t1) return null;
    }
    return .{
        .a = .{ .x = p.x + d.x * t0, .y = p.y + d.y * t0 },
        .b = .{ .x = p.x + d.x * t1, .y = p.y + d.y * t1 },
    };
}

fn drawSegment(ctx: *z2d.Context, segment: Segment, color: geometry.Color, width: f64) !void {
    if (color.a == 0 or width <= 0.0) return;
    primitives.setColor(ctx, color);
    ctx.setLineWidth(width);
    ctx.resetPath();
    try ctx.moveTo(segment.a.x, segment.a.y);
    try ctx.lineTo(segment.b.x, segment.b.y);
    try ctx.stroke();
}

fn drawInfiniteLine(
    ctx: *z2d.Context,
    canvas: Canvas,
    transform: Transform2D,
    local_point: Vec2,
    local_direction: Vec2,
    color: geometry.Color,
    width: f64,
) !void {
    const p = transform.applyPoint(local_point);
    const d = transform.applyVector(local_direction);
    if (clipInfiniteLine(canvas, p, d)) |segment| {
        try drawSegment(ctx, segment, color, width);
    }
}

const LocalBounds = struct { min: Vec2, max: Vec2 };

fn localViewportBounds(canvas: Canvas, inverse: Transform2D) LocalBounds {
    const half = canvas.visibleHalfExtents();
    const corners = [_]Vec2{
        .{ .x = -half.x, .y = -half.y },
        .{ .x = half.x, .y = -half.y },
        .{ .x = half.x, .y = half.y },
        .{ .x = -half.x, .y = half.y },
    };
    var min = inverse.applyPoint(corners[0]);
    var max = min;
    for (corners[1..]) |corner| {
        const p = inverse.applyPoint(corner);
        min.x = @min(min.x, p.x);
        min.y = @min(min.y, p.y);
        max.x = @max(max.x, p.x);
        max.y = @max(max.y, p.y);
    }
    return .{ .min = min, .max = max };
}

fn projectedFamilySpacingPx(
    canvas: Canvas,
    line_direction_view: Vec2,
    offset_per_line_view: Vec2,
) f64 {
    const direction_length = length(line_direction_view);
    if (direction_length <= 1e-14) return 0.0;
    return @abs(cross(offset_per_line_view, line_direction_view)) / direction_length * canvas.unit_size;
}

fn drawDenseCoverage(
    ctx: *z2d.Context,
    canvas: Canvas,
    base_color: geometry.Color,
    coverage_raw: f64,
) !void {
    const coverage = @max(0.0, @min(1.0, coverage_raw));
    if (coverage <= 0.0 or base_color.a == 0) return;
    var color = base_color;
    color.a = @intFromFloat(@round(@as(f64, @floatFromInt(color.a)) * coverage));
    primitives.setColor(ctx, color);
    const half = canvas.visibleHalfExtents();
    try primitives.rectangle(ctx, 2.0 * half.x, 2.0 * half.y, true, false);
}

fn rangeForGrid(min_value: f64, max_value: f64, origin: f64, step: f64) ?struct { first: i64, last: i64 } {
    if (!std.math.isFinite(min_value) or !std.math.isFinite(max_value) or
        !std.math.isFinite(origin) or !std.math.isFinite(step) or step <= 0.0) return null;
    const a = @ceil((min_value - origin) / step - 1e-10);
    const b = @floor((max_value - origin) / step + 1e-10);
    // Protect integer conversion for pathological camera transforms.
    const limit = 9.0e15;
    if (a < -limit or a > limit or b < -limit or b > limit or a > b) return null;
    return .{ .first = @intFromFloat(a), .last = @intFromFloat(b) };
}

fn drawGridFamily(
    ctx: *z2d.Context,
    canvas: Canvas,
    transform: Transform2D,
    origin: Vec2,
    step: Vec2,
    vertical: bool,
    local_bounds: LocalBounds,
    color: geometry.Color,
    width: f64,
) !void {
    const local_direction = if (vertical) Vec2{ .x = 0, .y = 1 } else Vec2{ .x = 1, .y = 0 };
    const offset = if (vertical) Vec2{ .x = step.x, .y = 0 } else Vec2{ .x = 0, .y = step.y };
    const direction_view = transform.applyVector(local_direction);
    const offset_view = transform.applyVector(offset);
    const spacing_px = projectedFamilySpacingPx(canvas, direction_view, offset_view);
    if (spacing_px <= 1e-12) return;

    const width_px = width * canvas.unit_size;
    // Once strokes overlap below pixel resolution, the exact infinite family is
    // better represented by its pixel coverage than by enumerating millions of
    // mathematically distinct but visually indistinguishable lines.
    if (width_px >= spacing_px) {
        try drawDenseCoverage(ctx, canvas, color, @min(1.0, width_px / spacing_px));
        return;
    }

    const min_value = if (vertical) local_bounds.min.x else local_bounds.min.y;
    const max_value = if (vertical) local_bounds.max.x else local_bounds.max.y;
    const grid_origin = if (vertical) origin.x else origin.y;
    const grid_step = if (vertical) step.x else step.y;
    const range = rangeForGrid(min_value, max_value, grid_origin, grid_step) orelse return;

    // Pixel-space LOD: merge subpixel-neighbor lines into a wider representative
    // line. This preserves average coverage while bounding work by viewport size.
    const target_spacing_px = 0.9;
    const stride_f = @max(1.0, @ceil(target_spacing_px / spacing_px));
    const stride: i64 = @intFromFloat(@min(stride_f, 1.0e9));
    const merged_width = width * @as(f64, @floatFromInt(stride));

    var k = range.first;
    if (stride > 1) {
        const rem = @mod(k, stride);
        if (rem != 0) k += stride - rem;
    }
    while (k <= range.last) : (k += stride) {
        const value = grid_origin + @as(f64, @floatFromInt(k)) * grid_step;
        const point = if (vertical) Vec2{ .x = value, .y = origin.y } else Vec2{ .x = origin.x, .y = value };
        try drawInfiniteLine(ctx, canvas, transform, point, local_direction, color, merged_width);
        if (range.last - k < stride) break;
    }
}

fn drawGrid(
    ctx: *z2d.Context,
    canvas: Canvas,
    transform: Transform2D,
    origin: Vec2,
    step: Vec2,
    color: geometry.Color,
    width: f64,
) !void {
    const det = transform.determinant();
    if (@abs(det) <= 1e-12) {
        // An affine rank-1 image of an infinite parallel family is one carrier
        // line. This is exact for the line geometry; a rank-0 image is a point
        // and therefore contributes no stroked line.
        const dx = transform.applyVector(.{ .x = 1, .y = 0 });
        const dy = transform.applyVector(.{ .x = 0, .y = 1 });
        const p = transform.applyPoint(origin);
        if (length(dx) > 1e-12) if (clipInfiniteLine(canvas, p, dx)) |seg| try drawSegment(ctx, seg, color, width);
        if (length(dy) > 1e-12) if (clipInfiniteLine(canvas, p, dy)) |seg| try drawSegment(ctx, seg, color, width);
        return;
    }

    const inverse = try transform.inverse();
    const bounds = localViewportBounds(canvas, inverse);
    try drawGridFamily(ctx, canvas, transform, origin, step, true, bounds, color, width);
    try drawGridFamily(ctx, canvas, transform, origin, step, false, bounds, color, width);
}

pub fn drawWireInfinite2D(ctx: *z2d.Context, canvas: Canvas, wire: WireInfinite2D) !void {
    const kind: Kind = switch (wire.kind) {
        0 => .line,
        1 => .grid,
        2 => .complex_grid,
        3 => .fractal,
        else => return error.InvalidInfiniteGeometry,
    };
    if (!std.math.isFinite(wire.stroke_width) or wire.stroke_width <= 0.0) return error.InvalidInfiniteGeometry;
    const transform = Transform2D.affine(wire.xx, wire.xy, wire.yx, wire.yy, wire.tx, wire.ty);
    const color = withOpacity(decodeColor(wire.rgba), wire.opacity);

    // Infinite geometry is resolved in view coordinates. Set the CTM once; the
    // resolver never creates large off-screen geometry or artificial endpoints.
    canvas.apply(ctx, Transform2D.identity, Transform2D.identity);
    switch (kind) {
        .line => try drawInfiniteLine(
            ctx,
            canvas,
            transform,
            .{ .x = wire.p0, .y = wire.p1 },
            .{ .x = wire.p2, .y = wire.p3 },
            color,
            wire.stroke_width,
        ),
        .grid => {
            if (wire.p2 <= 0.0 or wire.p3 <= 0.0) return error.InvalidInfiniteGeometry;
            try drawGrid(
                ctx,
                canvas,
                transform,
                .{ .x = wire.p0, .y = wire.p1 },
                .{ .x = wire.p2, .y = wire.p3 },
                color,
                wire.stroke_width,
            );
        },
        .complex_grid => {
            const secondary = withOpacity(decodeColor(wire.rgba_secondary), wire.opacity);
            try complex_grid.draw(ctx, canvas, .{
                .origin = .{ .x = wire.p0, .y = wire.p1 },
                .step = .{ .x = wire.p2, .y = wire.p3 },
                .map_kind = wire.map_kind,
                .progress = wire.progress,
                .map_params = .{ wire.q0, wire.q1, wire.q2, wire.q3, wire.q4, wire.q5, wire.q6, wire.q7 },
                .transform = transform,
                .x_color = color,
                .y_color = secondary,
                .stroke_width = wire.stroke_width,
            });
        },
        .fractal => {
            const palette_color = withOpacity(decodeColor(wire.rgba_secondary), wire.opacity);
            if (!std.math.isFinite(wire.p0) or wire.p0 < 1.0 or wire.p0 > 100000.0)
                return error.InvalidInfiniteGeometry;
            try fractal.draw(ctx, canvas, .{
                .kind = wire.map_kind,
                .max_iter = @intFromFloat(@round(wire.p0)),
                .escape_radius = wire.p1,
                .julia_re = wire.p2,
                .julia_im = wire.p3,
                .color_shift = wire.progress,
                .color_scale = wire.q0,
                .transform = transform,
                .inside_color = color,
                .palette_color = palette_color,
            });
        },
    }
}

test "infinite line clipping spans the viewport exactly" {
    const canvas = try Canvas.init(800, 600, 100);
    const segment = clipInfiniteLine(canvas, .{ .x = 0, .y = 0 }, .{ .x = 1, .y = 1 }).?;
    try std.testing.expectApproxEqAbs(@as(f64, -3), segment.a.y, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 3), segment.b.y, 1e-12);
}

test "grid range is derived from current local viewport" {
    const range = rangeForGrid(-4.1, 4.1, 0.0, 1.0).?;
    try std.testing.expectEqual(@as(i64, -4), range.first);
    try std.testing.expectEqual(@as(i64, 4), range.last);
}
