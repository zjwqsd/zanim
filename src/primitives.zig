const std = @import("std");
const z2d = @import("z2d");
const math = @import("math.zig");

pub const Vec2 = math.Vec2;

pub const Color = struct {
    r: u8,
    g: u8,
    b: u8,
    a: u8 = 255,
};

pub fn setColor(ctx: *z2d.Context, color: Color) void {
    // z2d compositor requires pre-multiplied alpha. Keep the public color
    // representation conventional (straight alpha) and convert here.
    const rgba: z2d.pixel.RGBA = .{
        .r = color.r,
        .g = color.g,
        .b = color.b,
        .a = color.a,
    };
    ctx.setSourceToPixel(.{ .rgba = rgba.multiply() });
}

pub fn line(ctx: *z2d.Context, a: Vec2, b: Vec2) !void {
    ctx.resetPath();
    try ctx.moveTo(a.x, a.y);
    try ctx.lineTo(b.x, b.y);
    try ctx.stroke();
}

pub fn polyline(ctx: *z2d.Context, points: []const Vec2) !void {
    if (points.len < 2) return;
    ctx.resetPath();
    try ctx.moveTo(points[0].x, points[0].y);
    for (points[1..]) |p| try ctx.lineTo(p.x, p.y);
    try ctx.stroke();
}

pub fn polygon(ctx: *z2d.Context, points: []const Vec2, fill: bool, stroke: bool) !void {
    if (points.len < 3) return;
    ctx.resetPath();
    try ctx.moveTo(points[0].x, points[0].y);
    for (points[1..]) |p| try ctx.lineTo(p.x, p.y);
    try ctx.closePath();

    if (fill) {
        try ctx.fill();
        if (stroke) {
            // z2d keeps the current path after fill/stroke. Intentionally
            // reuse it here so fill+stroke does not rebuild geometry.
            try ctx.stroke();
        }
    } else if (stroke) {
        try ctx.stroke();
    }
}

pub fn rectangle(ctx: *z2d.Context, width: f64, height: f64, fill: bool, stroke: bool) !void {
    const hw = width * 0.5;
    const hh = height * 0.5;
    const points = [_]Vec2{
        .{ .x = -hw, .y = -hh },
        .{ .x = hw, .y = -hh },
        .{ .x = hw, .y = hh },
        .{ .x = -hw, .y = hh },
    };
    try polygon(ctx, &points, fill, stroke);
}

pub fn circle(ctx: *z2d.Context, radius: f64, fill: bool, stroke: bool) !void {
    ctx.resetPath();
    try ctx.arc(0, 0, radius, 0, std.math.pi * 2.0);
    try ctx.closePath();
    if (fill) {
        try ctx.fill();
        if (stroke) try ctx.stroke();
    } else if (stroke) {
        try ctx.stroke();
    }
}

pub fn cubicBezier(ctx: *z2d.Context, p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2) !void {
    ctx.resetPath();
    try ctx.moveTo(p0.x, p0.y);
    try ctx.curveTo(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
    try ctx.stroke();
}

pub fn regularPolygon(comptime n: usize, radius: f64, phase: f64) [n]Vec2 {
    var points: [n]Vec2 = undefined;
    for (&points, 0..) |*p, i| {
        const angle = phase + @as(f64, @floatFromInt(i)) / @as(f64, @floatFromInt(n)) * std.math.pi * 2.0;
        p.* = .{ .x = @cos(angle) * radius, .y = @sin(angle) * radius };
    }
    return points;
}
