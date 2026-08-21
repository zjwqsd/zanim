const std = @import("std");
const z2d = @import("z2d");
const geometry = @import("geometry.zig");
const math = @import("math.zig");
const canvas_mod = @import("canvas.zig");

const Canvas = canvas_mod.Canvas;
const Transform2D = math.Transform2D;
const Vec2 = math.Vec2;

pub const Kind = enum(u32) {
    line_set = 0,
    circle_set = 1,
    rect_set = 2,
};

/// Borrowed C-ABI batch description. Geometry payload layout:
/// line:   [x0,y0,x1,y1] * count
/// circle: [cx,cy,r]     * count
/// rect:   [cx,cy,w,h]   * count
pub const WireBatch = extern struct {
    kind: u32,
    count: u32,
    data: ?[*]const f64,
    fill_rgba: ?[*]const u32,
    stroke_rgba: ?[*]const u32,
    stroke_widths: ?[*]const f64,

    target_data: ?[*]const f64,
    target_fill_rgba: ?[*]const u32,
    target_stroke_rgba: ?[*]const u32,
    target_stroke_widths: ?[*]const f64,
    alpha: f64,

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

fn mix(a: f64, b: f64, t: f64) f64 {
    return a + (b - a) * t;
}

fn mixU8(a: u8, b: u8, t: f64) u8 {
    return @intFromFloat(@round(@max(0.0, @min(255.0, mix(@floatFromInt(a), @floatFromInt(b), t)))));
}

fn mixColor(a: geometry.Color, b: geometry.Color, t: f64) geometry.Color {
    return .{
        .r = mixU8(a.r, b.r, t),
        .g = mixU8(a.g, b.g, t),
        .b = mixU8(a.b, b.b, t),
        .a = mixU8(a.a, b.a, t),
    };
}

fn withOpacity(color: geometry.Color, opacity_raw: f64) geometry.Color {
    const opacity = @max(0.0, @min(1.0, opacity_raw));
    var out = color;
    out.a = @intFromFloat(@round(@as(f64, @floatFromInt(color.a)) * opacity));
    return out;
}

fn alpha(wire: WireBatch) f64 {
    return @max(0.0, @min(1.0, wire.alpha));
}

fn dataAt(wire: WireBatch, index: usize) f64 {
    const source = wire.data.?[index];
    if (wire.target_data) |target| return mix(source, target[index], alpha(wire));
    return source;
}

fn fillAt(wire: WireBatch, index: usize) geometry.Color {
    const source = decodeColor(wire.fill_rgba.?[index]);
    const color = if (wire.target_fill_rgba) |target|
        mixColor(source, decodeColor(target[index]), alpha(wire))
    else
        source;
    return withOpacity(color, wire.opacity);
}

fn strokeColorAt(wire: WireBatch, index: usize) geometry.Color {
    const t = alpha(wire);
    const color = if (wire.stroke_rgba) |source_ptr| blk: {
        const source = decodeColor(source_ptr[index]);
        if (wire.target_stroke_rgba) |target_ptr| break :blk mixColor(source, decodeColor(target_ptr[index]), t);
        var transparent = source;
        transparent.a = 0;
        break :blk mixColor(source, transparent, t);
    } else blk: {
        const target = decodeColor(wire.target_stroke_rgba.?[index]);
        var transparent = target;
        transparent.a = 0;
        break :blk mixColor(transparent, target, t);
    };
    return withOpacity(color, wire.opacity);
}

fn strokeWidthAt(wire: WireBatch, index: usize) f64 {
    if (wire.stroke_widths) |source| {
        if (wire.target_stroke_widths) |target| return mix(source[index], target[index], alpha(wire));
        return source[index];
    }
    return wire.target_stroke_widths.?[index];
}

fn blendRgb(surface: *z2d.surface.ImageSurface(z2d.pixel.RGB), x: i32, y: i32, color: geometry.Color, coverage_raw: f64) void {
    if (x < 0 or y < 0 or x >= surface.width or y >= surface.height) return;
    const coverage = @max(0.0, @min(1.0, coverage_raw));
    if (coverage <= 0.0) return;
    const alpha_f = @as(f64, @floatFromInt(color.a)) * coverage;
    if (alpha_f < 0.5) return;
    const effective_alpha: u8 = @intFromFloat(@min(255.0, @round(alpha_f)));
    const src = (z2d.pixel.RGBA{ .r = color.r, .g = color.g, .b = color.b, .a = effective_alpha }).multiply();
    const idx: usize = @intCast(y * surface.width + x);
    surface.buf[idx] = z2d.compositor.runPixelT(
        z2d.pixel.RGB,
        surface.buf[idx],
        z2d.pixel.RGBA,
        src,
        .src_over,
    );
}

fn frac(x: f64) f64 {
    return x - @floor(x);
}

fn rfrac(x: f64) f64 {
    return 1.0 - frac(x);
}

/// Xiaolin Wu rasterization for a one-pixel anti-aliased line. Widths below
/// one pixel are represented by proportional coverage, which is ideal for
/// dense graph/network edges. Wider lines intentionally fall back to z2d.
fn drawWuLine(
    surface: *z2d.surface.ImageSurface(z2d.pixel.RGB),
    a: Vec2,
    b: Vec2,
    color: geometry.Color,
    coverage_scale: f64,
) void {
    var x0 = a.x;
    var y0 = a.y;
    var x1 = b.x;
    var y1 = b.y;
    const steep = @abs(y1 - y0) > @abs(x1 - x0);
    if (steep) {
        std.mem.swap(f64, &x0, &y0);
        std.mem.swap(f64, &x1, &y1);
    }
    if (x0 > x1) {
        std.mem.swap(f64, &x0, &x1);
        std.mem.swap(f64, &y0, &y1);
    }

    const dx = x1 - x0;
    const dy = y1 - y0;
    if (@abs(dx) < 1e-12) {
        const px: i32 = @intFromFloat(@round(if (steep) y0 else x0));
        const y_start: i32 = @intFromFloat(@floor(@min(if (steep) x0 else y0, if (steep) x1 else y1)));
        const y_end: i32 = @intFromFloat(@ceil(@max(if (steep) x0 else y0, if (steep) x1 else y1)));
        var yy = y_start;
        while (yy <= y_end) : (yy += 1) blendRgb(surface, px, yy, color, coverage_scale);
        return;
    }
    const gradient = dy / dx;

    const xend1 = @round(x0);
    const yend1 = y0 + gradient * (xend1 - x0);
    const xgap1 = rfrac(x0 + 0.5);
    const xpxl1: i32 = @intFromFloat(xend1);
    const ypxl1: i32 = @intFromFloat(@floor(yend1));
    if (steep) {
        blendRgb(surface, ypxl1, xpxl1, color, rfrac(yend1) * xgap1 * coverage_scale);
        blendRgb(surface, ypxl1 + 1, xpxl1, color, frac(yend1) * xgap1 * coverage_scale);
    } else {
        blendRgb(surface, xpxl1, ypxl1, color, rfrac(yend1) * xgap1 * coverage_scale);
        blendRgb(surface, xpxl1, ypxl1 + 1, color, frac(yend1) * xgap1 * coverage_scale);
    }
    var intery = yend1 + gradient;

    const xend2 = @round(x1);
    const yend2 = y1 + gradient * (xend2 - x1);
    const xgap2 = frac(x1 + 0.5);
    const xpxl2: i32 = @intFromFloat(xend2);
    const ypxl2: i32 = @intFromFloat(@floor(yend2));

    var x = xpxl1 + 1;
    while (x < xpxl2) : (x += 1) {
        const iy: i32 = @intFromFloat(@floor(intery));
        if (steep) {
            blendRgb(surface, iy, x, color, rfrac(intery) * coverage_scale);
            blendRgb(surface, iy + 1, x, color, frac(intery) * coverage_scale);
        } else {
            blendRgb(surface, x, iy, color, rfrac(intery) * coverage_scale);
            blendRgb(surface, x, iy + 1, color, frac(intery) * coverage_scale);
        }
        intery += gradient;
    }

    if (steep) {
        blendRgb(surface, ypxl2, xpxl2, color, rfrac(yend2) * xgap2 * coverage_scale);
        blendRgb(surface, ypxl2 + 1, xpxl2, color, frac(yend2) * xgap2 * coverage_scale);
    } else {
        blendRgb(surface, xpxl2, ypxl2, color, rfrac(yend2) * xgap2 * coverage_scale);
        blendRgb(surface, xpxl2, ypxl2 + 1, color, frac(yend2) * xgap2 * coverage_scale);
    }
}

fn drawThinLineSetFast(
    ctx: *z2d.Context,
    canvas: Canvas,
    wire: WireBatch,
    transform: Transform2D,
) !bool {
    if ((wire.stroke_rgba == null and wire.target_stroke_rgba == null) or
        (wire.stroke_widths == null and wire.target_stroke_widths == null) or wire.data == null) return error.InvalidBatch;
    const rgb_surface = switch (ctx.surface.*) {
        .image_surface_rgb => |*surface| surface,
        else => return false,
    };

    const device = canvas.basis().mul(transform);
    for (0..wire.count) |i| {
        const base = i * 4;
        const width = strokeWidthAt(wire, i);
        const width_px = width * canvas.unit_size;
        const color = strokeColorAt(wire, i);
        if (color.a == 0) continue;
        if (width_px <= 1.0) {
            const a = device.applyPoint(.{ .x = dataAt(wire, base), .y = dataAt(wire, base + 1) });
            const b = device.applyPoint(.{ .x = dataAt(wire, base + 2), .y = dataAt(wire, base + 3) });
            drawWuLine(rgb_surface, a, b, color, width_px);
        } else {
            const object = geometry.Object2D{
                .geometry = .{ .line = geometry.Line.init(
                    .{ .x = dataAt(wire, base), .y = dataAt(wire, base + 1) },
                    .{ .x = dataAt(wire, base + 2), .y = dataAt(wire, base + 3) },
                ) },
                .transform = transform,
                .style = .{ .fill = null, .stroke = .{ .color = color, .width = width } },
            };
            try object.draw(ctx, canvas, Transform2D.identity);
        }
    }
    return true;
}

fn drawAxisAlignedRectSetFast(
    ctx: *z2d.Context,
    canvas: Canvas,
    wire: WireBatch,
    transform: Transform2D,
) !bool {
    if (wire.fill_rgba == null or wire.data == null) return error.InvalidBatch;
    // Stroked rectangles and rotated/sheared transforms keep the general z2d
    // path. This fast path is deliberately narrow: dense filled heatmaps/grids.
    if (wire.stroke_rgba != null or wire.target_stroke_rgba != null) return false;
    const rgb_surface = switch (ctx.surface.*) {
        .image_surface_rgb => |*surface| surface,
        else => return false,
    };

    const device = canvas.basis().mul(transform);
    if (@abs(device.xy) > 1e-12 or @abs(device.yx) > 1e-12) return false;

    const surface_w = rgb_surface.width;
    const surface_h = rgb_surface.height;
    for (0..wire.count) |i| {
        const base = i * 4;
        const color = fillAt(wire, i);
        if (color.a == 0) continue;

        const cx = device.xx * dataAt(wire, base) + device.tx;
        const cy = device.yy * dataAt(wire, base + 1) + device.ty;
        const half_w = @abs(device.xx) * dataAt(wire, base + 2) * 0.5;
        const half_h = @abs(device.yy) * dataAt(wire, base + 3) * 0.5;
        const x0 = cx - half_w;
        const x1 = cx + half_w;
        const y0 = cy - half_h;
        const y1 = cy + half_h;

        // z2d fill coordinates use integer device positions as pixel-cell
        // boundaries: pixel (x,y) covers [x,x+1] × [y,y+1].
        if (x1 <= 0.0 or y1 <= 0.0 or
            x0 >= @as(f64, @floatFromInt(surface_w)) or
            y0 >= @as(f64, @floatFromInt(surface_h))) continue;

        var ix0: i32 = @intFromFloat(@floor(x0));
        var ix1: i32 = @intFromFloat(@ceil(x1) - 1.0);
        var iy0: i32 = @intFromFloat(@floor(y0));
        var iy1: i32 = @intFromFloat(@ceil(y1) - 1.0);
        ix0 = @max(0, ix0);
        iy0 = @max(0, iy0);
        ix1 = @min(surface_w - 1, ix1);
        iy1 = @min(surface_h - 1, iy1);
        if (ix0 > ix1 or iy0 > iy1) continue;

        var y = iy0;
        while (y <= iy1) : (y += 1) {
            const fy: f64 = @floatFromInt(y);
            const y_coverage = @max(0.0, @min(y1, fy + 1.0) - @max(y0, fy));
            if (y_coverage <= 0.0) continue;
            var x = ix0;
            while (x <= ix1) : (x += 1) {
                const fx: f64 = @floatFromInt(x);
                const x_coverage = @max(0.0, @min(x1, fx + 1.0) - @max(x0, fx));
                if (x_coverage <= 0.0) continue;
                blendRgb(rgb_surface, x, y, color, x_coverage * y_coverage);
            }
        }
    }
    return true;
}

pub fn drawWireBatch(ctx: *z2d.Context, canvas: Canvas, wire: WireBatch) !void {
    if (wire.count == 0 or wire.data == null) return error.InvalidBatch;
    const kind: Kind = switch (wire.kind) {
        0 => .line_set,
        1 => .circle_set,
        2 => .rect_set,
        else => return error.InvalidBatch,
    };
    const transform = Transform2D.affine(wire.xx, wire.xy, wire.yx, wire.yy, wire.tx, wire.ty);
    const n: usize = wire.count;
    const data = wire.data.?;

    switch (kind) {
        .line_set => {
            if (try drawThinLineSetFast(ctx, canvas, wire, transform)) return;
            if (wire.stroke_rgba == null or wire.stroke_widths == null) return error.InvalidBatch;
            const colors = wire.stroke_rgba.?;
            const widths = wire.stroke_widths.?;
            for (0..n) |i| {
                const base = i * 4;
                const object = geometry.Object2D{
                    .geometry = .{ .line = geometry.Line.init(
                        .{ .x = data[base], .y = data[base + 1] },
                        .{ .x = data[base + 2], .y = data[base + 3] },
                    ) },
                    .transform = transform,
                    .style = .{
                        .fill = null,
                        .stroke = .{ .color = decodeColor(colors[i]), .width = widths[i] },
                    },
                };
                try object.draw(ctx, canvas, Transform2D.identity);
            }
        },
        .circle_set => {
            if (wire.fill_rgba == null) return error.InvalidBatch;
            for (0..n) |i| {
                const base = i * 3;
                const center = Vec2{ .x = dataAt(wire, base), .y = dataAt(wire, base + 1) };
                const stroke: ?geometry.StrokeStyle = if (wire.stroke_rgba != null or wire.target_stroke_rgba != null)
                    .{ .color = strokeColorAt(wire, i), .width = strokeWidthAt(wire, i) }
                else
                    null;
                const object = geometry.Object2D{
                    .geometry = .{ .circle = try geometry.Circle.init(dataAt(wire, base + 2)) },
                    .transform = transform.mul(Transform2D.identity.translate(center.x, center.y)),
                    .style = .{ .fill = fillAt(wire, i), .stroke = stroke },
                };
                try object.draw(ctx, canvas, Transform2D.identity);
            }
        },
        .rect_set => {
            if (try drawAxisAlignedRectSetFast(ctx, canvas, wire, transform)) return;
            if (wire.fill_rgba == null) return error.InvalidBatch;
            for (0..n) |i| {
                const base = i * 4;
                const center = Vec2{ .x = dataAt(wire, base), .y = dataAt(wire, base + 1) };
                const stroke: ?geometry.StrokeStyle = if (wire.stroke_rgba != null or wire.target_stroke_rgba != null)
                    .{ .color = strokeColorAt(wire, i), .width = strokeWidthAt(wire, i) }
                else
                    null;
                const object = geometry.Object2D{
                    .geometry = .{ .rectangle = try geometry.Rectangle.init(dataAt(wire, base + 2), dataAt(wire, base + 3)) },
                    .transform = transform.mul(Transform2D.identity.translate(center.x, center.y)),
                    .style = .{ .fill = fillAt(wire, i), .stroke = stroke },
                };
                try object.draw(ctx, canvas, Transform2D.identity);
            }
        },
    }
}
