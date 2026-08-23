const std = @import("std");

pub const Complex = struct {
    re: f64,
    im: f64,

    pub fn init(re: f64, im: f64) Complex {
        return .{ .re = re, .im = im };
    }
    pub fn add(a: Complex, b: Complex) Complex {
        return .{ .re = a.re + b.re, .im = a.im + b.im };
    }
    pub fn sub(a: Complex, b: Complex) Complex {
        return .{ .re = a.re - b.re, .im = a.im - b.im };
    }
    pub fn scale(a: Complex, s: f64) Complex {
        return .{ .re = a.re * s, .im = a.im * s };
    }
    pub fn mul(a: Complex, b: Complex) Complex {
        return .{ .re = a.re * b.re - a.im * b.im, .im = a.re * b.im + a.im * b.re };
    }
    pub fn abs2(a: Complex) f64 {
        return a.re * a.re + a.im * a.im;
    }
    pub fn abs(a: Complex) f64 {
        return @sqrt(a.abs2());
    }
    pub fn div(a: Complex, b: Complex) ?Complex {
        const d = b.abs2();
        if (!(d > 1e-300) or !std.math.isFinite(d)) return null;
        return .{ .re = (a.re * b.re + a.im * b.im) / d, .im = (a.im * b.re - a.re * b.im) / d };
    }
    pub fn sqrtPrincipal(a: Complex) Complex {
        if (a.re == 0 and a.im == 0) return .{ .re = 0, .im = 0 };
        const r = a.abs();
        const x = @sqrt(@max(0.0, (r + a.re) * 0.5));
        var y = @sqrt(@max(0.0, (r - a.re) * 0.5));
        if (a.im < 0) y = -y;
        return .{ .re = x, .im = y };
    }
    pub fn logPrincipal(a: Complex) ?Complex {
        const r2 = a.abs2();
        if (!(r2 > 1e-300) or !std.math.isFinite(r2)) return null;
        return .{ .re = 0.5 * @log(r2), .im = std.math.atan2(a.im, a.re) };
    }
    pub fn exp(a: Complex) Complex {
        const e = @exp(a.re);
        return .{ .re = e * @cos(a.im), .im = e * @sin(a.im) };
    }
    pub fn powReal(a: Complex, t: f64) ?Complex {
        const l = a.logPrincipal() orelse return null;
        return l.scale(t).exp();
    }
    pub fn squareAdd(self: Complex, c: Complex) Complex {
        return .{ .re = self.re * self.re - self.im * self.im + c.re, .im = 2.0 * self.re * self.im + c.im };
    }
};

pub const FractalKind = enum(u32) { mandelbrot = 1, julia = 2 };
pub const Escape = struct { escaped: bool, iteration: u32, z: Complex };

pub fn insideMainMandelbrotComponents(c: Complex) bool {
    const x = c.re;
    const y2 = c.im * c.im;
    const xm = x - 0.25;
    const q = xm * xm + y2;
    if (q * (q + xm) <= 0.25 * y2) return true;
    const xp = x + 1.0;
    return xp * xp + y2 <= 0.0625;
}

pub fn fractalEscape(kind: FractalKind, point: Complex, julia_c: Complex, max_iter: u32, escape2: f64) Escape {
    if (kind == .mandelbrot and insideMainMandelbrotComponents(point)) return .{ .escaped = false, .iteration = max_iter, .z = .{ .re = 0, .im = 0 } };
    var z = if (kind == .mandelbrot) Complex{ .re = 0, .im = 0 } else point;
    const c = if (kind == .mandelbrot) point else julia_c;
    var i: u32 = 0;
    while (i < max_iter) : (i += 1) {
        z = z.squareAdd(c);
        if (z.abs2() > escape2) return .{ .escaped = true, .iteration = i + 1, .z = z };
    }
    return .{ .escaped = false, .iteration = max_iter, .z = z };
}

pub fn fractalSmoothIteration(result: Escape) f64 {
    const mag2 = @max(result.z.abs2(), 1.0000000001);
    const log_abs = 0.5 * @log(mag2);
    if (!(log_abs > 0.0) or !std.math.isFinite(log_abs)) return @floatFromInt(result.iteration);
    const nu = @log(log_abs / @log(2.0)) / @log(2.0);
    const value = @as(f64, @floatFromInt(result.iteration)) + 1.0 - nu;
    return if (std.math.isFinite(value)) value else @floatFromInt(result.iteration);
}

pub fn byteChannel(value: f64) u8 {
    return @intFromFloat(@round(@max(0.0, @min(255.0, value))));
}

pub fn fractalRgb(mu: f64, shift: f64, scale: f64, tint_r: u8, tint_g: u8, tint_b: u8) [3]u8 {
    const tau = 2.0 * std.math.pi;
    const phase = shift + mu * 0.021 * scale;
    const tr = 0.35 + 0.65 * (@as(f64, @floatFromInt(tint_r)) / 255.0);
    const tg = 0.35 + 0.65 * (@as(f64, @floatFromInt(tint_g)) / 255.0);
    const tb = 0.35 + 0.65 * (@as(f64, @floatFromInt(tint_b)) / 255.0);
    return .{
        byteChannel(255.0 * tr * (0.5 + 0.5 * @cos(tau * (phase + 0.00)))),
        byteChannel(255.0 * tg * (0.5 + 0.5 * @cos(tau * (phase + 0.12)))),
        byteChannel(255.0 * tb * (0.5 + 0.5 * @cos(tau * (phase + 0.24)))),
    };
}

pub const Preimage = struct { z: Complex, deriv: Complex };
pub const Preimages = struct {
    values: [2]Preimage = undefined,
    len: usize = 0,
    pub fn add(self: *Preimages, z: Complex, deriv: Complex) void {
        if (self.len >= self.values.len) return;
        if (!std.math.isFinite(z.re) or !std.math.isFinite(z.im) or !std.math.isFinite(deriv.re) or !std.math.isFinite(deriv.im)) return;
        self.values[self.len] = .{ .z = z, .deriv = deriv };
        self.len += 1;
    }
};

pub fn inverseSquare(w: Complex, progress_raw: f64) Preimages {
    var out = Preimages{};
    const a = @max(0.0, @min(1.0, progress_raw));
    if (a <= 1e-10) {
        out.add(w, .{ .re = 1, .im = 0 });
        return out;
    }
    const b = 1.0 - a;
    const disc = Complex.init(b * b, 0).add(w.scale(4.0 * a));
    const root = disc.sqrtPrincipal();
    const denom = 2.0 * a;
    const z0 = Complex.init(-b, 0).add(root).scale(1.0 / denom);
    const z1 = Complex.init(-b, 0).sub(root).scale(1.0 / denom);
    out.add(z0, Complex.init(b, 0).add(z0.scale(2.0 * a)));
    if (root.abs2() > 1e-24) out.add(z1, Complex.init(b, 0).add(z1.scale(2.0 * a)));
    return out;
}

pub fn inverseExp(w: Complex, k: Complex) Preimages {
    var out = Preimages{};
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
    if (root_u0.logPrincipal()) |z0| {
        const reciprocal_term = k.div(root_u0) orelse Complex.init(0, 0);
        out.add(z0, root_u0.sub(reciprocal_term));
    }
    if (root.abs2() > 1e-24) if (root_u1.logPrincipal()) |z1| {
        const reciprocal_term = k.div(root_u1) orelse Complex.init(0, 0);
        out.add(z1, root_u1.sub(reciprocal_term));
    };
    return out;
}

pub fn inverseReciprocal(w: Complex, progress_raw: f64) Preimages {
    var out = Preimages{};
    const theta = @max(0.0, @min(1.0, progress_raw)) * std.math.pi * 0.5;
    const c = @cos(theta);
    const s = @sin(theta);
    const numerator = w.scale(c).sub(.{ .re = 0, .im = s });
    const denominator = Complex.init(c, 0).sub(Complex.init(0, s).mul(w));
    const z = numerator.div(denominator) orelse return out;
    const forward_denom = Complex.init(0, s).mul(z).add(.{ .re = c, .im = 0 });
    const deriv = Complex.init(1, 0).div(forward_denom.mul(forward_denom)) orelse return out;
    out.add(z, deriv);
    return out;
}

pub fn inverseMobius(w: Complex, q: [8]f64) Preimages {
    var out = Preimages{};
    const a = Complex.init(q[0], q[1]);
    const b = Complex.init(q[2], q[3]);
    const c = Complex.init(q[4], q[5]);
    const d = Complex.init(q[6], q[7]);
    const det = a.mul(d).sub(b.mul(c));
    const z = d.mul(w).sub(b).div(a.sub(c.mul(w))) orelse return out;
    const forward_denom = c.mul(z).add(d);
    const deriv = det.div(forward_denom.mul(forward_denom)) orelse return out;
    out.add(z, deriv);
    return out;
}

pub fn mobiusPath(target: [8]f64, progress_raw: f64) ?[8]f64 {
    const target_a = Complex.init(target[0], target[1]);
    const target_b = Complex.init(target[2], target[3]);
    const target_c = Complex.init(target[4], target[5]);
    const target_d = Complex.init(target[6], target[7]);
    var a = target_a;
    var b = target_b;
    var c = target_c;
    var d = target_d;
    const progress = @max(0.0, @min(1.0, progress_raw));
    if (progress < 1.0 - 1e-12) {
        const inv_d = Complex.init(1, 0).div(target_d) orelse return null;
        const A = target_a.mul(inv_d);
        const B = target_b.mul(inv_d);
        const C = target_c.mul(inv_d);
        const delta = A.sub(B.mul(C));
        const scale = delta.powReal(progress) orelse return null;
        b = B.scale(progress);
        c = C.scale(progress);
        d = Complex.init(1, 0);
        a = scale.add(b.mul(c));
    } else if (target_d.abs2() > 1e-24) {
        const inv_d = Complex.init(1, 0).div(target_d).?;
        a = target_a.mul(inv_d);
        b = target_b.mul(inv_d);
        c = target_c.mul(inv_d);
        d = Complex.init(1, 0);
    }
    return .{ a.re, a.im, b.re, b.im, c.re, c.im, d.re, d.im };
}

pub fn gridDistance(value: f64, origin: f64, step: f64) f64 {
    const u = (value - origin) / step;
    return @abs(u - @round(u)) * step;
}

pub fn coverageForDistance(distance: f64, width: f64, pixel_size: f64) f64 {
    if (!std.math.isFinite(distance)) return 0.0;
    const aa = pixel_size * 0.75;
    return @max(0.0, @min(1.0, (width * 0.5 + aa - distance) / @max(pixel_size, 1e-12)));
}

test "shared fractal and complex kernels" {
    try std.testing.expect(insideMainMandelbrotComponents(.{ .re = 0, .im = 0 }));
    try std.testing.expect(fractalEscape(.mandelbrot, .{ .re = 2, .im = 2 }, .{ .re = 0, .im = 0 }, 100, 4).escaped);
    try std.testing.expectEqual(@as(usize, 2), inverseSquare(.{ .re = 4, .im = 0 }, 1).len);
}
