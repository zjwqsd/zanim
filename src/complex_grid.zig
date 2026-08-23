const std = @import("std");
const z2d = @import("z2d");
const canvas_mod = @import("canvas.zig");
const geometry = @import("geometry.zig");
const math = @import("math.zig");

const Canvas = canvas_mod.Canvas;
const Transform2D = math.Transform2D;
const Vec2 = math.Vec2;

pub const MapKind = enum(u32) {
    square = 1,
    exp = 2,
    reciprocal = 3,
    mobius = 4,
};

pub const Params = struct {
    origin: Vec2,
    step: Vec2,
    map_kind: u32,
    progress: f64,
    map_params: [8]f64,
    transform: Transform2D,
    x_color: geometry.Color,
    y_color: geometry.Color,
    stroke_width: f64,
};

const C = struct {
    re: f64,
    im: f64,

    fn init(re: f64, im: f64) C {
        return .{ .re = re, .im = im };
    }
    fn add(a: C, b: C) C {
        return .{ .re = a.re + b.re, .im = a.im + b.im };
    }
    fn sub(a: C, b: C) C {
        return .{ .re = a.re - b.re, .im = a.im - b.im };
    }
    fn scale(a: C, s: f64) C {
        return .{ .re = a.re * s, .im = a.im * s };
    }
    fn mul(a: C, b: C) C {
        return .{ .re = a.re * b.re - a.im * b.im, .im = a.re * b.im + a.im * b.re };
    }
    fn abs2(a: C) f64 {
        return a.re * a.re + a.im * a.im;
    }
    fn abs(a: C) f64 {
        return @sqrt(a.abs2());
    }
    fn div(a: C, b: C) ?C {
        const d = b.abs2();
        if (!(d > 1e-300) or !std.math.isFinite(d)) return null;
        return .{
            .re = (a.re * b.re + a.im * b.im) / d,
            .im = (a.im * b.re - a.re * b.im) / d,
        };
    }
    fn sqrtPrincipal(a: C) C {
        if (a.re == 0.0 and a.im == 0.0) return .{ .re = 0, .im = 0 };
        const r = a.abs();
        const x = @sqrt(@max(0.0, (r + a.re) * 0.5));
        var y = @sqrt(@max(0.0, (r - a.re) * 0.5));
        if (a.im < 0) y = -y;
        return .{ .re = x, .im = y };
    }
    fn logPrincipal(a: C) ?C {
        const r2 = a.abs2();
        if (!(r2 > 1e-300) or !std.math.isFinite(r2)) return null;
        return .{ .re = 0.5 * @log(r2), .im = std.math.atan2(a.im, a.re) };
    }
    fn exp(a: C) C {
        const er = @exp(a.re);
        return .{ .re = er * @cos(a.im), .im = er * @sin(a.im) };
    }
    fn powReal(a: C, t: f64) ?C {
        const l = a.logPrincipal() orelse return null;
        return l.scale(t).exp();
    }
};

const Preimage = struct { z: C, deriv: C };
const Preimages = struct {
    values: [2]Preimage = undefined,
    len: usize = 0,

    fn add(self: *Preimages, z: C, deriv: C) void {
        if (self.len >= self.values.len) return;
        if (!std.math.isFinite(z.re) or !std.math.isFinite(z.im) or
            !std.math.isFinite(deriv.re) or !std.math.isFinite(deriv.im)) return;
        self.values[self.len] = .{ .z = z, .deriv = deriv };
        self.len += 1;
    }
};

fn inverseSquare(w: C, progress_raw: f64) Preimages {
    var out = Preimages{};
    const a = @max(0.0, @min(1.0, progress_raw));
    if (a <= 1e-10) {
        out.add(w, .{ .re = 1, .im = 0 });
        return out;
    }
    const b = 1.0 - a;
    // a*z^2 + b*z - w = 0
    const disc = C.init(b * b, 0).add(w.scale(4.0 * a));
    const root = disc.sqrtPrincipal();
    const denom = 2.0 * a;
    const z0 = C.init(-b, 0).add(root).scale(1.0 / denom);
    const z1 = C.init(-b, 0).sub(root).scale(1.0 / denom);
    out.add(z0, C.init(b, 0).add(z0.scale(2.0 * a)));
    // At a double root both preimages coincide; adding once avoids double blend.
    if (root.abs2() > 1e-24) out.add(z1, C.init(b, 0).add(z1.scale(2.0 * a)));
    return out;
}

fn inverseExp(w: C, q: [8]f64) Preimages {
    var out = Preimages{};
    const k = C.init(q[0], q[1]);
    const v = w.add(.{ .re = 1, .im = 0 });

    // F_p(z) = exp(z) - 1 + (1-p) * lambda * exp(-z).
    // Writing u=exp(z) gives u^2 - (w+1)u + k = 0.  The map is
    // 2*pi*i-periodic for every p, so when source y-step divides 2*pi,
    // one principal logarithm per non-zero u root represents every branch.
    if (k.abs2() <= 1e-24) {
        const z = v.logPrincipal() orelse return out;
        out.add(z, v);
        return out;
    }

    const disc = v.mul(v).sub(k.scale(4.0));
    const root = disc.sqrtPrincipal();
    const root_u0 = v.add(root).scale(0.5);
    const root_u1 = v.sub(root).scale(0.5);

    if (root_u0.logPrincipal()) |z0| {
        const reciprocal_term = k.div(root_u0) orelse C.init(0, 0);
        out.add(z0, root_u0.sub(reciprocal_term));
    }
    if (root.abs2() > 1e-24) {
        if (root_u1.logPrincipal()) |z1| {
            const reciprocal_term = k.div(root_u1) orelse C.init(0, 0);
            out.add(z1, root_u1.sub(reciprocal_term));
        }
    }
    return out;
}

fn inverseReciprocal(w: C, progress_raw: f64) Preimages {
    var out = Preimages{};
    const theta = @max(0.0, @min(1.0, progress_raw)) * std.math.pi * 0.5;
    const c = @cos(theta);
    const s = @sin(theta);
    // f(z) = (c*z + i*s)/(i*s*z + c), det=1.
    // inverse: z = (c*w - i*s)/(-i*s*w + c)
    const numerator = w.scale(c).sub(.{ .re = 0, .im = s });
    const denominator = C.init(c, 0).sub(C.init(0, s).mul(w));
    const z = numerator.div(denominator) orelse return out;
    const forward_denom = C.init(0, s).mul(z).add(.{ .re = c, .im = 0 });
    const deriv = C.init(1, 0).div(forward_denom.mul(forward_denom)) orelse return out;
    out.add(z, deriv);
    return out;
}

fn inverseMobius(w: C, q: [8]f64) Preimages {
    var out = Preimages{};
    const a = C.init(q[0], q[1]);
    const b = C.init(q[2], q[3]);
    const c = C.init(q[4], q[5]);
    const d = C.init(q[6], q[7]);
    const det = a.mul(d).sub(b.mul(c));
    const numerator = d.mul(w).sub(b);
    const denominator = a.sub(c.mul(w));
    const z = numerator.div(denominator) orelse return out;
    const forward_denom = c.mul(z).add(d);
    const deriv = det.div(forward_denom.mul(forward_denom)) orelse return out;
    out.add(z, deriv);
    return out;
}

fn prepare(params_raw: Params) ?Params {
    var params = params_raw;
    const kind: MapKind = switch (params.map_kind) {
        1 => .square,
        2 => .exp,
        3 => .reciprocal,
        4 => .mobius,
        else => return null,
    };
    const progress = @max(0.0, @min(1.0, params.progress));
    switch (kind) {
        .exp => {
            // Store k=(1-p)*lambda once per frame.
            params.map_params[0] *= 1.0 - progress;
            params.map_params[1] *= 1.0 - progress;
        },
        .mobius => {
            const target_a = C.init(params.map_params[0], params.map_params[1]);
            const target_b = C.init(params.map_params[2], params.map_params[3]);
            const target_c = C.init(params.map_params[4], params.map_params[5]);
            const target_d = C.init(params.map_params[6], params.map_params[7]);

            var a = target_a;
            var b = target_b;
            var c = target_c;
            var d = target_d;
            if (progress < 1.0 - 1e-12) {
                const inv_d = C.init(1, 0).div(target_d) orelse return null;
                const A = target_a.mul(inv_d);
                const B = target_b.mul(inv_d);
                const Cc = target_c.mul(inv_d);
                const delta = A.sub(B.mul(Cc));
                const scale = delta.powReal(progress) orelse return null;
                b = B.scale(progress);
                c = Cc.scale(progress);
                d = C.init(1, 0);
                a = scale.add(b.mul(c));
            } else if (target_d.abs2() > 1e-24) {
                const inv_d = C.init(1, 0).div(target_d).?;
                a = target_a.mul(inv_d);
                b = target_b.mul(inv_d);
                c = target_c.mul(inv_d);
                d = C.init(1, 0);
            }
            params.map_params = .{ a.re, a.im, b.re, b.im, c.re, c.im, d.re, d.im };
        },
        else => {},
    }
    return params;
}

fn preimages(w: C, params: Params) ?Preimages {
    const kind: MapKind = switch (params.map_kind) {
        1 => .square,
        2 => .exp,
        3 => .reciprocal,
        4 => .mobius,
        else => return null,
    };
    return switch (kind) {
        .square => inverseSquare(w, params.progress),
        .exp => inverseExp(w, params.map_params),
        .reciprocal => inverseReciprocal(w, params.progress),
        .mobius => inverseMobius(w, params.map_params),
    };
}

fn nearestGridDistance(value: f64, origin: f64, step: f64) f64 {
    const u = (value - origin) / step;
    return @abs(u - @round(u)) * step;
}

fn sourceDistanceToView(
    delta: f64,
    source_normal_x: bool,
    deriv: C,
    transform: Transform2D,
) f64 {
    // B = A * J_f maps source tangent vectors into current view coordinates.
    const jxx = deriv.re;
    const jxy = -deriv.im;
    const jyx = deriv.im;
    const jyy = deriv.re;
    const bxx = transform.xx * jxx + transform.xy * jyx;
    const bxy = transform.xx * jxy + transform.xy * jyy;
    const byx = transform.yx * jxx + transform.yy * jyx;
    const byy = transform.yx * jxy + transform.yy * jyy;
    const det = bxx * byy - bxy * byx;
    if (@abs(det) <= 1e-20) return if (delta <= 1e-12) 0.0 else std.math.inf(f64);

    const ixx = byy / det;
    const ixy = -bxy / det;
    const iyx = -byx / det;
    const iyy = bxx / det;
    // grad_q(source_x) = B^-T e_x = (ixx, ixy)
    // grad_q(source_y) = B^-T e_y = (iyx, iyy)
    const gx = if (source_normal_x) ixx else iyx;
    const gy = if (source_normal_x) ixy else iyy;
    const grad_len = @sqrt(gx * gx + gy * gy);
    if (!(grad_len > 1e-20) or !std.math.isFinite(grad_len)) return std.math.inf(f64);
    return delta / grad_len;
}

fn coverageForDistance(distance: f64, width: f64, pixel_size: f64) f64 {
    if (!std.math.isFinite(distance)) return 0.0;
    const aa = pixel_size * 0.75;
    return @max(0.0, @min(1.0, (width * 0.5 + aa - distance) / @max(pixel_size, 1e-12)));
}

fn effectiveColor(color: geometry.Color, coverage: f64) geometry.Color {
    var out = color;
    out.a = @intFromFloat(@round(@as(f64, @floatFromInt(out.a)) * @max(0.0, @min(1.0, coverage))));
    return out;
}

fn blendRgb(dst: z2d.pixel.RGB, color: geometry.Color, coverage: f64) z2d.pixel.RGB {
    const c = effectiveColor(color, coverage);
    if (c.a == 0) return dst;
    const src = (z2d.pixel.RGBA{ .r = c.r, .g = c.g, .b = c.b, .a = c.a }).multiply();
    return z2d.compositor.runPixelT(z2d.pixel.RGB, dst, z2d.pixel.RGBA, src, .src_over);
}

fn blendRgba(dst: z2d.pixel.RGBA, color: geometry.Color, coverage: f64) z2d.pixel.RGBA {
    const c = effectiveColor(color, coverage);
    if (c.a == 0) return dst;
    const src = (z2d.pixel.RGBA{ .r = c.r, .g = c.g, .b = c.b, .a = c.a }).multiply();
    return z2d.compositor.runPixelT(z2d.pixel.RGBA, dst, z2d.pixel.RGBA, src, .src_over);
}

fn pixelCoverage(view: Vec2, inverse_transform: Transform2D, params: Params, pixel_size: f64) struct { x: f64, y: f64 } {
    const local = inverse_transform.applyPoint(view);
    const roots = preimages(C.init(local.x, local.y), params) orelse return .{ .x = 0, .y = 0 };
    var cov_x: f64 = 0.0;
    var cov_y: f64 = 0.0;
    for (roots.values[0..roots.len]) |root| {
        const dx = nearestGridDistance(root.z.re, params.origin.x, params.step.x);
        const dy = nearestGridDistance(root.z.im, params.origin.y, params.step.y);
        const view_dx = sourceDistanceToView(dx, true, root.deriv, params.transform);
        const view_dy = sourceDistanceToView(dy, false, root.deriv, params.transform);
        cov_x = @max(cov_x, coverageForDistance(view_dx, params.stroke_width, pixel_size));
        cov_y = @max(cov_y, coverageForDistance(view_dy, params.stroke_width, pixel_size));
    }
    return .{ .x = cov_x, .y = cov_y };
}

pub fn draw(ctx: *z2d.Context, canvas: Canvas, params_raw: Params) !void {
    if (!(params_raw.step.x > 0) or !(params_raw.step.y > 0) or !(params_raw.stroke_width > 0))
        return error.InvalidComplexGrid;
    const params = prepare(params_raw) orelse return error.InvalidComplexGrid;
    const inverse = params.transform.inverse() catch return error.InvalidComplexGrid;
    const pixel_size = 1.0 / canvas.unit_size;
    const width: usize = @intCast(canvas.width);
    const height: usize = @intCast(canvas.height);
    switch (ctx.surface.*) {
        .image_surface_rgb => |*surface| {
            for (0..height) |y| {
                const vy = -((@as(f64, @floatFromInt(y)) + 0.5) - canvas.origin_device.y) / canvas.unit_size;
                for (0..width) |x| {
                    const vx = ((@as(f64, @floatFromInt(x)) + 0.5) - canvas.origin_device.x) / canvas.unit_size;
                    const cov = pixelCoverage(.{ .x = vx, .y = vy }, inverse, params, pixel_size);
                    if (cov.x <= 0 and cov.y <= 0) continue;
                    const index = y * width + x;
                    var px = surface.buf[index];
                    // x=constant source lines use x_color; y=constant use y_color.
                    if (cov.x > 0) px = blendRgb(px, params.x_color, cov.x);
                    if (cov.y > 0) px = blendRgb(px, params.y_color, cov.y);
                    surface.buf[index] = px;
                }
            }
        },
        .image_surface_rgba => |*surface| {
            for (0..height) |y| {
                const vy = -((@as(f64, @floatFromInt(y)) + 0.5) - canvas.origin_device.y) / canvas.unit_size;
                for (0..width) |x| {
                    const vx = ((@as(f64, @floatFromInt(x)) + 0.5) - canvas.origin_device.x) / canvas.unit_size;
                    const cov = pixelCoverage(.{ .x = vx, .y = vy }, inverse, params, pixel_size);
                    if (cov.x <= 0 and cov.y <= 0) continue;
                    const index = y * width + x;
                    var px = surface.buf[index];
                    if (cov.x > 0) px = blendRgba(px, params.x_color, cov.x);
                    if (cov.y > 0) px = blendRgba(px, params.y_color, cov.y);
                    surface.buf[index] = px;
                }
            }
        },
        else => return error.UnsupportedComplexGridSurface,
    }
}

test "square inverse includes both branches" {
    const roots = inverseSquare(.{ .re = 4, .im = 0 }, 1.0);
    try std.testing.expectEqual(@as(usize, 2), roots.len);
    try std.testing.expectApproxEqAbs(@as(f64, 2), @abs(roots.values[0].z.re), 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 2), @abs(roots.values[1].z.re), 1e-12);
}

test "reciprocal homotopy endpoints are identity and reciprocal" {
    const w = C.init(2, 1);
    const start = inverseReciprocal(w, 0).values[0].z;
    try std.testing.expectApproxEqAbs(w.re, start.re, 1e-12);
    try std.testing.expectApproxEqAbs(w.im, start.im, 1e-12);
    const end = inverseReciprocal(w, 1).values[0].z;
    const expected = C.init(1, 0).div(w).?;
    try std.testing.expectApproxEqAbs(expected.re, end.re, 1e-12);
    try std.testing.expectApproxEqAbs(expected.im, end.im, 1e-12);
}

test "exp homotopy endpoints are cosh warp and exp" {
    const q = [_]f64{ 1, 0, 0, 0, 0, 0, 0, 0 };
    const w = C.init(0.7, -0.2);
    const end = inverseExp(w, prepare(.{ .origin = .{ .x = 0, .y = 0 }, .step = .{ .x = 1, .y = 1 }, .map_kind = 2, .progress = 1.0, .map_params = q, .transform = Transform2D.identity, .x_color = .{ .r = 0, .g = 0, .b = 0, .a = 255 }, .y_color = .{ .r = 0, .g = 0, .b = 0, .a = 255 }, .stroke_width = 1 }).?.map_params);
    try std.testing.expectEqual(@as(usize, 1), end.len);
    const u = end.values[0].z.exp();
    try std.testing.expectApproxEqAbs(w.re, u.re - 1.0, 1e-10);
    try std.testing.expectApproxEqAbs(w.im, u.im, 1e-10);

    const start = inverseExp(w, q);
    try std.testing.expect(start.len >= 1);
    for (start.values[0..start.len]) |root| {
        const ez = root.z.exp();
        const emz = C.init(1, 0).div(ez).?;
        const fw = ez.add(emz).sub(C.init(1, 0));
        try std.testing.expectApproxEqAbs(w.re, fw.re, 1e-9);
        try std.testing.expectApproxEqAbs(w.im, fw.im, 1e-9);
    }
}

test "mobius Gauss path endpoints are identity and target" {
    const q = [_]f64{ 1.069, -0.111, 0.55, -0.25, 0.18, -0.12, 1, 0 };
    const base = Params{
        .origin = .{ .x = 0, .y = 0 },
        .step = .{ .x = 1, .y = 1 },
        .map_kind = 4,
        .progress = 0,
        .map_params = q,
        .transform = Transform2D.identity,
        .x_color = .{ .r = 0, .g = 0, .b = 0, .a = 255 },
        .y_color = .{ .r = 0, .g = 0, .b = 0, .a = 255 },
        .stroke_width = 1,
    };
    const w = C.init(0.4, -0.3);
    const start_q = prepare(base).?.map_params;
    const start = inverseMobius(w, start_q).values[0].z;
    try std.testing.expectApproxEqAbs(w.re, start.re, 1e-12);
    try std.testing.expectApproxEqAbs(w.im, start.im, 1e-12);

    var end_params = base;
    end_params.progress = 1;
    const end_q = prepare(end_params).?.map_params;
    const end = inverseMobius(w, end_q).values[0].z;
    const a = C.init(q[0], q[1]);
    const bb = C.init(q[2], q[3]);
    const c = C.init(q[4], q[5]);
    const d = C.init(q[6], q[7]);
    const expected = d.mul(w).sub(bb).div(a.sub(c.mul(w))).?;
    try std.testing.expectApproxEqAbs(expected.re, end.re, 1e-12);
    try std.testing.expectApproxEqAbs(expected.im, end.im, 1e-12);
}
