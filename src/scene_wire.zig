const std = @import("std");
const z2d = @import("z2d");
const canvas_mod = @import("canvas.zig");
const batch = @import("batch.zig");
const geometry = @import("geometry.zig");
const interpolation = @import("interpolation.zig");
const math = @import("math.zig");
const raster = @import("raster.zig");
const vector = @import("vector.zig");

const Canvas = canvas_mod.Canvas;
const Vec2 = math.Vec2;
const Transform2D = math.Transform2D;

pub const GeometryKind = enum(u32) {
    line = 0,
    polyline = 1,
    polygon = 2,
    rectangle = 3,
    square = 4,
    circle = 5,
    ellipse = 6,
    arc = 7,
    regular_polygon = 8,
    cubic_bezier = 9,
};

/// Simple C ABI value for one persistent Object2D snapshot.
/// `points` is only used by polyline/polygon and stores flattened x,y pairs.
pub const WireObject = extern struct {
    kind: u32,
    p0: f64,
    p1: f64,
    p2: f64,
    p3: f64,
    p4: f64,
    p5: f64,
    p6: f64,
    p7: f64,
    points: ?[*]const f64,
    point_count: u32,

    xx: f64,
    xy: f64,
    yx: f64,
    yy: f64,
    tx: f64,
    ty: f64,

    fill_present: u32,
    fill_rgba: u32,
    stroke_present: u32,
    stroke_rgba: u32,
    stroke_width: f64,
    opacity: f64,
};

pub const WireInterpolation = extern struct {
    source: WireObject,
    target: WireObject,
    alpha: f64,
};

pub const DrawKind = enum(u32) {
    object = 0,
    batch = 1,
    vector = 2,
    interpolation = 3,
    raster = 4,
};

/// One command in the fully ordered scene draw stream. `index` addresses the
/// payload array selected by `kind`. This preserves Python Scene.add order
/// across heterogeneous object representations without introducing a scene graph.
pub const WireDrawItem = extern struct {
    kind: u32,
    index: u32,
};

const OwnedObject = struct {
    object: geometry.Object2D,
    owned_points: ?[]Vec2 = null,

    fn deinit(self: *OwnedObject, allocator: std.mem.Allocator) void {
        if (self.owned_points) |points| allocator.free(points);
        self.* = undefined;
    }
};

fn decodeColor(rgba: u32) geometry.Color {
    return .{
        .r = @intCast((rgba >> 24) & 0xff),
        .g = @intCast((rgba >> 16) & 0xff),
        .b = @intCast((rgba >> 8) & 0xff),
        .a = @intCast(rgba & 0xff),
    };
}

fn scaleAlpha(color: geometry.Color, opacity_raw: f64) geometry.Color {
    const opacity = @max(0.0, @min(1.0, opacity_raw));
    var out = color;
    out.a = @intFromFloat(@round(@as(f64, @floatFromInt(color.a)) * opacity));
    return out;
}

fn decodeStyle(wire: WireObject) geometry.Style {
    return .{
        .fill = if (wire.fill_present != 0) scaleAlpha(decodeColor(wire.fill_rgba), wire.opacity) else null,
        .stroke = if (wire.stroke_present != 0)
            .{ .color = scaleAlpha(decodeColor(wire.stroke_rgba), wire.opacity), .width = wire.stroke_width }
        else
            null,
    };
}

fn copyPoints(allocator: std.mem.Allocator, wire: WireObject) ![]Vec2 {
    if (wire.point_count == 0 or wire.points == null) return error.InvalidWireGeometry;
    const out = try allocator.alloc(Vec2, wire.point_count);
    errdefer allocator.free(out);
    const raw = wire.points.?;
    for (out, 0..) |*point, i| {
        point.* = .{ .x = raw[i * 2], .y = raw[i * 2 + 1] };
    }
    return out;
}

fn decodeObject(allocator: std.mem.Allocator, wire: WireObject) !OwnedObject {
    const kind: GeometryKind = switch (wire.kind) {
        0 => .line,
        1 => .polyline,
        2 => .polygon,
        3 => .rectangle,
        4 => .square,
        5 => .circle,
        6 => .ellipse,
        7 => .arc,
        8 => .regular_polygon,
        9 => .cubic_bezier,
        else => return error.InvalidWireGeometry,
    };

    var owned_points: ?[]Vec2 = null;
    errdefer if (owned_points) |points| allocator.free(points);

    const g: geometry.Geometry = switch (kind) {
        .line => .{ .line = geometry.Line.init(.{ .x = wire.p0, .y = wire.p1 }, .{ .x = wire.p2, .y = wire.p3 }) },
        .polyline => blk: {
            const points = try copyPoints(allocator, wire);
            owned_points = points;
            break :blk .{ .polyline = try geometry.Polyline.init(points) };
        },
        .polygon => blk: {
            const points = try copyPoints(allocator, wire);
            owned_points = points;
            break :blk .{ .polygon = try geometry.Polygon.init(points) };
        },
        .rectangle => .{ .rectangle = try geometry.Rectangle.init(wire.p0, wire.p1) },
        .square => .{ .square = try geometry.Square.init(wire.p0) },
        .circle => .{ .circle = try geometry.Circle.init(wire.p0) },
        .ellipse => .{ .ellipse = try geometry.Ellipse.init(wire.p0, wire.p1) },
        .arc => .{ .arc = try geometry.Arc.init(wire.p0, wire.p1, wire.p2) },
        .regular_polygon => .{ .regular_polygon = try geometry.RegularPolygon.init(@intFromFloat(wire.p0), wire.p1, wire.p2) },
        .cubic_bezier => .{ .cubic_bezier = geometry.CubicBezier.init(
            .{ .x = wire.p0, .y = wire.p1 },
            .{ .x = wire.p2, .y = wire.p3 },
            .{ .x = wire.p4, .y = wire.p5 },
            .{ .x = wire.p6, .y = wire.p7 },
        ) },
    };

    return .{
        .object = .{
            .geometry = g,
            .transform = Transform2D.affine(wire.xx, wire.xy, wire.yx, wire.yy, wire.tx, wire.ty),
            .style = decodeStyle(wire),
        },
        .owned_points = owned_points,
    };
}

fn drawInterpolation(
    ctx: *z2d.Context,
    canvas: Canvas,
    allocator: std.mem.Allocator,
    wire: WireInterpolation,
) !void {
    var source = try decodeObject(allocator, wire.source);
    defer source.deinit(allocator);
    var target = try decodeObject(allocator, wire.target);
    defer target.deinit(allocator);

    var source_scratch: [8]geometry.CubicSegment = undefined;
    var target_scratch: [8]geometry.CubicSegment = undefined;
    var output_scratch: [8]geometry.CubicSegment = undefined;
    const transient = try interpolation.sampleObjectsInto(
        source.object,
        target.object,
        wire.alpha,
        &source_scratch,
        &target_scratch,
        &output_scratch,
    );
    try transient.asObject().draw(ctx, canvas, Transform2D.identity);
}

fn drawScene(
    ctx: *z2d.Context,
    canvas: Canvas,
    allocator: std.mem.Allocator,
    draw_items: []const WireDrawItem,
    object_wires: []const WireObject,
    batch_wires: []const batch.WireBatch,
    vector_wires: []const vector.WireVectorObject,
    raster_wires: []const raster.WireRaster,
    interpolation_wires: []const WireInterpolation,
    surface: *z2d.Surface,
) !void {
    for (draw_items) |item| {
        const index: usize = item.index;
        const kind: DrawKind = switch (item.kind) {
            0 => .object,
            1 => .batch,
            2 => .vector,
            3 => .interpolation,
            4 => .raster,
            else => return error.InvalidDrawItem,
        };
        switch (kind) {
            .object => {
                if (index >= object_wires.len) return error.InvalidDrawItem;
                var decoded = try decodeObject(allocator, object_wires[index]);
                defer decoded.deinit(allocator);
                try decoded.object.draw(ctx, canvas, Transform2D.identity);
            },
            .batch => {
                if (index >= batch_wires.len) return error.InvalidDrawItem;
                try batch.drawWireBatch(ctx, canvas, batch_wires[index]);
            },
            .vector => {
                if (index >= vector_wires.len) return error.InvalidDrawItem;
                try vector.drawWireVector(ctx, canvas, vector_wires[index]);
            },
            .interpolation => {
                if (index >= interpolation_wires.len) return error.InvalidDrawItem;
                try drawInterpolation(ctx, canvas, allocator, interpolation_wires[index]);
            },
            .raster => {
                if (index >= raster_wires.len) return error.InvalidDrawItem;
                try raster.drawWireRaster(surface, canvas, raster_wires[index]);
            },
        }
    }
}

/// Render directly into caller-owned 32-bit RGBx pixels. This is the fast
/// video path: no PNG compression and no filesystem round-trip.
pub fn renderRgb0(
    width: i32,
    height: i32,
    unit_size: f64,
    draw_items: []const WireDrawItem,
    object_wires: []const WireObject,
    batch_wires: []const batch.WireBatch,
    vector_wires: []const vector.WireVectorObject,
    raster_wires: []const raster.WireRaster,
    interpolation_wires: []const WireInterpolation,
    pixels: []z2d.pixel.RGB,
) !void {
    const allocator = std.heap.smp_allocator;
    const expected: usize = @intCast(width * height);
    if (pixels.len < expected) return error.OutputBufferTooSmall;

    var threaded: std.Io.Threaded = .init_single_threaded;
    const io = threaded.io();
    var surface = z2d.Surface.initBuffer(
        .image_surface_rgb,
        .{ .r = 14, .g = 17, .b = 24 },
        pixels[0..expected],
        width,
        height,
    );

    var ctx = z2d.Context.init(io, allocator, &surface);
    defer ctx.deinit();
    ctx.setAntiAliasingMode(.multisample_4x);
    ctx.setLineJoinMode(.round);

    const canvas = try Canvas.init(width, height, unit_size);
    try drawScene(&ctx, canvas, allocator, draw_items, object_wires, batch_wires, vector_wires, raster_wires, interpolation_wires, &surface);
}

/// Render into caller-owned transparent premultiplied RGBA pixels.
pub fn renderRgba0(
    width: i32,
    height: i32,
    unit_size: f64,
    draw_items: []const WireDrawItem,
    object_wires: []const WireObject,
    batch_wires: []const batch.WireBatch,
    vector_wires: []const vector.WireVectorObject,
    raster_wires: []const raster.WireRaster,
    interpolation_wires: []const WireInterpolation,
    pixels: []z2d.pixel.RGBA,
) !void {
    const allocator = std.heap.smp_allocator;
    const expected: usize = @intCast(width * height);
    if (pixels.len < expected) return error.OutputBufferTooSmall;

    var threaded: std.Io.Threaded = .init_single_threaded;
    const io = threaded.io();
    var surface = z2d.Surface.initBuffer(
        .image_surface_rgba,
        .{ .r = 0, .g = 0, .b = 0, .a = 0 },
        pixels[0..expected],
        width,
        height,
    );
    var ctx = z2d.Context.init(io, allocator, &surface);
    defer ctx.deinit();
    ctx.setAntiAliasingMode(.multisample_4x);
    ctx.setLineJoinMode(.round);

    const canvas = try Canvas.init(width, height, unit_size);
    try drawScene(&ctx, canvas, allocator, draw_items, object_wires, batch_wires, vector_wires, raster_wires, interpolation_wires, &surface);
    for (pixels[0..expected]) |*px| px.* = px.demultiply();
}

pub fn renderFrame(
    path: []const u8,
    width: i32,
    height: i32,
    unit_size: f64,
    draw_items: []const WireDrawItem,
    object_wires: []const WireObject,
    batch_wires: []const batch.WireBatch,
    vector_wires: []const vector.WireVectorObject,
    raster_wires: []const raster.WireRaster,
    interpolation_wires: []const WireInterpolation,
) !void {
    const allocator = std.heap.smp_allocator;
    var threaded: std.Io.Threaded = .init_single_threaded;
    const io = threaded.io();

    var surface = try z2d.Surface.initPixel(
        .{ .rgb = .{ .r = 14, .g = 17, .b = 24 } },
        allocator,
        width,
        height,
    );
    defer surface.deinit(allocator);

    var ctx = z2d.Context.init(io, allocator, &surface);
    defer ctx.deinit();
    ctx.setAntiAliasingMode(.multisample_4x);
    ctx.setLineJoinMode(.round);

    const canvas = try Canvas.init(width, height, unit_size);

    try drawScene(&ctx, canvas, allocator, draw_items, object_wires, batch_wires, vector_wires, raster_wires, interpolation_wires, &surface);
    try z2d.png_exporter.writeToPNGFile(io, surface, path, .{});
}
