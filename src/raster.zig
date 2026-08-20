const std = @import("std");
const z2d = @import("z2d");
const canvas_mod = @import("canvas.zig");
const math = @import("math.zig");

const Canvas = canvas_mod.Canvas;
const Vec2 = math.Vec2;
const Transform2D = math.Transform2D;

pub const WireRaster = extern struct {
    pixels: ?[*]const u8,
    pixel_width: u32,
    pixel_height: u32,
    logical_width: f64,
    logical_height: f64,
    xx: f64,
    xy: f64,
    yx: f64,
    yy: f64,
    tx: f64,
    ty: f64,
    opacity: f64,
};

const Premul = struct {
    r: f64 = 0,
    g: f64 = 0,
    b: f64 = 0,
    a: f64 = 0,

    fn scale(self: Premul, weight: f64) Premul {
        return .{ .r = self.r * weight, .g = self.g * weight, .b = self.b * weight, .a = self.a * weight };
    }

    fn add(a: Premul, b: Premul) Premul {
        return .{ .r = a.r + b.r, .g = a.g + b.g, .b = a.b + b.b, .a = a.a + b.a };
    }
};

fn sourcePixel(wire: WireRaster, x: i32, y: i32) Premul {
    if (x < 0 or y < 0 or x >= wire.pixel_width or y >= wire.pixel_height or wire.pixels == null) return .{};
    const ux: usize = @intCast(x);
    const uy: usize = @intCast(y);
    const width: usize = @intCast(wire.pixel_width);
    const base = (uy * width + ux) * 4;
    const raw = wire.pixels.?;
    const alpha = @as(f64, @floatFromInt(raw[base + 3])) / 255.0;
    return .{
        .r = @as(f64, @floatFromInt(raw[base])) * alpha,
        .g = @as(f64, @floatFromInt(raw[base + 1])) * alpha,
        .b = @as(f64, @floatFromInt(raw[base + 2])) * alpha,
        .a = alpha,
    };
}

fn bilinear(wire: WireRaster, source: Vec2) Premul {
    // Source coordinates address pixel edges; integer+0.5 are pixel centers.
    const fx = source.x - 0.5;
    const fy = source.y - 0.5;
    const x0: i32 = @intFromFloat(@floor(fx));
    const y0: i32 = @intFromFloat(@floor(fy));
    const tx = fx - @as(f64, @floatFromInt(x0));
    const ty = fy - @as(f64, @floatFromInt(y0));
    const a = sourcePixel(wire, x0, y0).scale((1.0 - tx) * (1.0 - ty));
    const b = sourcePixel(wire, x0 + 1, y0).scale(tx * (1.0 - ty));
    const c = sourcePixel(wire, x0, y0 + 1).scale((1.0 - tx) * ty);
    const d = sourcePixel(wire, x0 + 1, y0 + 1).scale(tx * ty);
    return a.add(b).add(c).add(d);
}

fn clampU8(value: f64) u8 {
    return @intFromFloat(@round(@max(0.0, @min(255.0, value))));
}

fn blend(dst: z2d.pixel.RGB, src: Premul, opacity_raw: f64) z2d.pixel.RGB {
    // This is intentionally specialized instead of calling z2d.runPixelT:
    // affine raster sampling touches millions of pixels per frame, and the
    // generic RGBA16 conversion path is an order of magnitude slower here.
    const opacity = @max(0.0, @min(1.0, opacity_raw));
    const alpha = src.a * opacity;
    const inv = 1.0 - alpha;
    return .{
        .r = clampU8(src.r * opacity + @as(f64, @floatFromInt(dst.r)) * inv),
        .g = clampU8(src.g * opacity + @as(f64, @floatFromInt(dst.g)) * inv),
        .b = clampU8(src.b * opacity + @as(f64, @floatFromInt(dst.b)) * inv),
    };
}

fn blendRgba(dst: z2d.pixel.RGBA, src: Premul, opacity_raw: f64) z2d.pixel.RGBA {
    const opacity = @max(0.0, @min(1.0, opacity_raw));
    const alpha = src.a * opacity;
    const inv = 1.0 - alpha;
    const dst_alpha = @as(f64, @floatFromInt(dst.a)) / 255.0;
    return .{
        .r = clampU8(src.r * opacity + @as(f64, @floatFromInt(dst.r)) * inv),
        .g = clampU8(src.g * opacity + @as(f64, @floatFromInt(dst.g)) * inv),
        .b = clampU8(src.b * opacity + @as(f64, @floatFromInt(dst.b)) * inv),
        .a = clampU8((alpha + dst_alpha * inv) * 255.0),
    };
}


fn min4(a: f64, b: f64, c: f64, d: f64) f64 {
    return @min(@min(a, b), @min(c, d));
}
fn max4(a: f64, b: f64, c: f64, d: f64) f64 {
    return @max(@max(a, b), @max(c, d));
}

pub fn drawWireRaster(surface: *z2d.Surface, canvas: Canvas, wire: WireRaster) !void {
    if (wire.pixels == null or wire.pixel_width == 0 or wire.pixel_height == 0) return error.InvalidRaster;
    if (!(wire.logical_width > 0) or !(wire.logical_height > 0)) return error.InvalidRaster;
    if (wire.opacity <= 0) return;

    const model = Transform2D.affine(wire.xx, wire.xy, wire.yx, wire.yy, wire.tx, wire.ty);
    const source_to_local = Transform2D.identity
        .translate(-wire.logical_width * 0.5, wire.logical_height * 0.5)
        .scale(
        wire.logical_width / @as(f64, @floatFromInt(wire.pixel_width)),
        -wire.logical_height / @as(f64, @floatFromInt(wire.pixel_height)),
    );
    const source_to_device = canvas.basis().mul(model).mul(source_to_local);
    const device_to_source = source_to_device.inverse() catch return; // zero-area raster

    const w: f64 = @floatFromInt(wire.pixel_width);
    const h: f64 = @floatFromInt(wire.pixel_height);
    const p0 = source_to_device.applyPoint(.{ .x = 0, .y = 0 });
    const p1 = source_to_device.applyPoint(.{ .x = w, .y = 0 });
    const p2 = source_to_device.applyPoint(.{ .x = w, .y = h });
    const p3 = source_to_device.applyPoint(.{ .x = 0, .y = h });

    var x0: i32 = @intFromFloat(@floor(min4(p0.x, p1.x, p2.x, p3.x)));
    var y0: i32 = @intFromFloat(@floor(min4(p0.y, p1.y, p2.y, p3.y)));
    var x1: i32 = @intFromFloat(@ceil(max4(p0.x, p1.x, p2.x, p3.x)));
    var y1: i32 = @intFromFloat(@ceil(max4(p0.y, p1.y, p2.y, p3.y)));
    x0 = @max(0, x0);
    y0 = @max(0, y0);
    x1 = @min(canvas.width, x1);
    y1 = @min(canvas.height, y1);
    if (x0 >= x1 or y0 >= y1) return;

    switch (surface.*) {
        .image_surface_rgb => |*rgb| {
            var y = y0;
            while (y < y1) : (y += 1) {
                var x = x0;
                while (x < x1) : (x += 1) {
                    const source = device_to_source.applyPoint(.{
                        .x = @as(f64, @floatFromInt(x)) + 0.5,
                        .y = @as(f64, @floatFromInt(y)) + 0.5,
                    });
                    // Keep one-pixel support outside the image for bilinear
                    // edge antialiasing; sourcePixel returns transparent there.
                    if (source.x < -0.5 or source.y < -0.5 or
                        source.x > w + 0.5 or source.y > h + 0.5) continue;
                    const sample = bilinear(wire, source);
                    if (sample.a <= 0) continue;
                    const index: usize = @intCast(y * canvas.width + x);
                    rgb.buf[index] = blend(rgb.buf[index], sample, wire.opacity);
                }
            }
        },
        .image_surface_rgba => |*rgba| {
            var y = y0;
            while (y < y1) : (y += 1) {
                var x = x0;
                while (x < x1) : (x += 1) {
                    const source = device_to_source.applyPoint(.{
                        .x = @as(f64, @floatFromInt(x)) + 0.5,
                        .y = @as(f64, @floatFromInt(y)) + 0.5,
                    });
                    if (source.x < -0.5 or source.y < -0.5 or
                        source.x > w + 0.5 or source.y > h + 0.5) continue;
                    const sample = bilinear(wire, source);
                    if (sample.a <= 0) continue;
                    const index: usize = @intCast(y * canvas.width + x);
                    rgba.buf[index] = blendRgba(rgba.buf[index], sample, wire.opacity);
                }
            }
        },
        else => return error.UnsupportedRasterSurface,
    }
}

test "transparent raster blend is source-over" {
    const dst = z2d.pixel.RGB{ .r = 20, .g = 40, .b = 60 };
    const src = Premul{ .r = 100, .g = 0, .b = 0, .a = 0.5 };
    const got = blend(dst, src, 1.0);
    try std.testing.expectEqual(@as(u8, 110), got.r);
    try std.testing.expectEqual(@as(u8, 20), got.g);
    try std.testing.expectEqual(@as(u8, 30), got.b);
}
