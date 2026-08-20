const std = @import("std");
const z2d = @import("z2d");
const math = @import("math.zig");
const se2 = @import("se2.zig");
const canvas_mod = @import("canvas.zig");
const p = @import("primitives.zig");

pub const Vec2 = math.Vec2;
pub const Linear2D = math.Linear2D;
pub const Transform2D = math.Transform2D;
pub const SE2 = se2.SE2;
pub const Canvas = canvas_mod.Canvas;
pub const Color = p.Color;

pub const GeometryError = error{
    InvalidSize,
    InvalidRadius,
    TooFewPoints,
    TooFewSides,
};

pub const StrokeStyle = struct {
    color: Color = .{ .r = 230, .g = 232, .b = 238 },
    width: f64 = 0.035,
};

pub const Style = struct {
    fill: ?Color = null,
    stroke: ?StrokeStyle = .{},
};

pub const Line = struct {
    start: Vec2,
    end: Vec2,

    pub fn init(start: Vec2, end: Vec2) Line {
        return .{ .start = start, .end = end };
    }
};

/// Borrowed point storage; the caller owns the slice for the Object2D lifetime.
pub const Polyline = struct {
    points: []const Vec2,

    pub fn init(points: []const Vec2) GeometryError!Polyline {
        if (points.len < 2) return error.TooFewPoints;
        return .{ .points = points };
    }
};

/// Borrowed point storage; the caller owns the slice for the Object2D lifetime.
pub const Polygon = struct {
    points: []const Vec2,

    pub fn init(points: []const Vec2) GeometryError!Polygon {
        if (points.len < 3) return error.TooFewPoints;
        return .{ .points = points };
    }
};

pub const Rectangle = struct {
    width: f64,
    height: f64,

    pub fn init(width: f64, height: f64) GeometryError!Rectangle {
        if (!(width > 0) or !(height > 0)) return error.InvalidSize;
        return .{ .width = width, .height = height };
    }
};

pub const Square = struct {
    side: f64,

    pub fn init(side: f64) GeometryError!Square {
        if (!(side > 0)) return error.InvalidSize;
        return .{ .side = side };
    }
};

pub const Circle = struct {
    radius: f64,

    pub fn init(radius: f64) GeometryError!Circle {
        if (!(radius > 0)) return error.InvalidRadius;
        return .{ .radius = radius };
    }
};

pub const Ellipse = struct {
    radius_x: f64,
    radius_y: f64,

    pub fn init(radius_x: f64, radius_y: f64) GeometryError!Ellipse {
        if (!(radius_x > 0) or !(radius_y > 0)) return error.InvalidRadius;
        return .{ .radius_x = radius_x, .radius_y = radius_y };
    }
};

pub const Arc = struct {
    radius: f64,
    start_angle: f64,
    sweep_angle: f64,

    pub fn init(radius: f64, start_angle: f64, sweep_angle: f64) GeometryError!Arc {
        if (!(radius > 0)) return error.InvalidRadius;
        return .{ .radius = radius, .start_angle = start_angle, .sweep_angle = sweep_angle };
    }
};

pub const RegularPolygon = struct {
    sides: u32,
    radius: f64,
    phase: f64 = std.math.pi / 2.0,

    pub fn init(sides: u32, radius: f64, phase: f64) GeometryError!RegularPolygon {
        if (sides < 3) return error.TooFewSides;
        if (!(radius > 0)) return error.InvalidRadius;
        return .{ .sides = sides, .radius = radius, .phase = phase };
    }
};

pub const CubicBezier = struct {
    p0: Vec2,
    p1: Vec2,
    p2: Vec2,
    p3: Vec2,

    pub fn init(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2) CubicBezier {
        return .{ .p0 = p0, .p1 = p1, .p2 = p2, .p3 = p3 };
    }
};

pub const CubicSegment = struct {
    p0: Vec2,
    p1: Vec2,
    p2: Vec2,
    p3: Vec2,
};

/// Borrowed cubic contour storage. Morph sampling can expose a transient
/// scratch buffer through this view without allocating or mutating Object2D.
pub const CubicPath = struct {
    segments: []const CubicSegment,
    closed: bool = true,

    pub fn init(segments: []const CubicSegment, closed: bool) GeometryError!CubicPath {
        if (segments.len == 0) return error.TooFewPoints;
        return .{ .segments = segments, .closed = closed };
    }
};

pub const Geometry = union(enum) {
    line: Line,
    polyline: Polyline,
    polygon: Polygon,
    rectangle: Rectangle,
    square: Square,
    circle: Circle,
    ellipse: Ellipse,
    arc: Arc,
    regular_polygon: RegularPolygon,
    cubic_bezier: CubicBezier,
    cubic_path: CubicPath,
};

/// A drawable 2D object. Geometry is defined in immutable local coordinates.
/// `transform` is the accumulated affine map from those local coordinates to
/// world coordinates.
///
/// Linear maps can be composed in either frame:
///   local: T <- T * L
///   world: T <- L * T
///
/// SE(2) is layered on top with the exact same left/right multiplication rule.
pub const Object2D = struct {
    geometry: Geometry,
    transform: Transform2D = .identity,
    style: Style = .{},

    pub fn init(geometry: Geometry) Object2D {
        return .{ .geometry = geometry };
    }

    /// Apply a pure linear map in the object's local coordinate frame.
    /// The object's current world origin is unchanged.
    pub fn applyLinearLocal(self: *Object2D, linear: Linear2D) void {
        self.transform = self.transform.mul(linear.toTransform2D());
    }

    /// Apply a pure linear map in the world coordinate frame, about the world origin.
    /// Existing object translation is transformed as well.
    pub fn applyLinearWorld(self: *Object2D, linear: Linear2D) void {
        self.transform = linear.toTransform2D().mul(self.transform);
    }

    /// Apply an SE(2) rigid transform in the object's local frame.
    pub fn applySE2Local(self: *Object2D, rigid: SE2) void {
        self.transform = self.transform.mul(rigid.toTransform2D());
    }

    /// Apply an SE(2) rigid transform in the world frame.
    pub fn applySE2World(self: *Object2D, rigid: SE2) void {
        self.transform = rigid.toTransform2D().mul(self.transform);
    }

    pub fn localToWorld(self: Object2D, point: Vec2) Vec2 {
        return self.transform.applyPoint(point);
    }

    pub fn draw(self: Object2D, ctx: *z2d.Context, canvas: Canvas, view: Transform2D) !void {
        // Keep object transforms out of z2d's CTM. z2d requires an invertible
        // CTM for stroking, while a legitimate linear-algebra animation may
        // use singular maps (det = 0). Apply the object transform pointwise.
        canvas.apply(ctx, view, Transform2D.identity);
        try drawGeometryTransformed(ctx, self.geometry, self.style, self.transform);
    }
};

fn applyStyle(ctx: *z2d.Context, style: Style) void {
    if (style.stroke) |stroke| ctx.setLineWidth(stroke.width);
}

fn finishPath(ctx: *z2d.Context, style: Style) !void {
    if (style.fill) |fill_color| {
        p.setColor(ctx, fill_color);
        try ctx.fill();
    }
    if (style.stroke) |stroke| {
        p.setColor(ctx, stroke.color);
        ctx.setLineWidth(stroke.width);
        try ctx.stroke();
    }
}

fn drawOpenPath(ctx: *z2d.Context, style: Style) !void {
    if (style.stroke) |stroke| {
        p.setColor(ctx, stroke.color);
        ctx.setLineWidth(stroke.width);
        try ctx.stroke();
    }
}

fn transformed(t: Transform2D, point: Vec2) Vec2 {
    return t.applyPoint(point);
}

fn moveToTransformed(ctx: *z2d.Context, t: Transform2D, point: Vec2) !void {
    const q = transformed(t, point);
    try ctx.moveTo(q.x, q.y);
}

fn lineToTransformed(ctx: *z2d.Context, t: Transform2D, point: Vec2) !void {
    const q = transformed(t, point);
    try ctx.lineTo(q.x, q.y);
}

fn curveToTransformed(ctx: *z2d.Context, t: Transform2D, p1: Vec2, p2: Vec2, p3: Vec2) !void {
    const q1 = transformed(t, p1);
    const q2 = transformed(t, p2);
    const q3 = transformed(t, p3);
    try ctx.curveTo(q1.x, q1.y, q2.x, q2.y, q3.x, q3.y);
}

fn beginPolygonTransformed(ctx: *z2d.Context, points: []const Vec2, t: Transform2D) !void {
    ctx.resetPath();
    try moveToTransformed(ctx, t, points[0]);
    for (points[1..]) |point| try lineToTransformed(ctx, t, point);
    try ctx.closePath();
}

fn drawRectanglePathTransformed(ctx: *z2d.Context, width: f64, height: f64, t: Transform2D) !void {
    const hx = width * 0.5;
    const hy = height * 0.5;
    const points = [_]Vec2{
        .{ .x = -hx, .y = -hy },
        .{ .x = hx, .y = -hy },
        .{ .x = hx, .y = hy },
        .{ .x = -hx, .y = hy },
    };
    try beginPolygonTransformed(ctx, &points, t);
}

fn drawEllipsePathTransformed(ctx: *z2d.Context, rx: f64, ry: f64, t: Transform2D) !void {
    // Four cubic Beziers. Transforming their control points pointwise supports
    // all affine maps, including singular maps that collapse the ellipse.
    const k = 0.5522847498307936;
    ctx.resetPath();
    try moveToTransformed(ctx, t, .{ .x = rx, .y = 0 });
    try curveToTransformed(ctx, t, .{ .x = rx, .y = k * ry }, .{ .x = k * rx, .y = ry }, .{ .x = 0, .y = ry });
    try curveToTransformed(ctx, t, .{ .x = -k * rx, .y = ry }, .{ .x = -rx, .y = k * ry }, .{ .x = -rx, .y = 0 });
    try curveToTransformed(ctx, t, .{ .x = -rx, .y = -k * ry }, .{ .x = -k * rx, .y = -ry }, .{ .x = 0, .y = -ry });
    try curveToTransformed(ctx, t, .{ .x = k * rx, .y = -ry }, .{ .x = rx, .y = -k * ry }, .{ .x = rx, .y = 0 });
    try ctx.closePath();
}

fn drawArcPathTransformed(ctx: *z2d.Context, shape: Arc, t: Transform2D) !void {
    ctx.resetPath();
    if (@abs(shape.sweep_angle) < 1e-15) return;

    // Split into <= 90-degree cubic segments. Affine maps preserve cubic
    // Beziers, so pointwise transformation works for shear, reflection and
    // singular collapse without relying on z2d's invertible CTM.
    const segments_f = @ceil(@abs(shape.sweep_angle) / (std.math.pi / 2.0));
    const segments: usize = @max(1, @as(usize, @intFromFloat(segments_f)));
    const delta = shape.sweep_angle / @as(f64, @floatFromInt(segments));

    var a0 = shape.start_angle;
    const start = Vec2{ .x = shape.radius * @cos(a0), .y = shape.radius * @sin(a0) };
    try moveToTransformed(ctx, t, start);

    for (0..segments) |_| {
        const a1 = a0 + delta;
        const k = (4.0 / 3.0) * @tan(delta / 4.0);
        const p0 = Vec2{ .x = shape.radius * @cos(a0), .y = shape.radius * @sin(a0) };
        const p3 = Vec2{ .x = shape.radius * @cos(a1), .y = shape.radius * @sin(a1) };
        const tangent0 = Vec2{ .x = -shape.radius * @sin(a0), .y = shape.radius * @cos(a0) };
        const tangent1 = Vec2{ .x = -shape.radius * @sin(a1), .y = shape.radius * @cos(a1) };
        const p1 = Vec2{ .x = p0.x + k * tangent0.x, .y = p0.y + k * tangent0.y };
        const p2 = Vec2{ .x = p3.x - k * tangent1.x, .y = p3.y - k * tangent1.y };
        try curveToTransformed(ctx, t, p1, p2, p3);
        a0 = a1;
    }
}

fn drawRegularPolygonPathTransformed(ctx: *z2d.Context, shape: RegularPolygon, t: Transform2D) !void {
    ctx.resetPath();
    const n: usize = @intCast(shape.sides);
    for (0..n) |i| {
        const angle = shape.phase + @as(f64, @floatFromInt(i)) * (2.0 * std.math.pi / @as(f64, @floatFromInt(n)));
        const point = Vec2{ .x = shape.radius * @cos(angle), .y = shape.radius * @sin(angle) };
        if (i == 0) try moveToTransformed(ctx, t, point) else try lineToTransformed(ctx, t, point);
    }
    try ctx.closePath();
}

pub fn drawGeometryTransformed(ctx: *z2d.Context, geometry: Geometry, style: Style, t: Transform2D) !void {
    applyStyle(ctx, style);
    switch (geometry) {
        .line => |shape| {
            ctx.resetPath();
            try moveToTransformed(ctx, t, shape.start);
            try lineToTransformed(ctx, t, shape.end);
            try drawOpenPath(ctx, style);
        },
        .polyline => |shape| {
            ctx.resetPath();
            try moveToTransformed(ctx, t, shape.points[0]);
            for (shape.points[1..]) |point| try lineToTransformed(ctx, t, point);
            try drawOpenPath(ctx, style);
        },
        .polygon => |shape| {
            try beginPolygonTransformed(ctx, shape.points, t);
            try finishPath(ctx, style);
        },
        .rectangle => |shape| {
            try drawRectanglePathTransformed(ctx, shape.width, shape.height, t);
            try finishPath(ctx, style);
        },
        .square => |shape| {
            try drawRectanglePathTransformed(ctx, shape.side, shape.side, t);
            try finishPath(ctx, style);
        },
        .circle => |shape| {
            try drawEllipsePathTransformed(ctx, shape.radius, shape.radius, t);
            try finishPath(ctx, style);
        },
        .ellipse => |shape| {
            try drawEllipsePathTransformed(ctx, shape.radius_x, shape.radius_y, t);
            try finishPath(ctx, style);
        },
        .arc => |shape| {
            try drawArcPathTransformed(ctx, shape, t);
            try drawOpenPath(ctx, style);
        },
        .regular_polygon => |shape| {
            try drawRegularPolygonPathTransformed(ctx, shape, t);
            try finishPath(ctx, style);
        },
        .cubic_bezier => |shape| {
            ctx.resetPath();
            try moveToTransformed(ctx, t, shape.p0);
            try curveToTransformed(ctx, t, shape.p1, shape.p2, shape.p3);
            try drawOpenPath(ctx, style);
        },
        .cubic_path => |shape| {
            ctx.resetPath();
            try moveToTransformed(ctx, t, shape.segments[0].p0);
            for (shape.segments) |segment| {
                try curveToTransformed(ctx, t, segment.p1, segment.p2, segment.p3);
            }
            if (shape.closed) {
                try ctx.closePath();
                try finishPath(ctx, style);
            } else {
                try drawOpenPath(ctx, style);
            }
        },
    }
}

pub fn drawGeometry(ctx: *z2d.Context, geometry: Geometry, style: Style) !void {
    try drawGeometryTransformed(ctx, geometry, style, Transform2D.identity);
}

test "geometry constructors reject invalid sizes" {
    try std.testing.expectError(error.InvalidRadius, Circle.init(0));
    try std.testing.expectError(error.InvalidSize, Rectangle.init(-1, 2));
    try std.testing.expectError(error.TooFewSides, RegularPolygon.init(2, 1, 0));
}

test "Object2D defaults to identity affine transform" {
    const object = Object2D.init(.{ .circle = try Circle.init(1.0) });
    const p0 = object.localToWorld(.{});
    const p1 = object.localToWorld(.{ .x = 1, .y = 2 });
    try std.testing.expectApproxEqAbs(@as(f64, 0), p0.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 0), p0.y, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 1), p1.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 2), p1.y, 1e-12);
}

test "local and world linear transforms have distinct frame semantics" {
    var local_object = Object2D.init(.{ .circle = try Circle.init(1.0) });
    local_object.transform = Transform2D.identity.translate(2, 3);
    local_object.applyLinearLocal(Linear2D.scaling(2, 1));
    const local_origin = local_object.localToWorld(.{});
    const local_x = local_object.localToWorld(.{ .x = 1, .y = 0 });
    try std.testing.expectApproxEqAbs(@as(f64, 2), local_origin.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 3), local_origin.y, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 4), local_x.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 3), local_x.y, 1e-12);

    var world_object = Object2D.init(.{ .circle = try Circle.init(1.0) });
    world_object.transform = Transform2D.identity.translate(2, 3);
    world_object.applyLinearWorld(Linear2D.scaling(2, 1));
    const world_origin = world_object.localToWorld(.{});
    const world_x = world_object.localToWorld(.{ .x = 1, .y = 0 });
    try std.testing.expectApproxEqAbs(@as(f64, 4), world_origin.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 3), world_origin.y, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 6), world_x.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 3), world_x.y, 1e-12);
}

test "SE2 object operations are affine composition wrappers" {
    var local_object = Object2D.init(.{ .rectangle = try Rectangle.init(2, 1) });
    local_object.transform = Transform2D.identity.rotate(std.math.pi / 2.0);
    local_object.applySE2Local(SE2.init(0, .{ .x = 1, .y = 0 }));
    const local_origin = local_object.localToWorld(.{});
    try std.testing.expectApproxEqAbs(@as(f64, 0), local_origin.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 1), local_origin.y, 1e-12);

    var world_object = Object2D.init(.{ .rectangle = try Rectangle.init(2, 1) });
    world_object.transform = Transform2D.identity.rotate(std.math.pi / 2.0);
    world_object.applySE2World(SE2.init(0, .{ .x = 1, .y = 0 }));
    const world_origin = world_object.localToWorld(.{});
    try std.testing.expectApproxEqAbs(@as(f64, 1), world_origin.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 0), world_origin.y, 1e-12);
}

test "common geometry renders through Canvas and affine object transforms" {
    const alloc = std.testing.allocator;
    var threaded: std.Io.Threaded = .init_single_threaded;
    const io = threaded.io();
    var surface = try z2d.Surface.initPixel(
        .{ .rgb = .{ .r = 10, .g = 12, .b = 18 } },
        alloc,
        640,
        360,
    );
    defer surface.deinit(alloc);

    var ctx = z2d.Context.init(io, alloc, &surface);
    defer ctx.deinit();
    ctx.setAntiAliasingMode(.multisample_4x);

    const canvas = try Canvas.init(640, 360, 60);
    const view = math.Transform2D.identity;
    const fill_style = Style{
        .fill = .{ .r = 70, .g = 130, .b = 230, .a = 180 },
        .stroke = .{ .color = .{ .r = 230, .g = 235, .b = 245 }, .width = 0.03 },
    };

    const polygon_points = [_]Vec2{
        .{ .x = -0.8, .y = -0.5 },
        .{ .x = 0.9, .y = -0.3 },
        .{ .x = 0.2, .y = 0.9 },
    };
    const polyline_points = [_]Vec2{
        .{ .x = -1, .y = -0.5 },
        .{ .x = 0, .y = 0.7 },
        .{ .x = 1, .y = -0.2 },
    };

    const objects = [_]Object2D{
        .{ .geometry = .{ .line = Line.init(.{ .x = -1, .y = 0 }, .{ .x = 1, .y = 0 }) }, .transform = SE2.init(0.25, .{ .x = -3.5, .y = 1.8 }).toTransform2D() },
        .{ .geometry = .{ .polyline = try Polyline.init(&polyline_points) }, .transform = SE2.init(-0.2, .{ .x = 0, .y = 1.8 }).toTransform2D() },
        .{ .geometry = .{ .polygon = try Polygon.init(&polygon_points) }, .transform = SE2.init(0.4, .{ .x = 3.5, .y = 1.8 }).toTransform2D(), .style = fill_style },
        .{ .geometry = .{ .rectangle = try Rectangle.init(2.2, 1.1) }, .transform = SE2.init(0.3, .{ .x = -3.5, .y = 0 }).toTransform2D(), .style = fill_style },
        .{ .geometry = .{ .square = try Square.init(1.4) }, .transform = SE2.init(-0.45, .{ .x = -1.2, .y = 0 }).toTransform2D(), .style = fill_style },
        .{ .geometry = .{ .circle = try Circle.init(0.75) }, .transform = SE2.init(0.8, .{ .x = 1.2, .y = 0 }).toTransform2D(), .style = fill_style },
        .{ .geometry = .{ .ellipse = try Ellipse.init(1.0, 0.55) }, .transform = SE2.init(0.55, .{ .x = 3.7, .y = 0 }).toTransform2D(), .style = fill_style },
        .{ .geometry = .{ .arc = try Arc.init(0.9, -0.4, 1.8) }, .transform = SE2.init(-0.35, .{ .x = -3.2, .y = -1.8 }).toTransform2D() },
        .{ .geometry = .{ .regular_polygon = try RegularPolygon.init(6, 0.9, std.math.pi / 2.0) }, .transform = SE2.init(0.2, .{ .x = 0, .y = -1.8 }).toTransform2D(), .style = fill_style },
        .{ .geometry = .{ .cubic_bezier = CubicBezier.init(.{ .x = -1, .y = -0.5 }, .{ .x = -0.3, .y = 1 }, .{ .x = 0.3, .y = -1 }, .{ .x = 1, .y = 0.5 }) }, .transform = SE2.init(0.35, .{ .x = 3.3, .y = -1.8 }).toTransform2D() },
    };

    for (objects) |object| try object.draw(&ctx, canvas, view);
}

test "Object2D singular linear map can render" {
    const alloc = std.testing.allocator;
    var threaded: std.Io.Threaded = .init_single_threaded;
    const io = threaded.io();
    var surface = try z2d.Surface.initPixel(
        .{ .rgb = .{ .r = 10, .g = 12, .b = 18 } },
        alloc,
        320,
        180,
    );
    defer surface.deinit(alloc);

    var ctx = z2d.Context.init(io, alloc, &surface);
    defer ctx.deinit();

    const canvas = try Canvas.init(320, 180, 50);
    var object = Object2D{
        .geometry = .{ .rectangle = try Rectangle.init(2, 1) },
        .style = .{ .fill = .{ .r = 80, .g = 140, .b = 230 } },
    };
    object.applyLinearLocal(Linear2D.init(1, 0, 0, 0));
    try object.draw(&ctx, canvas, Transform2D.identity);
}
