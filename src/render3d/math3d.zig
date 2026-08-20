const std = @import("std");

pub const Vec3 = struct {
    x: f32,
    y: f32,
    z: f32,

    pub fn sub(a: Vec3, b: Vec3) Vec3 {
        return .{ .x = a.x - b.x, .y = a.y - b.y, .z = a.z - b.z };
    }
    pub fn dot(a: Vec3, b: Vec3) f32 {
        return a.x * b.x + a.y * b.y + a.z * b.z;
    }
    pub fn cross(a: Vec3, b: Vec3) Vec3 {
        return .{
            .x = a.y * b.z - a.z * b.y,
            .y = a.z * b.x - a.x * b.z,
            .z = a.x * b.y - a.y * b.x,
        };
    }
    pub fn normalized(v: Vec3) !Vec3 {
        const len = @sqrt(dot(v, v));
        if (!(len > 1e-8) or !std.math.isFinite(len)) return error.DegenerateVector;
        return .{ .x = v.x / len, .y = v.y / len, .z = v.z / len };
    }
};

/// Column-major 4x4 matrix for OpenGL/GLSL.
pub const Mat4 = [16]f32;

pub fn identity() Mat4 {
    return .{
        1, 0, 0, 0,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0, 0, 0, 1,
    };
}

pub fn fromRowMajor(values: [16]f32) Mat4 {
    var out: Mat4 = undefined;
    for (0..4) |row| for (0..4) |col| {
        out[col * 4 + row] = values[row * 4 + col];
    };
    return out;
}

pub fn mul(a: Mat4, b: Mat4) Mat4 {
    var out: Mat4 = @splat(0);
    for (0..4) |col| for (0..4) |row| {
        var sum: f32 = 0;
        for (0..4) |k| sum += a[k * 4 + row] * b[col * 4 + k];
        out[col * 4 + row] = sum;
    };
    return out;
}

pub fn lookAt(eye: Vec3, target: Vec3, up_hint: Vec3) !Mat4 {
    const f = try Vec3.normalized(Vec3.sub(target, eye));
    const s = try Vec3.normalized(Vec3.cross(f, up_hint));
    const u = Vec3.cross(s, f);
    return .{
        s.x,               u.x,               -f.x,             0,
        s.y,               u.y,               -f.y,             0,
        s.z,               u.z,               -f.z,             0,
        -Vec3.dot(s, eye), -Vec3.dot(u, eye), Vec3.dot(f, eye), 1,
    };
}

pub fn perspective(fov_y_degrees: f32, aspect: f32, near: f32, far: f32) !Mat4 {
    if (!(aspect > 0) or !(near > 0) or !(far > near)) return error.InvalidProjection;
    const radians = fov_y_degrees * std.math.pi / 180.0;
    const f = 1.0 / @tan(radians * 0.5);
    const nf = 1.0 / (near - far);
    return .{
        f / aspect, 0, 0,                   0,
        0,          f, 0,                   0,
        0,          0, (far + near) * nf,   -1,
        0,          0, 2 * far * near * nf, 0,
    };
}

pub fn orthographic(height: f32, aspect: f32, near: f32, far: f32) !Mat4 {
    if (!(height > 0) or !(aspect > 0) or !(near > 0) or !(far > near)) return error.InvalidProjection;
    const width = height * aspect;
    return .{
        2.0 / width, 0,            0,                            0,
        0,           2.0 / height, 0,                            0,
        0,           0,            -2.0 / (far - near),          0,
        0,           0,            -(far + near) / (far - near), 1,
    };
}

test "matrix multiplication identity" {
    const a: Mat4 = .{ 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16 };
    try std.testing.expectEqualSlices(f32, &a, &mul(identity(), a));
}
