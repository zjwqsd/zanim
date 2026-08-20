const std = @import("std");

pub const Vec2 = struct {
    x: f64 = 0.0,
    y: f64 = 0.0,

    pub fn lerp(a: Vec2, b: Vec2, t: f64) Vec2 {
        return .{
            .x = a.x + (b.x - a.x) * t,
            .y = a.y + (b.y - a.y) * t,
        };
    }
};

/// Pure 2x2 linear map in mathematical coordinates.
///
/// Matrix layout (column vectors):
///   [ xx xy ]
///   [ yx yy ]
///
/// `a.mul(b)` means apply b first, then a.
pub const Linear2D = struct {
    xx: f64 = 1.0,
    xy: f64 = 0.0,
    yx: f64 = 0.0,
    yy: f64 = 1.0,

    pub const identity: Linear2D = .{};

    pub fn init(xx: f64, xy: f64, yx: f64, yy: f64) Linear2D {
        return .{ .xx = xx, .xy = xy, .yx = yx, .yy = yy };
    }

    pub fn mul(a: Linear2D, b: Linear2D) Linear2D {
        return .{
            .xx = a.xx * b.xx + a.xy * b.yx,
            .xy = a.xx * b.xy + a.xy * b.yy,
            .yx = a.yx * b.xx + a.yy * b.yx,
            .yy = a.yx * b.xy + a.yy * b.yy,
        };
    }

    pub fn rotation(radians: f64) Linear2D {
        const c = @cos(radians);
        const s = @sin(radians);
        return .{ .xx = c, .xy = -s, .yx = s, .yy = c };
    }

    pub fn scaling(x: f64, y: f64) Linear2D {
        return .{ .xx = x, .yy = y };
    }

    pub fn shear(x: f64, y: f64) Linear2D {
        return .{ .xx = 1.0, .xy = x, .yx = y, .yy = 1.0 };
    }

    pub fn determinant(a: Linear2D) f64 {
        return a.xx * a.yy - a.xy * a.yx;
    }

    pub fn inverse(a: Linear2D) error{SingularMatrix}!Linear2D {
        const det = a.determinant();
        if (@abs(det) < 1e-15) return error.SingularMatrix;
        return .{
            .xx = a.yy / det,
            .xy = -a.xy / det,
            .yx = -a.yx / det,
            .yy = a.xx / det,
        };
    }

    pub fn apply(a: Linear2D, v: Vec2) Vec2 {
        return .{
            .x = a.xx * v.x + a.xy * v.y,
            .y = a.yx * v.x + a.yy * v.y,
        };
    }

    pub fn toTransform2D(a: Linear2D) Transform2D {
        return .{ .xx = a.xx, .xy = a.xy, .yx = a.yx, .yy = a.yy };
    }
};

/// 2D affine transform in mathematical coordinates.
///
/// Matrix layout (column vectors):
///   [ xx xy tx ]
///   [ yx yy ty ]
///   [  0  0  1 ]
///
/// `a.mul(b)` means "apply b first, then a".
pub const Transform2D = struct {
    xx: f64 = 1.0,
    xy: f64 = 0.0,
    yx: f64 = 0.0,
    yy: f64 = 1.0,
    tx: f64 = 0.0,
    ty: f64 = 0.0,

    pub const identity: Transform2D = .{};

    pub fn affine(xx: f64, xy: f64, yx: f64, yy: f64, tx: f64, ty: f64) Transform2D {
        return .{ .xx = xx, .xy = xy, .yx = yx, .yy = yy, .tx = tx, .ty = ty };
    }

    pub fn fromLinear(linear: Linear2D) Transform2D {
        return linear.toTransform2D();
    }

    pub fn mul(a: Transform2D, b: Transform2D) Transform2D {
        return .{
            .xx = a.xx * b.xx + a.xy * b.yx,
            .xy = a.xx * b.xy + a.xy * b.yy,
            .yx = a.yx * b.xx + a.yy * b.yx,
            .yy = a.yx * b.xy + a.yy * b.yy,
            .tx = a.xx * b.tx + a.xy * b.ty + a.tx,
            .ty = a.yx * b.tx + a.yy * b.ty + a.ty,
        };
    }

    pub fn translate(a: Transform2D, x: f64, y: f64) Transform2D {
        return a.mul(.{ .tx = x, .ty = y });
    }

    pub fn scale(a: Transform2D, x: f64, y: f64) Transform2D {
        return a.mul(.{ .xx = x, .yy = y });
    }

    pub fn rotate(a: Transform2D, radians: f64) Transform2D {
        const c = @cos(radians);
        const s = @sin(radians);
        return a.mul(.{ .xx = c, .xy = -s, .yx = s, .yy = c });
    }

    pub fn shear(a: Transform2D, x: f64, y: f64) Transform2D {
        return a.mul(.{ .xy = x, .yx = y });
    }

    pub fn determinant(a: Transform2D) f64 {
        return a.xx * a.yy - a.xy * a.yx;
    }

    pub fn inverse(a: Transform2D) error{SingularMatrix}!Transform2D {
        const det = a.determinant();
        if (@abs(det) < 1e-15) return error.SingularMatrix;
        return .{
            .xx = a.yy / det,
            .xy = -a.xy / det,
            .yx = -a.yx / det,
            .yy = a.xx / det,
            .tx = (a.xy * a.ty - a.yy * a.tx) / det,
            .ty = (a.yx * a.tx - a.xx * a.ty) / det,
        };
    }

    pub fn applyPoint(a: Transform2D, p: Vec2) Vec2 {
        return .{
            .x = a.xx * p.x + a.xy * p.y + a.tx,
            .y = a.yx * p.x + a.yy * p.y + a.ty,
        };
    }

    pub fn applyVector(a: Transform2D, v: Vec2) Vec2 {
        return .{
            .x = a.xx * v.x + a.xy * v.y,
            .y = a.yx * v.x + a.yy * v.y,
        };
    }
};

test "positive rotation is counter-clockwise in mathematical coordinates" {
    const p = Transform2D.identity.rotate(std.math.pi / 2.0).applyPoint(.{ .x = 1, .y = 0 });
    try std.testing.expectApproxEqAbs(@as(f64, 0), p.x, 1e-12);
    try std.testing.expectApproxEqAbs(@as(f64, 1), p.y, 1e-12);
}

test "transform inverse round trip" {
    const m = Transform2D.identity.translate(2, -3).rotate(0.7).scale(2, 0.5).shear(0.2, -0.1);
    const p = Vec2{ .x = 1.25, .y = -4.5 };
    const back = (try m.inverse()).applyPoint(m.applyPoint(p));
    try std.testing.expectApproxEqAbs(p.x, back.x, 1e-11);
    try std.testing.expectApproxEqAbs(p.y, back.y, 1e-11);
}

test "Linear2D supports arbitrary nonsingular linear maps" {
    const a = Linear2D.init(1.2, -0.4, 0.7, 0.9);
    const p = Vec2{ .x = 2.0, .y = -3.0 };
    const back = (try a.inverse()).apply(a.apply(p));
    try std.testing.expectApproxEqAbs(p.x, back.x, 1e-12);
    try std.testing.expectApproxEqAbs(p.y, back.y, 1e-12);
}

test "Linear2D composition applies right operand first" {
    const a = Linear2D.shear(0.5, -0.2);
    const b = Linear2D.scaling(2.0, 3.0);
    const p = Vec2{ .x = 1.0, .y = 2.0 };
    const sequential = a.apply(b.apply(p));
    const composed = a.mul(b).apply(p);
    try std.testing.expectApproxEqAbs(sequential.x, composed.x, 1e-12);
    try std.testing.expectApproxEqAbs(sequential.y, composed.y, 1e-12);
}
