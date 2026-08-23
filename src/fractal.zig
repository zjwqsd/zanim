const std = @import("std");
const z2d = @import("z2d");
const canvas_mod = @import("canvas.zig");
const geometry = @import("geometry.zig");
const math = @import("math.zig");

const Canvas = canvas_mod.Canvas;
const Transform2D = math.Transform2D;
const Vec2 = math.Vec2;

pub const Kind = enum(u32) {
    mandelbrot = 1,
    julia = 2,
};

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

const C = struct {
    re: f64,
    im: f64,

    fn abs2(self: C) f64 {
        return self.re * self.re + self.im * self.im;
    }

    fn squareAdd(self: C, c: C) C {
        return .{
            .re = self.re * self.re - self.im * self.im + c.re,
            .im = 2.0 * self.re * self.im + c.im,
        };
    }
};

const Escape = struct {
    escaped: bool,
    iteration: u32,
    z: C,
};

fn insideMainMandelbrotComponents(c: C) bool {
    // Exact interior shortcuts for the main cardioid and period-2 bulb. They
    // avoid hundreds of iterations over the large black interior at deep zoom.
    const x = c.re;
    const y2 = c.im * c.im;
    const xm = x - 0.25;
    const q = xm * xm + y2;
    if (q * (q + xm) <= 0.25 * y2) return true;
    const xp = x + 1.0;
    return xp * xp + y2 <= 0.0625;
}

fn escape(kind: Kind, point: C, julia_c: C, max_iter: u32, escape2: f64) Escape {
    if (kind == .mandelbrot and insideMainMandelbrotComponents(point)) {
        return .{ .escaped = false, .iteration = max_iter, .z = .{ .re = 0, .im = 0 } };
    }

    var z = if (kind == .mandelbrot) C{ .re = 0, .im = 0 } else point;
    const c = if (kind == .mandelbrot) point else julia_c;
    var i: u32 = 0;
    while (i < max_iter) : (i += 1) {
        z = z.squareAdd(c);
        if (z.abs2() > escape2) {
            return .{ .escaped = true, .iteration = i + 1, .z = z };
        }
    }
    return .{ .escaped = false, .iteration = max_iter, .z = z };
}

fn smoothIteration(result: Escape) f64 {
    const mag2 = @max(result.z.abs2(), 1.0000000001);
    const log_abs = 0.5 * @log(mag2);
    if (!(log_abs > 0.0) or !std.math.isFinite(log_abs)) {
        return @floatFromInt(result.iteration);
    }
    const nu = @log(log_abs / @log(2.0)) / @log(2.0);
    const value = @as(f64, @floatFromInt(result.iteration)) + 1.0 - nu;
    return if (std.math.isFinite(value)) value else @floatFromInt(result.iteration);
}

fn channel(value: f64) u8 {
    return @intFromFloat(@round(@max(0.0, @min(255.0, value))));
}

fn palette(mu: f64, shift: f64, scale: f64, tint: geometry.Color) geometry.Color {
    // A continuous cosine palette keyed to smooth escape time rather than to
    // max_iter, so changing iteration budget does not make the picture jump.
    const tau = 2.0 * std.math.pi;
    const phase = shift + mu * 0.021 * scale;
    const tr = 0.35 + 0.65 * (@as(f64, @floatFromInt(tint.r)) / 255.0);
    const tg = 0.35 + 0.65 * (@as(f64, @floatFromInt(tint.g)) / 255.0);
    const tb = 0.35 + 0.65 * (@as(f64, @floatFromInt(tint.b)) / 255.0);
    return .{
        .r = channel(255.0 * tr * (0.5 + 0.5 * @cos(tau * (phase + 0.00)))),
        .g = channel(255.0 * tg * (0.5 + 0.5 * @cos(tau * (phase + 0.12)))),
        .b = channel(255.0 * tb * (0.5 + 0.5 * @cos(tau * (phase + 0.24)))),
        .a = tint.a,
    };
}

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
    const result = escape(
        kind,
        .{ .re = local.x, .im = local.y },
        .{ .re = params.julia_re, .im = params.julia_im },
        params.max_iter,
        escape2,
    );
    if (!result.escaped) return params.inside_color;
    return palette(smoothIteration(result), params.color_shift, params.color_scale, params.palette_color);
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
    try std.testing.expect(insideMainMandelbrotComponents(.{ .re = 0, .im = 0 }));
    try std.testing.expect(!insideMainMandelbrotComponents(.{ .re = 1, .im = 1 }));
}

test "mandelbrot escapes outside radius" {
    const result = escape(.mandelbrot, .{ .re = 2, .im = 2 }, .{ .re = 0, .im = 0 }, 100, 4.0);
    try std.testing.expect(result.escaped);
}

test "julia zero stays bounded for c zero" {
    const result = escape(.julia, .{ .re = 0, .im = 0 }, .{ .re = 0, .im = 0 }, 50, 4.0);
    try std.testing.expect(!result.escaped);
}
