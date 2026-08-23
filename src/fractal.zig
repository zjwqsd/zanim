const std = @import("std");
const z2d = @import("z2d");
const canvas_mod = @import("canvas.zig");
const geometry = @import("geometry.zig");
const math = @import("math.zig");
const procedural = @import("procedural.zig");

const Canvas = canvas_mod.Canvas;
const Transform2D = math.Transform2D;
const Vec2 = math.Vec2;

pub const Kind = procedural.FractalKind;

pub const Params = struct {
    kind: u32,
    max_iter: u32,
    escape_radius: f64,
    julia_re: f64,
    julia_im: f64,
    color_shift: f64,
    color_scale: f64,
    transform: Transform2D,
    inside_color: geometry.Color,
    palette_color: geometry.Color,
};

fn blendRgb(dst: z2d.pixel.RGB, color: geometry.Color) z2d.pixel.RGB {
    if (color.a == 0) return dst;
    const src = (z2d.pixel.RGBA{ .r = color.r, .g = color.g, .b = color.b, .a = color.a }).multiply();
    return z2d.compositor.runPixelT(z2d.pixel.RGB, dst, z2d.pixel.RGBA, src, .src_over);
}

fn blendRgba(dst: z2d.pixel.RGBA, color: geometry.Color) z2d.pixel.RGBA {
    if (color.a == 0) return dst;
    const src = (z2d.pixel.RGBA{ .r = color.r, .g = color.g, .b = color.b, .a = color.a }).multiply();
    return z2d.compositor.runPixelT(z2d.pixel.RGBA, dst, z2d.pixel.RGBA, src, .src_over);
}

fn colorAt(local: Vec2, kind: Kind, params: Params, escape2: f64) geometry.Color {
    const result = procedural.fractalEscape(
        kind,
        .{ .re = local.x, .im = local.y },
        .{ .re = params.julia_re, .im = params.julia_im },
        params.max_iter,
        escape2,
    );
    if (!result.escaped) return params.inside_color;
    const rgb = procedural.fractalRgb(procedural.fractalSmoothIteration(result), params.color_shift, params.color_scale, params.palette_color.r, params.palette_color.g, params.palette_color.b);
    return .{ .r = rgb[0], .g = rgb[1], .b = rgb[2], .a = params.palette_color.a };
}

pub fn draw(ctx: *z2d.Context, canvas: Canvas, params: Params) !void {
    const kind: Kind = switch (params.kind) {
        1 => .mandelbrot,
        2 => .julia,
        else => return error.InvalidFractalKind,
    };
    if (params.max_iter == 0 or params.max_iter > 100_000 or
        !(params.escape_radius >= 2.0) or !std.math.isFinite(params.escape_radius) or
        !(params.color_scale > 0.0) or !std.math.isFinite(params.color_scale))
        return error.InvalidFractal;

    const inverse = params.transform.inverse() catch return error.InvalidFractalTransform;
    const escape2 = params.escape_radius * params.escape_radius;
    const width: usize = @intCast(canvas.width);
    const height: usize = @intCast(canvas.height);

    switch (ctx.surface.*) {
        .image_surface_rgb => |*surface| {
            for (0..height) |y| {
                const vy = -((@as(f64, @floatFromInt(y)) + 0.5) - canvas.origin_device.y) / canvas.unit_size;
                for (0..width) |x| {
                    const vx = ((@as(f64, @floatFromInt(x)) + 0.5) - canvas.origin_device.x) / canvas.unit_size;
                    const local = inverse.applyPoint(.{ .x = vx, .y = vy });
                    const index = y * width + x;
                    surface.buf[index] = blendRgb(surface.buf[index], colorAt(local, kind, params, escape2));
                }
            }
        },
        .image_surface_rgba => |*surface| {
            for (0..height) |y| {
                const vy = -((@as(f64, @floatFromInt(y)) + 0.5) - canvas.origin_device.y) / canvas.unit_size;
                for (0..width) |x| {
                    const vx = ((@as(f64, @floatFromInt(x)) + 0.5) - canvas.origin_device.x) / canvas.unit_size;
                    const local = inverse.applyPoint(.{ .x = vx, .y = vy });
                    const index = y * width + x;
                    surface.buf[index] = blendRgba(surface.buf[index], colorAt(local, kind, params, escape2));
                }
            }
        },
        else => return error.UnsupportedFractalSurface,
    }
}

test "mandelbrot cardioid shortcut contains zero" {
    try std.testing.expect(procedural.insideMainMandelbrotComponents(.{ .re = 0, .im = 0 }));
    try std.testing.expect(!procedural.insideMainMandelbrotComponents(.{ .re = 1, .im = 1 }));
}

test "mandelbrot escapes outside radius" {
    const result = procedural.fractalEscape(.mandelbrot, .{ .re = 2, .im = 2 }, .{ .re = 0, .im = 0 }, 100, 4.0);
    try std.testing.expect(result.escaped);
}

test "julia zero stays bounded for c zero" {
    const result = procedural.fractalEscape(.julia, .{ .re = 0, .im = 0 }, .{ .re = 0, .im = 0 }, 50, 4.0);
    try std.testing.expect(!result.escaped);
}
