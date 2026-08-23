const std = @import("std");
const geometry = @import("geometry.zig");
const math = @import("math.zig");

pub const Vec2 = math.Vec2;
pub const Transform2D = math.Transform2D;
pub const CubicSegment = geometry.CubicSegment;
pub const CubicPath = geometry.CubicPath;
pub const Object2D = geometry.Object2D;
pub const Style = geometry.Style;
pub const StrokeStyle = geometry.StrokeStyle;
pub const Color = geometry.Color;

pub const InterpolationError = error{
    UnsupportedGeometry,
    EmptyPath,
    TopologyMismatch,
    ScratchTooSmall,
};

const OwnedPath = struct {
    segments: []CubicSegment,
    closed: bool,
};

fn lerp(a: f64, b: f64, t: f64) f64 {
    return a + (b - a) * t;
}

fn lerpVec(a: Vec2, b: Vec2, t: f64) Vec2 {
    return .{ .x = lerp(a.x, b.x, t), .y = lerp(a.y, b.y, t) };
}

fn lerpSegment(a: CubicSegment, b: CubicSegment, t: f64) CubicSegment {
    return .{
        .p0 = lerpVec(a.p0, b.p0, t),
        .p1 = lerpVec(a.p1, b.p1, t),
        .p2 = lerpVec(a.p2, b.p2, t),
        .p3 = lerpVec(a.p3, b.p3, t),
    };
}

fn cubicLine(a: Vec2, b: Vec2) CubicSegment {
    return .{
        .p0 = a,
        .p1 = lerpVec(a, b, 1.0 / 3.0),
        .p2 = lerpVec(a, b, 2.0 / 3.0),
        .p3 = b,
    };
}

fn rectangle8(width: f64, height: f64) [8]CubicSegment {
    const hx = width * 0.5;
    const hy = height * 0.5;
    const anchors = [_]Vec2{
        .{ .x = hx, .y = 0 },
        .{ .x = hx, .y = hy },
        .{ .x = 0, .y = hy },
        .{ .x = -hx, .y = hy },
        .{ .x = -hx, .y = 0 },
        .{ .x = -hx, .y = -hy },
        .{ .x = 0, .y = -hy },
        .{ .x = hx, .y = -hy },
    };
    var out: [8]CubicSegment = undefined;
    for (0..8) |i| out[i] = cubicLine(anchors[i], anchors[(i + 1) % 8]);
    return out;
}

fn ellipse8(rx: f64, ry: f64) [8]CubicSegment {
    var out: [8]CubicSegment = undefined;
    const delta = std.math.pi / 4.0;
    const k = (4.0 / 3.0) * @tan(delta / 4.0);
    for (0..8) |i| {
        const a0 = @as(f64, @floatFromInt(i)) * delta;
        const a1 = a0 + delta;
        const p0 = Vec2{ .x = rx * @cos(a0), .y = ry * @sin(a0) };
        const p3 = Vec2{ .x = rx * @cos(a1), .y = ry * @sin(a1) };
        const t0 = Vec2{ .x = -rx * @sin(a0), .y = ry * @cos(a0) };
        const t1 = Vec2{ .x = -rx * @sin(a1), .y = ry * @cos(a1) };
        out[i] = .{
            .p0 = p0,
            .p1 = .{ .x = p0.x + k * t0.x, .y = p0.y + k * t0.y },
            .p2 = .{ .x = p3.x - k * t1.x, .y = p3.y - k * t1.y },
            .p3 = p3,
        };
    }
    return out;
}

fn splitLine8(a: Vec2, b: Vec2) [8]CubicSegment {
    var out: [8]CubicSegment = undefined;
    for (0..8) |i| {
        const t0 = @as(f64, @floatFromInt(i)) / 8.0;
        const t1 = @as(f64, @floatFromInt(i + 1)) / 8.0;
        out[i] = cubicLine(lerpVec(a, b, t0), lerpVec(a, b, t1));
    }
    return out;
}

fn cubicPoint(c: geometry.CubicBezier, t: f64) Vec2 {
    const u = 1.0 - t;
    return .{
        .x = u * u * u * c.p0.x + 3 * u * u * t * c.p1.x + 3 * u * t * t * c.p2.x + t * t * t * c.p3.x,
        .y = u * u * u * c.p0.y + 3 * u * u * t * c.p1.y + 3 * u * t * t * c.p2.y + t * t * t * c.p3.y,
    };
}

fn cubicDerivative(c: geometry.CubicBezier, t: f64) Vec2 {
    const u = 1.0 - t;
    return .{
        .x = 3 * u * u * (c.p1.x - c.p0.x) + 6 * u * t * (c.p2.x - c.p1.x) + 3 * t * t * (c.p3.x - c.p2.x),
        .y = 3 * u * u * (c.p1.y - c.p0.y) + 6 * u * t * (c.p2.y - c.p1.y) + 3 * t * t * (c.p3.y - c.p2.y),
    };
}

fn splitCubic8(c: geometry.CubicBezier) [8]CubicSegment {
    var out: [8]CubicSegment = undefined;
    const dt = 1.0 / 8.0;
    for (0..8) |i| {
        const t0 = @as(f64, @floatFromInt(i)) * dt;
        const t1 = @as(f64, @floatFromInt(i + 1)) * dt;
        const p0 = cubicPoint(c, t0);
        const p3 = cubicPoint(c, t1);
        const d0 = cubicDerivative(c, t0);
        const d1 = cubicDerivative(c, t1);
        out[i] = .{
            .p0 = p0,
            .p1 = .{ .x = p0.x + d0.x * dt / 3.0, .y = p0.y + d0.y * dt / 3.0 },
            .p2 = .{ .x = p3.x - d1.x * dt / 3.0, .y = p3.y - d1.y * dt / 3.0 },
            .p3 = p3,
        };
    }
    return out;
}

fn distance(a: Vec2, b: Vec2) f64 {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    return @sqrt(dx * dx + dy * dy);
}

fn resamplePolylineInto(points: []const Vec2, closed: bool, out: []CubicSegment) void {
    const edge_count = if (closed) points.len else points.len - 1;
    var total: f64 = 0.0;
    for (0..edge_count) |i| total += distance(points[i], points[(i + 1) % points.len]);

    if (total <= 1e-14) {
        for (out) |*segment| segment.* = cubicLine(points[0], points[0]);
        return;
    }

    const count_f = @as(f64, @floatFromInt(out.len));
    var edge_index: usize = 0;
    var walked: f64 = 0.0;
    var edge_start = points[0];
    var edge_end = points[1 % points.len];
    var edge_length = distance(edge_start, edge_end);
    var a = points[0];

    for (out, 0..) |*segment, i| {
        const target = total * @as(f64, @floatFromInt(i + 1)) / count_f;
        while (edge_index + 1 < edge_count and walked + edge_length < target - 1e-14) {
            walked += edge_length;
            edge_index += 1;
            edge_start = points[edge_index];
            edge_end = points[(edge_index + 1) % points.len];
            edge_length = distance(edge_start, edge_end);
        }
        const local = if (edge_length <= 1e-14) 0.0 else (target - walked) / edge_length;
        const b = lerpVec(edge_start, edge_end, @max(0.0, @min(1.0, local)));
        segment.* = cubicLine(a, b);
        a = b;
    }
}

fn resamplePolyline8(points: []const Vec2, closed: bool) [8]CubicSegment {
    var out: [8]CubicSegment = undefined;
    resamplePolylineInto(points, closed, &out);
    return out;
}

/// Number of cubic segments needed to preserve useful detail during a transient
/// interpolation. Ordinary primitive morphs keep the historical 8-segment
/// normalization. Polyline-to-polyline morphs use the denser endpoint so a
/// detailed path never collapses to eight coarse segments while transforming.
pub fn requiredScratchSegments(source: Object2D, target: Object2D) usize {
    return switch (source.geometry) {
        .polyline => |a| switch (target.geometry) {
            .polyline => |b| @max(a.points.len - 1, b.points.len - 1),
            else => 8,
        },
        else => 8,
    };
}

fn arc8(shape: geometry.Arc) [8]CubicSegment {
    var out: [8]CubicSegment = undefined;
    const delta = shape.sweep_angle / 8.0;
    const k = if (@abs(delta) < 1e-14) 0.0 else (4.0 / 3.0) * @tan(delta / 4.0);
    for (0..8) |i| {
        const a0 = shape.start_angle + @as(f64, @floatFromInt(i)) * delta;
        const a1 = a0 + delta;
        const p0 = Vec2{ .x = shape.radius * @cos(a0), .y = shape.radius * @sin(a0) };
        const p3 = Vec2{ .x = shape.radius * @cos(a1), .y = shape.radius * @sin(a1) };
        const t0 = Vec2{ .x = -shape.radius * @sin(a0), .y = shape.radius * @cos(a0) };
        const t1 = Vec2{ .x = -shape.radius * @sin(a1), .y = shape.radius * @cos(a1) };
        out[i] = .{
            .p0 = p0,
            .p1 = .{ .x = p0.x + k * t0.x, .y = p0.y + k * t0.y },
            .p2 = .{ .x = p3.x - k * t1.x, .y = p3.y - k * t1.y },
            .p3 = p3,
        };
    }
    return out;
}

fn regularPolygon8(shape: geometry.RegularPolygon) [8]CubicSegment {
    var out: [8]CubicSegment = undefined;
    const sides_f = @as(f64, @floatFromInt(shape.sides));
    const edge_length = 2.0 * shape.radius * @sin(std.math.pi / sides_f);
    const total = edge_length * sides_f;
    for (0..8) |i| {
        const targets = [_]f64{
            total * @as(f64, @floatFromInt(i)) / 8.0,
            total * @as(f64, @floatFromInt(i + 1)) / 8.0,
        };
        var ps: [2]Vec2 = undefined;
        for (targets, 0..) |target, j| {
            const edge_pos = target / edge_length;
            const edge_index: u32 = @intFromFloat(@floor(@min(edge_pos, sides_f - 1e-12)));
            const local = edge_pos - @as(f64, @floatFromInt(edge_index));
            const a0 = shape.phase + 2.0 * std.math.pi * @as(f64, @floatFromInt(edge_index)) / sides_f;
            const a1 = shape.phase + 2.0 * std.math.pi * @as(f64, @floatFromInt((edge_index + 1) % shape.sides)) / sides_f;
            const a = Vec2{ .x = shape.radius * @cos(a0), .y = shape.radius * @sin(a0) };
            const b = Vec2{ .x = shape.radius * @cos(a1), .y = shape.radius * @sin(a1) };
            ps[j] = lerpVec(a, b, @max(0.0, @min(1.0, local)));
        }
        out[i] = cubicLine(ps[0], ps[1]);
    }
    return out;
}

/// Normalize geometry into a caller-owned cubic scratch buffer when needed.
/// CubicPath can be borrowed directly. No heap allocation occurs.
pub fn normalizeGeometryInto(g: geometry.Geometry, scratch: []CubicSegment) InterpolationError!CubicPath {
    switch (g) {
        .square => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = rectangle8(shape.side, shape.side);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = true };
        },
        .rectangle => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = rectangle8(shape.width, shape.height);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = true };
        },
        .circle => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = ellipse8(shape.radius, shape.radius);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = true };
        },
        .ellipse => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = ellipse8(shape.radius_x, shape.radius_y);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = true };
        },
        .polygon => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = resamplePolyline8(shape.points, true);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = true };
        },
        .regular_polygon => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = regularPolygon8(shape);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = true };
        },
        .line => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = splitLine8(shape.start, shape.end);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = false };
        },
        .polyline => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = resamplePolyline8(shape.points, false);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = false };
        },
        .arc => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = arc8(shape);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = false };
        },
        .cubic_bezier => |shape| {
            if (scratch.len < 8) return error.ScratchTooSmall;
            const temp = splitCubic8(shape);
            @memcpy(scratch[0..8], &temp);
            return .{ .segments = scratch[0..8], .closed = false };
        },
        .cubic_path => |shape| {
            if (shape.segments.len == 0) return error.EmptyPath;
            return shape;
        },
    }
}

fn normalizeGeometryForPairInto(
    g: geometry.Geometry,
    segment_count: usize,
    scratch: []CubicSegment,
) InterpolationError!CubicPath {
    if (g == .polyline and segment_count != 8) {
        if (scratch.len < segment_count) return error.ScratchTooSmall;
        const shape = g.polyline;
        resamplePolylineInto(shape.points, false, scratch[0..segment_count]);
        return .{ .segments = scratch[0..segment_count], .closed = false };
    }
    return normalizeGeometryInto(g, scratch);
}

fn samplePaths(
    source_path: CubicPath,
    target_path: CubicPath,
    source_transform: Transform2D,
    target_transform: Transform2D,
    source_style: Style,
    target_style: Style,
    alpha_raw: f64,
    out: []CubicSegment,
) InterpolationError!InterpolatedObjectView {
    if (source_path.segments.len != target_path.segments.len or source_path.closed != target_path.closed) {
        return error.TopologyMismatch;
    }
    if (out.len < source_path.segments.len) return error.ScratchTooSmall;
    const t = @max(0.0, @min(1.0, alpha_raw));
    for (source_path.segments, target_path.segments, out[0..source_path.segments.len]) |a, b, *segment| {
        segment.* = lerpSegment(a, b, t);
    }
    return .{
        .geometry = .{ .segments = out[0..source_path.segments.len], .closed = source_path.closed },
        .transform = lerpTransform(source_transform, target_transform, t),
        .style = lerpStyle(source_style, target_style, t),
    };
}

/// Allocation-free interpolation between two object values. Scratch belongs to
/// the caller and may live on the stack. This has the same semantics as
/// ObjectInterpolation.sample, without owning endpoint snapshots.
pub fn sampleObjectsInto(
    source: Object2D,
    target: Object2D,
    alpha: f64,
    source_scratch: []CubicSegment,
    target_scratch: []CubicSegment,
    out_scratch: []CubicSegment,
) InterpolationError!InterpolatedObjectView {
    const segment_count = requiredScratchSegments(source, target);
    const source_path = try normalizeGeometryForPairInto(source.geometry, segment_count, source_scratch);
    const target_path = try normalizeGeometryForPairInto(target.geometry, segment_count, target_scratch);
    return samplePaths(
        source_path,
        target_path,
        source.transform,
        target.transform,
        source.style,
        target.style,
        alpha,
        out_scratch,
    );
}

fn snapshotGeometry(allocator: std.mem.Allocator, g: geometry.Geometry) !OwnedPath {
    if (g == .cubic_path) {
        const shape = g.cubic_path;
        if (shape.segments.len == 0) return error.EmptyPath;
        return .{ .segments = try allocator.dupe(CubicSegment, shape.segments), .closed = shape.closed };
    }
    var scratch: [8]CubicSegment = undefined;
    const path = try normalizeGeometryInto(g, &scratch);
    return .{ .segments = try allocator.dupe(CubicSegment, path.segments), .closed = path.closed };
}

fn lerpTransform(a: Transform2D, b: Transform2D, t: f64) Transform2D {
    return .{
        .xx = lerp(a.xx, b.xx, t),
        .xy = lerp(a.xy, b.xy, t),
        .yx = lerp(a.yx, b.yx, t),
        .yy = lerp(a.yy, b.yy, t),
        .tx = lerp(a.tx, b.tx, t),
        .ty = lerp(a.ty, b.ty, t),
    };
}

fn channel(c: u8, alpha_scale: f64) u8 {
    return @intFromFloat(@round(@as(f64, @floatFromInt(c)) * alpha_scale));
}

fn transparent(c: Color) Color {
    return .{ .r = c.r, .g = c.g, .b = c.b, .a = 0 };
}

fn lerpColor(a: Color, b: Color, t: f64) Color {
    return .{
        .r = @intFromFloat(@round(lerp(@floatFromInt(a.r), @floatFromInt(b.r), t))),
        .g = @intFromFloat(@round(lerp(@floatFromInt(a.g), @floatFromInt(b.g), t))),
        .b = @intFromFloat(@round(lerp(@floatFromInt(a.b), @floatFromInt(b.b), t))),
        .a = @intFromFloat(@round(lerp(@floatFromInt(a.a), @floatFromInt(b.a), t))),
    };
}

fn lerpOptionalColor(a: ?Color, b: ?Color, t: f64) ?Color {
    if (a == null and b == null) return null;
    if (a) |ca| {
        if (b) |cb| return lerpColor(ca, cb, t);
        return lerpColor(ca, transparent(ca), t);
    }
    const cb = b.?;
    return lerpColor(transparent(cb), cb, t);
}

fn lerpStroke(a: ?StrokeStyle, b: ?StrokeStyle, t: f64) ?StrokeStyle {
    if (a == null and b == null) return null;
    if (a) |sa| {
        if (b) |sb| return .{ .color = lerpColor(sa.color, sb.color, t), .width = lerp(sa.width, sb.width, t) };
        return .{ .color = lerpColor(sa.color, transparent(sa.color), t), .width = sa.width };
    }
    const sb = b.?;
    return .{ .color = lerpColor(transparent(sb.color), sb.color, t), .width = sb.width };
}

fn lerpStyle(a: Style, b: Style, t: f64) Style {
    return .{ .fill = lerpOptionalColor(a.fill, b.fill, t), .stroke = lerpStroke(a.stroke, b.stroke, t) };
}

/// Immutable snapshot of the object state needed by an interpolation.
/// It does not reference or own the source Object2D itself.
pub const ObjectSnapshot = struct {
    path: OwnedPath,
    transform: Transform2D,
    style: Style,
};

/// Transient frame value. `geometry.segments` borrows caller-provided scratch.
pub const InterpolatedObjectView = struct {
    geometry: CubicPath,
    transform: Transform2D,
    style: Style,

    pub fn asObject(self: InterpolatedObjectView) Object2D {
        return .{
            .geometry = .{ .cubic_path = self.geometry },
            .transform = self.transform,
            .style = self.style,
        };
    }
};

fn snapshotPolylineResampled(
    allocator: std.mem.Allocator,
    shape: geometry.Polyline,
    segment_count: usize,
) !OwnedPath {
    const segments = try allocator.alloc(CubicSegment, segment_count);
    errdefer allocator.free(segments);
    resamplePolylineInto(shape.points, false, segments);
    return .{ .segments = segments, .closed = false };
}

/// Interpolation between two distinct object snapshots.
///
/// This type never mutates either Object2D. It is deliberately unrelated to
/// Object2D's applyLinear*/applySE2* methods, which are real state changes on
/// one persistent object.
pub const ObjectInterpolation = struct {
    allocator: std.mem.Allocator,
    source: ObjectSnapshot,
    target: ObjectSnapshot,

    pub fn init(allocator: std.mem.Allocator, source_object: Object2D, target_object: Object2D) !ObjectInterpolation {
        const segment_count = requiredScratchSegments(source_object, target_object);
        const both_polylines = source_object.geometry == .polyline and target_object.geometry == .polyline;
        const source_path = if (both_polylines)
            try snapshotPolylineResampled(allocator, source_object.geometry.polyline, segment_count)
        else
            try snapshotGeometry(allocator, source_object.geometry);
        errdefer allocator.free(source_path.segments);
        const target_path = if (both_polylines)
            try snapshotPolylineResampled(allocator, target_object.geometry.polyline, segment_count)
        else
            try snapshotGeometry(allocator, target_object.geometry);
        errdefer allocator.free(target_path.segments);

        if (source_path.segments.len != target_path.segments.len or source_path.closed != target_path.closed) {
            return error.TopologyMismatch;
        }

        return .{
            .allocator = allocator,
            .source = .{ .path = source_path, .transform = source_object.transform, .style = source_object.style },
            .target = .{ .path = target_path, .transform = target_object.transform, .style = target_object.style },
        };
    }

    pub fn deinit(self: *ObjectInterpolation) void {
        self.allocator.free(self.source.path.segments);
        self.allocator.free(self.target.path.segments);
        self.* = undefined;
    }

    pub fn segmentCount(self: ObjectInterpolation) usize {
        return self.source.path.segments.len;
    }

    /// Pure random-access evaluation. Source and target objects are untouched.
    pub fn sample(self: ObjectInterpolation, alpha_raw: f64, scratch: []CubicSegment) InterpolationError!InterpolatedObjectView {
        return samplePaths(
            .{ .segments = self.source.path.segments, .closed = self.source.path.closed },
            .{ .segments = self.target.path.segments, .closed = self.target.path.closed },
            self.source.transform,
            self.target.transform,
            self.source.style,
            self.target.style,
            alpha_raw,
            scratch,
        );
    }
};

fn expectVec(expected: Vec2, actual: Vec2) !void {
    try std.testing.expectApproxEqAbs(expected.x, actual.x, 1e-12);
    try std.testing.expectApproxEqAbs(expected.y, actual.y, 1e-12);
}

test "ObjectInterpolation samples two snapshots without mutating either object" {
    var source = Object2D{
        .geometry = .{ .square = try geometry.Square.init(2.0) },
        .transform = Transform2D.identity.translate(-2, 0),
        .style = .{ .fill = .{ .r = 30, .g = 90, .b = 220 } },
    };
    const target = Object2D{
        .geometry = .{ .circle = try geometry.Circle.init(1.0) },
        .transform = Transform2D.identity.translate(3, 1),
        .style = .{ .fill = .{ .r = 230, .g = 90, .b = 70 } },
    };
    const source_before = source.transform;
    const target_before = target.transform;

    var interpolation = try ObjectInterpolation.init(std.testing.allocator, source, target);
    defer interpolation.deinit();

    var scratch: [8]CubicSegment = undefined;
    const mid = try interpolation.sample(0.5, &scratch);
    try std.testing.expectApproxEqAbs(@as(f64, 0.5), mid.transform.tx, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 0.5), mid.transform.ty, 1e-12);

    try std.testing.expectEqualDeep(source_before, source.transform);
    try std.testing.expectEqualDeep(target_before, target.transform);

    // Real transform operations still mutate the persistent source object.
    source.applyLinearLocal(math.Linear2D.scaling(2, 1));
    try std.testing.expect(!std.meta.eql(source_before, source.transform));
    // The already compiled interpolation still samples its frozen source snapshot.
    const start = try interpolation.sample(0.0, &scratch);
    try std.testing.expectEqualDeep(source_before, start.transform);
}

test "ObjectInterpolation is random-access and endpoint exact" {
    const source = Object2D{ .geometry = .{ .square = try geometry.Square.init(2.0) } };
    const target = Object2D{ .geometry = .{ .circle = try geometry.Circle.init(1.0) } };
    var interpolation = try ObjectInterpolation.init(std.testing.allocator, source, target);
    defer interpolation.deinit();

    var scratch_a: [8]CubicSegment = undefined;
    var scratch_b: [8]CubicSegment = undefined;
    const a = try interpolation.sample(0.73, &scratch_a);
    _ = try interpolation.sample(0.19, &scratch_b);
    const again = try interpolation.sample(0.73, &scratch_b);
    try expectVec(a.geometry.segments[4].p2, again.geometry.segments[4].p2);

    const start = try interpolation.sample(0.0, &scratch_a);
    const end = try interpolation.sample(1.0, &scratch_b);
    try expectVec(interpolation.source.path.segments[0].p0, start.geometry.segments[0].p0);
    try expectVec(interpolation.target.path.segments[6].p2, end.geometry.segments[6].p2);
}

test "ObjectInterpolation rejects incompatible prepared topology" {
    const line = Object2D{ .geometry = .{ .line = geometry.Line.init(.{}, .{ .x = 1 }) } };
    const square = Object2D{ .geometry = .{ .square = try geometry.Square.init(2) } };
    try std.testing.expectError(error.TopologyMismatch, ObjectInterpolation.init(std.testing.allocator, line, square));
}

test "polygon and regular polygon normalize to compatible closed paths" {
    const points = [_]Vec2{
        .{ .x = -1, .y = -1 },
        .{ .x = 1, .y = -0.8 },
        .{ .x = 0.7, .y = 1.1 },
        .{ .x = -0.6, .y = 0.9 },
    };
    var a_scratch: [8]CubicSegment = undefined;
    var b_scratch: [8]CubicSegment = undefined;
    const a = try normalizeGeometryInto(.{ .polygon = try geometry.Polygon.init(&points) }, &a_scratch);
    const b = try normalizeGeometryInto(.{ .regular_polygon = try geometry.RegularPolygon.init(5, 1.0, std.math.pi / 2.0) }, &b_scratch);
    try std.testing.expect(a.closed and b.closed);
    try std.testing.expectEqual(@as(usize, 8), a.segments.len);
    try std.testing.expectEqual(@as(usize, 8), b.segments.len);
}

test "polyline arc line and cubic normalize to compatible open paths" {
    const points = [_]Vec2{
        .{ .x = -1, .y = 0 },
        .{ .x = 0, .y = 1 },
        .{ .x = 1.0, .y = 0.0 },
    };
    var scratch: [8]CubicSegment = undefined;
    const poly = try normalizeGeometryInto(.{ .polyline = try geometry.Polyline.init(&points) }, &scratch);
    try std.testing.expect(!poly.closed);
    try std.testing.expectEqual(@as(usize, 8), poly.segments.len);
    const arc = try normalizeGeometryInto(.{ .arc = try geometry.Arc.init(1, 0, std.math.pi) }, &scratch);
    try std.testing.expectEqual(@as(usize, 8), arc.segments.len);
    const line = try normalizeGeometryInto(.{ .line = geometry.Line.init(.{}, .{ .x = 1, .y = 1 }) }, &scratch);
    try std.testing.expectEqual(@as(usize, 8), line.segments.len);
    const cubic = try normalizeGeometryInto(.{ .cubic_bezier = geometry.CubicBezier.init(.{}, .{ .x = 0.3, .y = 1.0 }, .{ .x = 0.7, .y = -1.0 }, .{ .x = 1.0, .y = 0.0 }) }, &scratch);
    try std.testing.expectEqual(@as(usize, 8), cubic.segments.len);
}

test "polyline interpolation preserves dense path detail" {
    const source_points = [_]Vec2{
        .{ .x = -1.0, .y = 0.0 },
        .{ .x = 1.0, .y = 0.0 },
    };
    var target_points: [17]Vec2 = undefined;
    for (&target_points, 0..) |*point, i| {
        const x = -1.0 + 2.0 * @as(f64, @floatFromInt(i)) / 16.0;
        point.* = .{ .x = x, .y = if (i % 2 == 0) 0.0 else 0.5 };
    }
    const source = Object2D{
        .geometry = .{ .polyline = try geometry.Polyline.init(&source_points) },
    };
    const target = Object2D{
        .geometry = .{ .polyline = try geometry.Polyline.init(&target_points) },
    };

    try std.testing.expectEqual(@as(usize, 16), requiredScratchSegments(source, target));

    var source_scratch: [16]CubicSegment = undefined;
    var target_scratch: [16]CubicSegment = undefined;
    var output_scratch: [16]CubicSegment = undefined;
    const end = try sampleObjectsInto(
        source,
        target,
        1.0,
        &source_scratch,
        &target_scratch,
        &output_scratch,
    );
    try std.testing.expectEqual(@as(usize, 16), end.geometry.segments.len);
    try expectVec(target_points[8], end.geometry.segments[7].p3);

    var compiled = try ObjectInterpolation.init(std.testing.allocator, source, target);
    defer compiled.deinit();
    try std.testing.expectEqual(@as(usize, 16), compiled.segmentCount());
}
