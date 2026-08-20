const std = @import("std");
const z2d = @import("z2d");
const math = @import("math.zig");

pub const Vec2 = math.Vec2;
pub const Transform2D = math.Transform2D;

/// Defines the relation between human-friendly mathematical coordinates and
/// z2d device pixels. World coordinates are x-right / y-up.
pub const Canvas = struct {
    width: i32,
    height: i32,
    /// Number of device pixels corresponding to one logical unit.
    unit_size: f64,
    /// Device-space pixel location of mathematical (0, 0).
    origin_device: Vec2,

    pub const Error = error{
        InvalidCanvasSize,
        InvalidUnitSize,
    };

    pub fn init(width: i32, height: i32, unit_size: f64) Error!Canvas {
        if (width <= 0 or height <= 0) return error.InvalidCanvasSize;
        if (!std.math.isFinite(unit_size) or unit_size <= 0) return error.InvalidUnitSize;
        return .{
            .width = width,
            .height = height,
            .unit_size = unit_size,
            .origin_device = .{
                .x = @as(f64, @floatFromInt(width)) * 0.5,
                .y = @as(f64, @floatFromInt(height)) * 0.5,
            },
        };
    }

    pub fn setOriginDevice(self: *Canvas, x: f64, y: f64) void {
        self.origin_device = .{ .x = x, .y = y };
    }

    /// Base matrix from mathematical world coordinates to z2d pixels.
    /// The negative y scale is the only place where y-up becomes device y-down.
    pub fn basis(self: Canvas) Transform2D {
        return Transform2D.identity
            .translate(self.origin_device.x, self.origin_device.y)
            .scale(self.unit_size, -self.unit_size);
    }

    /// Final CTM = Canvas basis × View × Model.
    pub fn matrix(self: Canvas, view: Transform2D, model: Transform2D) Transform2D {
        return self.basis().mul(view).mul(model);
    }

    pub fn worldToDevice(self: Canvas, point: Vec2, view: Transform2D) Vec2 {
        return self.basis().mul(view).applyPoint(point);
    }

    pub fn deviceToWorld(self: Canvas, point: Vec2, view: Transform2D) !Vec2 {
        return (try self.basis().mul(view).inverse()).applyPoint(point);
    }

    pub fn visibleHalfExtents(self: Canvas) Vec2 {
        return .{
            .x = @as(f64, @floatFromInt(self.width)) / (2.0 * self.unit_size),
            .y = @as(f64, @floatFromInt(self.height)) / (2.0 * self.unit_size),
        };
    }

    pub fn apply(self: Canvas, ctx: *z2d.Context, view: Transform2D, model: Transform2D) void {
        ctx.setTransformation(toZ2D(self.matrix(view, model)));
    }
};

pub fn toZ2D(m: Transform2D) z2d.Transformation {
    return .{
        .ax = m.xx,
        .by = m.xy,
        .cx = m.yx,
        .dy = m.yy,
        .tx = m.tx,
        .ty = m.ty,
    };
}

test "centered canvas uses x-right y-up coordinates" {
    const canvas = try Canvas.init(800, 600, 100);
    const origin = canvas.worldToDevice(.{}, Transform2D.identity);
    const one_one = canvas.worldToDevice(.{ .x = 1, .y = 1 }, Transform2D.identity);

    try std.testing.expectApproxEqAbs(@as(f64, 400), origin.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 300), origin.y, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 500), one_one.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 200), one_one.y, 1e-12);
}

test "canvas coordinate conversion round trip" {
    const canvas = try Canvas.init(1280, 720, 72);
    const view = Transform2D.identity.translate(1.5, -0.5).rotate(0.2).scale(1.2, 1.2);
    const p = Vec2{ .x = -2.75, .y = 1.25 };
    const back = try canvas.deviceToWorld(canvas.worldToDevice(p, view), view);
    try std.testing.expectApproxEqAbs(p.x, back.x, 1e-11);
    try std.testing.expectApproxEqAbs(p.y, back.y, 1e-11);
}
