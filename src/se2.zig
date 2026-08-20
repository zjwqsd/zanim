const std = @import("std");
const math = @import("math.zig");

pub const Vec2 = math.Vec2;
pub const Transform2D = math.Transform2D;

/// Element of SE(2): a proper 2D rigid transform.
///
/// p' = R(theta) p + t
///
/// The representation stores exactly one angle and one translation vector, so
/// scale, shear, and reflection cannot accidentally enter an object's pose.
pub const SE2 = struct {
    theta: f64 = 0.0,
    translation: Vec2 = .{},

    pub const identity: SE2 = .{};

    pub fn init(theta: f64, translation: Vec2) SE2 {
        return .{ .theta = theta, .translation = translation };
    }

    /// Group product. `a.mul(b)` means apply b first, then a.
    pub fn mul(a: SE2, b: SE2) SE2 {
        const rotated_b_translation = a.applyVector(b.translation);
        return .{
            .theta = a.theta + b.theta,
            .translation = .{
                .x = rotated_b_translation.x + a.translation.x,
                .y = rotated_b_translation.y + a.translation.y,
            },
        };
    }

    pub fn inverse(a: SE2) SE2 {
        const c = @cos(a.theta);
        const s = @sin(a.theta);
        return .{
            .theta = -a.theta,
            .translation = .{
                .x = -(c * a.translation.x + s * a.translation.y),
                .y = -(-s * a.translation.x + c * a.translation.y),
            },
        };
    }

    pub fn applyPoint(a: SE2, p: Vec2) Vec2 {
        const v = a.applyVector(p);
        return .{
            .x = v.x + a.translation.x,
            .y = v.y + a.translation.y,
        };
    }

    pub fn applyVector(a: SE2, v: Vec2) Vec2 {
        const c = @cos(a.theta);
        const s = @sin(a.theta);
        return .{
            .x = c * v.x - s * v.y,
            .y = s * v.x + c * v.y,
        };
    }

    pub fn toTransform2D(a: SE2) Transform2D {
        const c = @cos(a.theta);
        const s = @sin(a.theta);
        return .{
            .xx = c,
            .xy = -s,
            .yx = s,
            .yy = c,
            .tx = a.translation.x,
            .ty = a.translation.y,
        };
    }
};

fn expectVecApprox(expected: Vec2, actual: Vec2) !void {
    try std.testing.expectApproxEqAbs(expected.x, actual.x, 1e-12);
    try std.testing.expectApproxEqAbs(expected.y, actual.y, 1e-12);
}

test "SE2 rotation is positive counter-clockwise" {
    const pose = SE2.init(std.math.pi / 2.0, .{});
    try expectVecApprox(.{ .x = 0, .y = 1 }, pose.applyPoint(.{ .x = 1, .y = 0 }));
}

test "SE2 composition applies right operand first" {
    const a = SE2.init(std.math.pi / 2.0, .{ .x = 1, .y = 2 });
    const b = SE2.init(0.0, .{ .x = 3, .y = 0 });
    const p = Vec2{ .x = 2, .y = -1 };
    try expectVecApprox(a.applyPoint(b.applyPoint(p)), a.mul(b).applyPoint(p));
}

test "SE2 inverse round trip" {
    const pose = SE2.init(0.73, .{ .x = 2.4, .y = -1.7 });
    const p = Vec2{ .x = -4.2, .y = 0.8 };
    try expectVecApprox(p, pose.inverse().applyPoint(pose.applyPoint(p)));
}

test "SE2 converts exactly to affine matrix" {
    const pose = SE2.init(-0.42, .{ .x = 3.0, .y = 4.0 });
    const p = Vec2{ .x = 1.2, .y = -0.7 };
    try expectVecApprox(pose.applyPoint(p), pose.toTransform2D().applyPoint(p));
    try std.testing.expectApproxEqAbs(@as(f64, 1), pose.toTransform2D().determinant(), 1e-12);
}
