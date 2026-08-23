const std = @import("std");
const math = @import("math.zig");

const Vec2 = math.Vec2;
const Linear2D = math.Linear2D;

const max_segments = 4096;
var segment_data: [max_segments * 4]f64 = undefined;

const Segment = struct { a: Vec2, b: Vec2 };
const Bounds = struct { min: Vec2, max: Vec2 };

export fn zanim_web_abi_version() u32 {
    return 1;
}

export fn zanim_web_grid_data_ptr() usize {
    return @intFromPtr(&segment_data);
}

export fn zanim_web_matrix_det(xx: f64, xy: f64, yx: f64, yy: f64) f64 {
    return Linear2D.init(xx, xy, yx, yy).determinant();
}

fn clipInfiniteLine(half: Vec2, p: Vec2, d: Vec2) ?Segment {
    const eps = 1e-14;
    if (d.x * d.x + d.y * d.y <= eps * eps) return null;

    var t0 = -std.math.inf(f64);
    var t1 = std.math.inf(f64);
    const axes = [_]struct { p: f64, d: f64, lo: f64, hi: f64 }{
        .{ .p = p.x, .d = d.x, .lo = -half.x, .hi = half.x },
        .{ .p = p.y, .d = d.y, .lo = -half.y, .hi = half.y },
    };
    for (axes) |axis| {
        if (@abs(axis.d) <= eps) {
            if (axis.p < axis.lo or axis.p > axis.hi) return null;
            continue;
        }
        var lo = (axis.lo - axis.p) / axis.d;
        var hi = (axis.hi - axis.p) / axis.d;
        if (lo > hi) std.mem.swap(f64, &lo, &hi);
        t0 = @max(t0, lo);
        t1 = @min(t1, hi);
        if (t0 > t1) return null;
    }
    return .{
        .a = .{ .x = p.x + d.x * t0, .y = p.y + d.y * t0 },
        .b = .{ .x = p.x + d.x * t1, .y = p.y + d.y * t1 },
    };
}

fn localBounds(half: Vec2, inverse: Linear2D) Bounds {
    const corners = [_]Vec2{
        .{ .x = -half.x, .y = -half.y },
        .{ .x = half.x, .y = -half.y },
        .{ .x = half.x, .y = half.y },
        .{ .x = -half.x, .y = half.y },
    };
    var min = inverse.apply(corners[0]);
    var max = min;
    for (corners[1..]) |corner| {
        const p = inverse.apply(corner);
        min.x = @min(min.x, p.x);
        min.y = @min(min.y, p.y);
        max.x = @max(max.x, p.x);
        max.y = @max(max.y, p.y);
    }
    return .{ .min = min, .max = max };
}

fn appendSegment(count: *usize, segment: Segment) void {
    if (count.* >= max_segments) return;
    const base = count.* * 4;
    segment_data[base] = segment.a.x;
    segment_data[base + 1] = segment.a.y;
    segment_data[base + 2] = segment.b.x;
    segment_data[base + 3] = segment.b.y;
    count.* += 1;
}

fn appendFamily(
    count: *usize,
    half: Vec2,
    matrix: Linear2D,
    bounds: Bounds,
    step: f64,
    vertical: bool,
) void {
    const min_value = if (vertical) bounds.min.x else bounds.min.y;
    const max_value = if (vertical) bounds.max.x else bounds.max.y;
    var first: i64 = @intFromFloat(@ceil(min_value / step - 1e-10));
    const last: i64 = @intFromFloat(@floor(max_value / step + 1e-10));
    if (last < first) return;

    // Bound work under pathological transforms. The browser renderer cannot
    // distinguish thousands of subpixel lines anyway.
    const family_count = last - first + 1;
    const max_family_lines: i64 = 1536;
    const stride: i64 = @max(1, @divTrunc(family_count + max_family_lines - 1, max_family_lines));
    const rem = @mod(first, stride);
    if (rem != 0) first += stride - rem;

    var k = first;
    while (k <= last and count.* < max_segments) : (k += stride) {
        const value = @as(f64, @floatFromInt(k)) * step;
        const local_point = if (vertical) Vec2{ .x = value, .y = 0 } else Vec2{ .x = 0, .y = value };
        const local_direction = if (vertical) Vec2{ .x = 0, .y = 1 } else Vec2{ .x = 1, .y = 0 };
        const p = matrix.apply(local_point);
        const d = matrix.apply(local_direction);
        if (clipInfiniteLine(half, p, d)) |segment| appendSegment(count, segment);
        if (last - k < stride) break;
    }
}

/// Resolve an exact infinite origin-centered square grid into the line segments
/// visible in the current logical viewport. Returned segments live in a stable
/// WASM buffer exposed by `zanim_web_grid_data_ptr`.
export fn zanim_web_resolve_grid(
    width_px: u32,
    height_px: u32,
    unit_size: f64,
    step: f64,
    xx: f64,
    xy: f64,
    yx: f64,
    yy: f64,
) u32 {
    if (width_px == 0 or height_px == 0 or !(unit_size > 0) or !(step > 0)) return 0;
    const matrix = Linear2D.init(xx, xy, yx, yy);
    const half = Vec2{
        .x = @as(f64, @floatFromInt(width_px)) / (2.0 * unit_size),
        .y = @as(f64, @floatFromInt(height_px)) / (2.0 * unit_size),
    };
    var count: usize = 0;

    if (@abs(matrix.determinant()) <= 1e-12) {
        // A rank-1 linear image of the complete grid lies on one carrier line.
        const dx = matrix.apply(.{ .x = 1, .y = 0 });
        const dy = matrix.apply(.{ .x = 0, .y = 1 });
        const direction = if (dx.x * dx.x + dx.y * dx.y >= dy.x * dy.x + dy.y * dy.y) dx else dy;
        if (clipInfiniteLine(half, .{}, direction)) |segment| appendSegment(&count, segment);
        return @intCast(count);
    }

    const inverse = matrix.inverse() catch return 0;
    const bounds = localBounds(half, inverse);
    appendFamily(&count, half, matrix, bounds, step, true);
    appendFamily(&count, half, matrix, bounds, step, false);
    return @intCast(count);
}

test "web grid resolver has visible identity segments" {
    const count = zanim_web_resolve_grid(1280, 720, 100, 0.5, 1, 0, 0, 1);
    try std.testing.expect(count > 20);
}

test "web grid resolver collapses singular plane to one carrier" {
    const count = zanim_web_resolve_grid(1280, 720, 100, 0.5, 1, 0.65, 0, 0);
    try std.testing.expectEqual(@as(u32, 1), count);
}

const fractal_max_width = 960;
const fractal_max_height = 540;
var fractal_pixels: [fractal_max_width * fractal_max_height * 4]u8 = undefined;

const Complex = struct {
    re: f64,
    im: f64,
    fn init(re: f64, im: f64) Complex { return .{ .re = re, .im = im }; }
    fn add(a: Complex, b: Complex) Complex { return .{ .re = a.re + b.re, .im = a.im + b.im }; }
    fn sub(a: Complex, b: Complex) Complex { return .{ .re = a.re - b.re, .im = a.im - b.im }; }
    fn scale(a: Complex, k: f64) Complex { return .{ .re = a.re * k, .im = a.im * k }; }
    fn mul(a: Complex, b: Complex) Complex { return .{ .re = a.re*b.re-a.im*b.im, .im = a.re*b.im+a.im*b.re }; }
    fn abs2(self: Complex) f64 { return self.re * self.re + self.im * self.im; }
    fn abs(self: Complex) f64 { return @sqrt(self.abs2()); }
    fn div(a: Complex, b: Complex) ?Complex {
        const d=b.abs2(); if (!(d>1e-300) or !std.math.isFinite(d)) return null;
        return .{ .re=(a.re*b.re+a.im*b.im)/d, .im=(a.im*b.re-a.re*b.im)/d };
    }
    fn sqrtPrincipal(a: Complex) Complex {
        if (a.re==0 and a.im==0) return .{.re=0,.im=0};
        const r=a.abs(); const x=@sqrt(@max(0.0,(r+a.re)*0.5)); var y=@sqrt(@max(0.0,(r-a.re)*0.5)); if(a.im<0)y=-y; return .{.re=x,.im=y};
    }
    fn logPrincipal(a: Complex) ?Complex { const r2=a.abs2(); if(!(r2>1e-300) or !std.math.isFinite(r2)) return null; return .{.re=0.5*@log(r2),.im=std.math.atan2(a.im,a.re)}; }
    fn exp(a: Complex) Complex { const e=@exp(a.re); return .{.re=e*@cos(a.im),.im=e*@sin(a.im)}; }
    fn powReal(a: Complex,t:f64) ?Complex { const l=a.logPrincipal() orelse return null; return l.scale(t).exp(); }
    fn squareAdd(self: Complex, c: Complex) Complex { return .{ .re = self.re * self.re - self.im * self.im + c.re, .im = 2.0 * self.re * self.im + c.im }; }
};

fn webMandelbrotInside(c: Complex) bool {
    const x = c.re;
    const y2 = c.im * c.im;
    const xm = x - 0.25;
    const q = xm * xm + y2;
    if (q * (q + xm) <= 0.25 * y2) return true;
    const xp = x + 1.0;
    return xp * xp + y2 <= 0.0625;
}

fn byteChannel(v: f64) u8 { return @intFromFloat(@round(@max(0.0, @min(255.0, v)))); }

fn webFractalColor(mu: f64, shift: f64, scale: f64, tint_r: u8, tint_g: u8, tint_b: u8, out: *[4]u8) void {
    const tau = 2.0 * std.math.pi;
    const phase_value = shift + mu * 0.021 * scale;
    const tr = 0.35 + 0.65 * (@as(f64, @floatFromInt(tint_r)) / 255.0);
    const tg = 0.35 + 0.65 * (@as(f64, @floatFromInt(tint_g)) / 255.0);
    const tb = 0.35 + 0.65 * (@as(f64, @floatFromInt(tint_b)) / 255.0);
    out[0] = byteChannel(255.0 * tr * (0.5 + 0.5 * @cos(tau * (phase_value + 0.00))));
    out[1] = byteChannel(255.0 * tg * (0.5 + 0.5 * @cos(tau * (phase_value + 0.12))));
    out[2] = byteChannel(255.0 * tb * (0.5 + 0.5 * @cos(tau * (phase_value + 0.24))));
    out[3] = 255;
}

export fn zanim_web_fractal_data_ptr() usize {
    return @intFromPtr(&fractal_pixels);
}

/// Render Mandelbrot (kind=1) or Julia (kind=2) into a stable RGBA8 buffer.
/// `world_per_pixel` controls viewport scale and keeps the API independent of Canvas DPR.
export fn zanim_web_render_fractal(
    kind: u32,
    width: u32,
    height: u32,
    center_re: f64,
    center_im: f64,
    world_per_pixel: f64,
    max_iter: u32,
    julia_re: f64,
    julia_im: f64,
    color_shift: f64,
    color_scale: f64,
    inside_r: u32,
    inside_g: u32,
    inside_b: u32,
    palette_r: u32,
    palette_g: u32,
    palette_b: u32,
) u32 {
    if ((kind != 1 and kind != 2) or width == 0 or height == 0 or width > fractal_max_width or height > fractal_max_height or
        !(world_per_pixel > 0.0) or max_iter == 0 or max_iter > 20_000 or !(color_scale > 0.0) or
        inside_r > 255 or inside_g > 255 or inside_b > 255 or palette_r > 255 or palette_g > 255 or palette_b > 255) return 0;
    const w: usize = @intCast(width);
    const h: usize = @intCast(height);
    const escape2 = 4.0;
    const jc = Complex{ .re = julia_re, .im = julia_im };
    for (0..h) |y| {
        const im = center_im - (@as(f64, @floatFromInt(y)) + 0.5 - @as(f64, @floatFromInt(height)) * 0.5) * world_per_pixel;
        for (0..w) |x| {
            const re = center_re + (@as(f64, @floatFromInt(x)) + 0.5 - @as(f64, @floatFromInt(width)) * 0.5) * world_per_pixel;
            const point = Complex{ .re = re, .im = im };
            const base = (y * w + x) * 4;
            if (kind == 1 and webMandelbrotInside(point)) {
                fractal_pixels[base] = @intCast(inside_r); fractal_pixels[base + 1] = @intCast(inside_g); fractal_pixels[base + 2] = @intCast(inside_b); fractal_pixels[base + 3] = 255;
                continue;
            }
            var z = if (kind == 1) Complex{ .re = 0, .im = 0 } else point;
            const c = if (kind == 1) point else jc;
            var escaped = false;
            var iter: u32 = 0;
            while (iter < max_iter) : (iter += 1) {
                z = z.squareAdd(c);
                if (z.abs2() > escape2) { escaped = true; iter += 1; break; }
            }
            if (!escaped) {
                fractal_pixels[base] = @intCast(inside_r); fractal_pixels[base + 1] = @intCast(inside_g); fractal_pixels[base + 2] = @intCast(inside_b); fractal_pixels[base + 3] = 255;
            } else {
                const mag2 = @max(z.abs2(), 1.0000000001);
                const log_abs = 0.5 * @log(mag2);
                var mu: f64 = @floatFromInt(iter);
                if (log_abs > 0.0 and std.math.isFinite(log_abs)) {
                    const nu = @log(log_abs / @log(2.0)) / @log(2.0);
                    const candidate = @as(f64, @floatFromInt(iter)) + 1.0 - nu;
                    if (std.math.isFinite(candidate)) mu = candidate;
                }
                var rgba: [4]u8 = undefined;
                webFractalColor(mu, color_shift, color_scale, @intCast(palette_r), @intCast(palette_g), @intCast(palette_b), &rgba);
                fractal_pixels[base] = rgba[0]; fractal_pixels[base + 1] = rgba[1]; fractal_pixels[base + 2] = rgba[2]; fractal_pixels[base + 3] = rgba[3];
            }
        }
    }
    return width * height;
}

test "web Mandelbrot field renders rgba pixels" {
    const count = zanim_web_render_fractal(1, 64, 36, -0.5, 0, 3.2 / 64.0, 80, 0, 0, 0.0, 1.0, 5, 7, 14, 105, 185, 255);
    try std.testing.expectEqual(@as(u32, 64 * 36), count);
    try std.testing.expect(fractal_pixels[3] == 255);
}

const WebPreimage = struct { z: Complex, deriv: Complex };
const WebPreimages = struct {
    values: [2]WebPreimage = undefined,
    len: usize = 0,
    fn add(self: *WebPreimages, z: Complex, deriv: Complex) void {
        if (self.len >= 2) return;
        if (!std.math.isFinite(z.re) or !std.math.isFinite(z.im) or !std.math.isFinite(deriv.re) or !std.math.isFinite(deriv.im)) return;
        self.values[self.len] = .{ .z=z, .deriv=deriv }; self.len += 1;
    }
};

fn webInverseSquare(w: Complex, progress_raw: f64) WebPreimages {
    var out = WebPreimages{};
    const a = @max(0.0, @min(1.0, progress_raw));
    if (a <= 1e-10) {
        out.add(w, .{ .re = 1, .im = 0 });
        return out;
    }
    const bb = 1.0 - a;
    const disc = Complex.init(bb * bb, 0).add(w.scale(4.0 * a));
    const root = disc.sqrtPrincipal();
    const denom = 2.0 * a;
    const z0 = Complex.init(-bb, 0).add(root).scale(1.0 / denom);
    const z1 = Complex.init(-bb, 0).sub(root).scale(1.0 / denom);
    out.add(z0, Complex.init(bb, 0).add(z0.scale(2.0 * a)));
    if (root.abs2() > 1e-24) out.add(z1, Complex.init(bb, 0).add(z1.scale(2.0 * a)));
    return out;
}

fn webInverseReciprocal(w: Complex, progress_raw: f64) WebPreimages {
    var out = WebPreimages{};
    const th = @max(0.0, @min(1.0, progress_raw)) * std.math.pi * 0.5;
    const c = @cos(th);
    const ss = @sin(th);
    const num = w.scale(c).sub(.{ .re = 0, .im = ss });
    const den = Complex.init(c, 0).sub(Complex.init(0, ss).mul(w));
    const z = num.div(den) orelse return out;
    const fd = Complex.init(0, ss).mul(z).add(.{ .re = c, .im = 0 });
    const der = Complex.init(1, 0).div(fd.mul(fd)) orelse return out;
    out.add(z, der);
    return out;
}

fn webInverseExp(w: Complex, k: Complex) WebPreimages {
    var out = WebPreimages{};
    const v = w.add(.{ .re = 1, .im = 0 });
    if (k.abs2() <= 1e-24) {
        const z = v.logPrincipal() orelse return out;
        out.add(z, v);
        return out;
    }
    const disc = v.mul(v).sub(k.scale(4.0));
    const root = disc.sqrtPrincipal();
    const root_u0 = v.add(root).scale(0.5);
    const root_u1 = v.sub(root).scale(0.5);
    if (root_u0.logPrincipal()) |z| {
        const rt = k.div(root_u0) orelse Complex.init(0, 0);
        out.add(z, root_u0.sub(rt));
    }
    if (root.abs2() > 1e-24) {
        if (root_u1.logPrincipal()) |z| {
            const rt = k.div(root_u1) orelse Complex.init(0, 0);
            out.add(z, root_u1.sub(rt));
        }
    }
    return out;
}

fn webMobiusPath(target: [8]f64, p: f64) ?[8]f64 {
    const ta = Complex.init(target[0], target[1]);
    const tb = Complex.init(target[2], target[3]);
    const tc = Complex.init(target[4], target[5]);
    const td = Complex.init(target[6], target[7]);
    var a = ta;
    var b0 = tb;
    var c0 = tc;
    var d0 = td;
    const progress = @max(0.0, @min(1.0, p));
    if (progress < 1.0 - 1e-12) {
        const inv = Complex.init(1, 0).div(td) orelse return null;
        const aa = ta.mul(inv);
        const bb = tb.mul(inv);
        const cc = tc.mul(inv);
        const delta = aa.sub(bb.mul(cc));
        const sc = delta.powReal(progress) orelse return null;
        b0 = bb.scale(progress);
        c0 = cc.scale(progress);
        d0 = Complex.init(1, 0);
        a = sc.add(b0.mul(c0));
    } else if (td.abs2() > 1e-24) {
        const inv = Complex.init(1, 0).div(td).?;
        a = ta.mul(inv);
        b0 = tb.mul(inv);
        c0 = tc.mul(inv);
        d0 = Complex.init(1, 0);
    }
    return .{ a.re, a.im, b0.re, b0.im, c0.re, c0.im, d0.re, d0.im };
}

fn webInverseMobius(w: Complex, q: [8]f64) WebPreimages {
    var out = WebPreimages{};
    const a = Complex.init(q[0], q[1]);
    const b0 = Complex.init(q[2], q[3]);
    const c0 = Complex.init(q[4], q[5]);
    const d0 = Complex.init(q[6], q[7]);
    const det = a.mul(d0).sub(b0.mul(c0));
    const z = d0.mul(w).sub(b0).div(a.sub(c0.mul(w))) orelse return out;
    const fd = c0.mul(z).add(d0);
    const der = det.div(fd.mul(fd)) orelse return out;
    out.add(z, der);
    return out;
}

fn webGridDistance(v: f64, step: f64) f64 {
    const u = v / step;
    return @abs(u - @round(u)) * step;
}

fn webCoverage(dist: f64, width_world: f64, pixel: f64) f64 {
    if (!std.math.isFinite(dist)) return 0;
    const aa = pixel * 0.75;
    return @max(0.0, @min(1.0, (width_world * 0.5 + aa - dist) / @max(pixel, 1e-12)));
}

fn webBlendGrid(base: usize, cx: f64, cy: f64) void {
    const ax = @max(0.0, @min(1.0, cx)) * 0.86;
    const ay = @max(0.0, @min(1.0, cy)) * 0.86;
    const oa = ax + ay * (1.0 - ax);
    if (oa <= 1e-8) {
        fractal_pixels[base] = 0;
        fractal_pixels[base + 1] = 0;
        fractal_pixels[base + 2] = 0;
        fractal_pixels[base + 3] = 0;
        return;
    }
    const ox = [3]f64{ 255, 151, 92 };
    const yc = [3]f64{ 95, 218, 255 };
    fractal_pixels[base] = byteChannel((ox[0] * ax + yc[0] * ay * (1.0 - ax)) / oa);
    fractal_pixels[base + 1] = byteChannel((ox[1] * ax + yc[1] * ay * (1.0 - ax)) / oa);
    fractal_pixels[base + 2] = byteChannel((ox[2] * ax + yc[2] * ay * (1.0 - ax)) / oa);
    fractal_pixels[base + 3] = byteChannel(255.0 * oa);
}

/// Native inverse-mapped complex lattice. map_kind: 1 square, 2 exp, 3 reciprocal, 4 mobius.
export fn zanim_web_render_complex_grid(
    map_kind: u32,
    width: u32,
    height: u32,
    center_re: f64,
    center_im: f64,
    world_per_pixel: f64,
    step_x: f64,
    step_y: f64,
    progress: f64,
    stroke_px: f64,
    q0: f64,
    q1: f64,
    q2: f64,
    q3: f64,
    q4: f64,
    q5: f64,
    q6: f64,
    q7: f64,
) u32 {
    if (map_kind < 1 or map_kind > 4 or width == 0 or height == 0 or width > fractal_max_width or height > fractal_max_height or
        !(world_per_pixel > 0) or !(step_x > 0) or !(step_y > 0) or !(stroke_px > 0)) return 0;
    var q = [8]f64{ q0, q1, q2, q3, q4, q5, q6, q7 };
    const p0 = @max(0.0, @min(1.0, progress));
    if (map_kind == 2) {
        q[0] *= 1.0 - p0;
        q[1] *= 1.0 - p0;
    } else if (map_kind == 4) {
        q = webMobiusPath(q, p0) orelse return 0;
    }
    const w: usize = @intCast(width);
    const h: usize = @intCast(height);
    const stroke_world = stroke_px * world_per_pixel;
    for (0..h) |yy| {
        const im = center_im - (@as(f64, @floatFromInt(yy)) + 0.5 - @as(f64, @floatFromInt(height)) * 0.5) * world_per_pixel;
        for (0..w) |xx| {
            const re = center_re + (@as(f64, @floatFromInt(xx)) + 0.5 - @as(f64, @floatFromInt(width)) * 0.5) * world_per_pixel;
            const target = Complex.init(re, im);
            const roots = if (map_kind == 1)
                webInverseSquare(target, p0)
            else if (map_kind == 2)
                webInverseExp(target, Complex.init(q[0], q[1]))
            else if (map_kind == 3)
                webInverseReciprocal(target, p0)
            else
                webInverseMobius(target, q);
            var covx: f64 = 0;
            var covy: f64 = 0;
            for (roots.values[0..roots.len]) |root| {
                const local_scale = root.deriv.abs();
                covx = @max(covx, webCoverage(webGridDistance(root.z.re, step_x) * local_scale, stroke_world, world_per_pixel));
                covy = @max(covy, webCoverage(webGridDistance(root.z.im, step_y) * local_scale, stroke_world, world_per_pixel));
            }
            webBlendGrid((yy * w + xx) * 4, covx, covy);
        }
    }
    return width * height;
}

test "web complex square keeps both branches visible" {
    const roots=webInverseSquare(.{.re=4,.im=0},1);try std.testing.expectEqual(@as(usize,2),roots.len);
}
test "web complex grid produces transparent rgba layer" {
    const count=zanim_web_render_complex_grid(1,64,36,0,0,5.0/64.0,0.5,0.5,1,0.9,0,0,0,0,0,0,0,0);try std.testing.expectEqual(@as(u32,64*36),count);
}
