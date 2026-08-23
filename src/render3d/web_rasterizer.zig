const std = @import("std");
const wire = @import("wire.zig");
const math = @import("math3d.zig");

const Vec3 = math.Vec3;

const Vec4 = struct { x: f32, y: f32, z: f32, w: f32 };
const ClipVertex = struct { clip: Vec4, normal: Vec3 };
const ScreenVertex = struct { x: f32, y: f32, depth: f32, inv_w: f32, normal: Vec3 };

const NormalMatrix = struct {
    m00: f32,
    m01: f32,
    m02: f32,
    m10: f32,
    m11: f32,
    m12: f32,
    m20: f32,
    m21: f32,
    m22: f32,

    fn apply(self: NormalMatrix, v: Vec3) Vec3 {
        return .{
            .x = self.m00 * v.x + self.m01 * v.y + self.m02 * v.z,
            .y = self.m10 * v.x + self.m11 * v.y + self.m12 * v.z,
            .z = self.m20 * v.x + self.m21 * v.y + self.m22 * v.z,
        };
    }
};

pub const max_vertices_per_mesh = 16_384;
var vertex_scratch: [max_vertices_per_mesh]ClipVertex = undefined;

const light_len = @sqrt(0.35 * 0.35 + 0.82 * 0.82 + 0.48 * 0.48);
const light_dir = Vec3{
    .x = 0.35 / light_len,
    .y = 0.82 / light_len,
    .z = 0.48 / light_len,
};

pub fn render(
    pixels: []u8,
    depth: []f32,
    width: u32,
    height: u32,
    camera: wire.WireCamera3D,
    meshes: []const wire.WireMesh3D,
) !void {
    if (width == 0 or height == 0) return error.InvalidDimensions;
    const pixel_count = @as(usize, width) * @as(usize, height);
    if (pixels.len < pixel_count * 4 or depth.len < pixel_count) return error.InvalidOutputSize;
    @memset(pixels[0 .. pixel_count * 4], 0);
    @memset(depth[0..pixel_count], std.math.inf(f32));

    const eye = Vec3{ .x = camera.px, .y = camera.py, .z = camera.pz };
    const target = Vec3{ .x = camera.tx, .y = camera.ty, .z = camera.tz };
    const up = Vec3{ .x = camera.ux, .y = camera.uy, .z = camera.uz };
    const aspect = @as(f32, @floatFromInt(width)) / @as(f32, @floatFromInt(height));
    const view = try math.lookAt(eye, target, up);
    const proj = if (camera.projection_kind == 0)
        try math.perspective(camera.fov_y_degrees, aspect, camera.near_plane, camera.far_plane)
    else
        try math.orthographic(camera.orthographic_height, aspect, camera.near_plane, camera.far_plane);
    const view_proj = math.mul(proj, view);

    for (meshes) |mesh| {
        const alpha = effectiveAlpha(mesh);
        if (!(alpha >= 0 and alpha <= 1) or !std.math.isFinite(alpha)) return error.InvalidOpacity;
        if (alpha < 0.999) continue;
        try drawMesh(width, height, view_proj, mesh, depth, pixels, true);
    }

    var transparent: [64]usize = undefined;
    var transparent_count: usize = 0;
    for (meshes, 0..) |mesh, index| {
        const alpha = effectiveAlpha(mesh);
        if (alpha > 0.001 and alpha < 0.999) {
            if (transparent_count >= transparent.len) return error.TooManyMeshes;
            var at = transparent_count;
            const distance = modelCenterDistance2(mesh, eye);
            while (at > 0 and modelCenterDistance2(meshes[transparent[at - 1]], eye) < distance) : (at -= 1) {
                transparent[at] = transparent[at - 1];
            }
            transparent[at] = index;
            transparent_count += 1;
        }
    }
    for (transparent[0..transparent_count]) |index| {
        try drawMesh(width, height, view_proj, meshes[index], depth, pixels, false);
    }
}

fn modelCenterDistance2(mesh: wire.WireMesh3D, eye: Vec3) f32 {
    const x = mesh.model[3] - eye.x;
    const y = mesh.model[7] - eye.y;
    const z = mesh.model[11] - eye.z;
    return x * x + y * y + z * z;
}

fn drawMesh(
    width: u32,
    height: u32,
    view_proj: math.Mat4,
    mesh: wire.WireMesh3D,
    depth: []f32,
    pixels: []u8,
    is_opaque: bool,
) !void {
    const positions = mesh.positions orelse return error.InvalidMesh;
    const normals = mesh.normals orelse return error.InvalidMesh;
    const indices = mesh.indices orelse return error.InvalidMesh;
    if (mesh.vertex_count < 3 or mesh.index_count < 3 or mesh.index_count % 3 != 0) return error.InvalidMesh;
    if (mesh.vertex_count > max_vertices_per_mesh) return error.MeshTooLarge;

    const model = math.fromRowMajor(mesh.model);
    const mvp = math.mul(view_proj, model);
    const normal_matrix = try normalMatrix(model);
    const rgba = unpackColor(mesh.color_rgba, mesh.opacity);
    const vertices = vertex_scratch[0..mesh.vertex_count];
    for (vertices, 0..) |*vertex, index| {
        vertex.* = makeVertex(mvp, normal_matrix, positions, normals, index);
    }

    var triangle: usize = 0;
    while (triangle < mesh.index_count) : (triangle += 3) {
        const idx0: usize = @intCast(indices[triangle]);
        const idx1: usize = @intCast(indices[triangle + 1]);
        const idx2: usize = @intCast(indices[triangle + 2]);
        if (idx0 >= mesh.vertex_count or idx1 >= mesh.vertex_count or idx2 >= mesh.vertex_count) return error.InvalidMesh;

        var polygon_a: [16]ClipVertex = undefined;
        var polygon_b: [16]ClipVertex = undefined;
        polygon_a[0] = vertices[idx0];
        polygon_a[1] = vertices[idx1];
        polygon_a[2] = vertices[idx2];
        var count: usize = 3;
        var use_a = true;
        inline for (0..6) |plane| {
            if (count < 3) break;
            count = if (use_a)
                clipPolygon(polygon_a[0..count], &polygon_b, plane)
            else
                clipPolygon(polygon_b[0..count], &polygon_a, plane);
            use_a = !use_a;
        }
        if (count < 3) continue;
        const polygon = if (use_a) polygon_a[0..count] else polygon_b[0..count];
        var fan: usize = 1;
        while (fan + 1 < polygon.len) : (fan += 1) {
            rasterTriangle(width, height, polygon[0], polygon[fan], polygon[fan + 1], rgba, depth, pixels, is_opaque);
        }
    }
}

fn makeVertex(mvp: math.Mat4, normal_matrix: NormalMatrix, positions: [*]const f32, normals: [*]const f32, index: usize) ClipVertex {
    const p = Vec4{
        .x = positions[index * 3],
        .y = positions[index * 3 + 1],
        .z = positions[index * 3 + 2],
        .w = 1,
    };
    const n = Vec3{
        .x = normals[index * 3],
        .y = normals[index * 3 + 1],
        .z = normals[index * 3 + 2],
    };
    return .{ .clip = mulVec4(mvp, p), .normal = normal_matrix.apply(n) };
}

fn mulVec4(m: math.Mat4, v: Vec4) Vec4 {
    return .{
        .x = m[0] * v.x + m[4] * v.y + m[8] * v.z + m[12] * v.w,
        .y = m[1] * v.x + m[5] * v.y + m[9] * v.z + m[13] * v.w,
        .z = m[2] * v.x + m[6] * v.y + m[10] * v.z + m[14] * v.w,
        .w = m[3] * v.x + m[7] * v.y + m[11] * v.z + m[15] * v.w,
    };
}

fn planeDistance(v: Vec4, plane: usize) f32 {
    return switch (plane) {
        0 => v.x + v.w,
        1 => v.w - v.x,
        2 => v.y + v.w,
        3 => v.w - v.y,
        4 => v.z + v.w,
        5 => v.w - v.z,
        else => unreachable,
    };
}

fn clipPolygon(input: []const ClipVertex, output: *[16]ClipVertex, plane: usize) usize {
    if (input.len == 0) return 0;
    var out_count: usize = 0;
    var previous = input[input.len - 1];
    var previous_distance = planeDistance(previous.clip, plane);
    var previous_inside = previous_distance >= 0;
    for (input) |current| {
        const current_distance = planeDistance(current.clip, plane);
        const current_inside = current_distance >= 0;
        if (current_inside != previous_inside) {
            const denominator = previous_distance - current_distance;
            const t = if (@abs(denominator) <= 1e-20) 0.0 else previous_distance / denominator;
            output[out_count] = lerpVertex(previous, current, t);
            out_count += 1;
        }
        if (current_inside) {
            output[out_count] = current;
            out_count += 1;
        }
        previous = current;
        previous_distance = current_distance;
        previous_inside = current_inside;
    }
    return out_count;
}

fn lerpVertex(a: ClipVertex, b: ClipVertex, t: f32) ClipVertex {
    const s = 1.0 - t;
    return .{
        .clip = .{
            .x = a.clip.x * s + b.clip.x * t,
            .y = a.clip.y * s + b.clip.y * t,
            .z = a.clip.z * s + b.clip.z * t,
            .w = a.clip.w * s + b.clip.w * t,
        },
        .normal = .{
            .x = a.normal.x * s + b.normal.x * t,
            .y = a.normal.y * s + b.normal.y * t,
            .z = a.normal.z * s + b.normal.z * t,
        },
    };
}

fn rasterTriangle(
    width: u32,
    height: u32,
    a: ClipVertex,
    b: ClipVertex,
    c: ClipVertex,
    rgba: [4]f32,
    depth: []f32,
    pixels: []u8,
    is_opaque: bool,
) void {
    if (@abs(a.clip.w) <= 1e-12 or @abs(b.clip.w) <= 1e-12 or @abs(c.clip.w) <= 1e-12) return;
    const va = toScreen(width, height, a);
    const vb = toScreen(width, height, b);
    const vc = toScreen(width, height, c);

    const ax = a.clip.x / a.clip.w;
    const ay = a.clip.y / a.clip.w;
    const bx = b.clip.x / b.clip.w;
    const by = b.clip.y / b.clip.w;
    const cx = c.clip.x / c.clip.w;
    const cy = c.clip.y / c.clip.w;
    const ndc_area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
    if (!(ndc_area > 1e-12)) return;

    const area = edge(va.x, va.y, vb.x, vb.y, vc.x, vc.y);
    if (@abs(area) <= 1e-12) return;
    const inv_area = 1.0 / area;
    const min_x = @max(0, @as(i32, @intFromFloat(@floor(@min(va.x, @min(vb.x, vc.x))))));
    const max_x = @min(@as(i32, @intCast(width)) - 1, @as(i32, @intFromFloat(@ceil(@max(va.x, @max(vb.x, vc.x))))));
    const min_y = @max(0, @as(i32, @intFromFloat(@floor(@min(va.y, @min(vb.y, vc.y))))));
    const max_y = @min(@as(i32, @intCast(height)) - 1, @as(i32, @intFromFloat(@ceil(@max(va.y, @max(vb.y, vc.y))))));
    if (min_x > max_x or min_y > max_y) return;

    var y = min_y;
    while (y <= max_y) : (y += 1) {
        const py = @as(f32, @floatFromInt(y)) + 0.5;
        var x = min_x;
        while (x <= max_x) : (x += 1) {
            const px = @as(f32, @floatFromInt(x)) + 0.5;
            const w0 = edge(vb.x, vb.y, vc.x, vc.y, px, py) * inv_area;
            const w1 = edge(vc.x, vc.y, va.x, va.y, px, py) * inv_area;
            const w2 = 1.0 - w0 - w1;
            if (w0 < -1e-6 or w1 < -1e-6 or w2 < -1e-6) continue;
            const z = w0 * va.depth + w1 * vb.depth + w2 * vc.depth;
            if (z < 0 or z > 1) continue;
            const pixel = @as(usize, @intCast(y)) * @as(usize, width) + @as(usize, @intCast(x));
            if (z > depth[pixel] + 1e-7) continue;

            const p0 = w0 * va.inv_w;
            const p1 = w1 * vb.inv_w;
            const p2 = w2 * vc.inv_w;
            var n = Vec3{
                .x = p0 * va.normal.x + p1 * vb.normal.x + p2 * vc.normal.x,
                .y = p0 * va.normal.y + p1 * vb.normal.y + p2 * vc.normal.y,
                .z = p0 * va.normal.z + p1 * vb.normal.z + p2 * vc.normal.z,
            };
            const len2 = Vec3.dot(n, n);
            if (len2 > 1e-20) {
                const inv_len = 1.0 / @sqrt(len2);
                n.x *= inv_len;
                n.y *= inv_len;
                n.z *= inv_len;
            }
            const diffuse = @max(0.0, Vec3.dot(n, light_dir));
            const illumination = 0.24 + 0.76 * diffuse;
            const src = [4]f32{
                @max(0, @min(1, rgba[0] * illumination)),
                @max(0, @min(1, rgba[1] * illumination)),
                @max(0, @min(1, rgba[2] * illumination)),
                rgba[3],
            };
            if (is_opaque) {
                depth[pixel] = z;
                writeOpaque(pixels, pixel, src);
            } else {
                blendSourceOver(pixels, pixel, src);
            }
        }
    }
}

fn toScreen(width: u32, height: u32, v: ClipVertex) ScreenVertex {
    const inv_w = 1.0 / v.clip.w;
    const nx = v.clip.x * inv_w;
    const ny = v.clip.y * inv_w;
    const nz = v.clip.z * inv_w;
    return .{
        .x = (nx * 0.5 + 0.5) * @as(f32, @floatFromInt(width)),
        .y = (0.5 - ny * 0.5) * @as(f32, @floatFromInt(height)),
        .depth = nz * 0.5 + 0.5,
        .inv_w = inv_w,
        .normal = v.normal,
    };
}

fn edge(ax: f32, ay: f32, bx: f32, by: f32, px: f32, py: f32) f32 {
    return (bx - ax) * (py - ay) - (by - ay) * (px - ax);
}

fn normalMatrix(model: math.Mat4) !NormalMatrix {
    const a00 = model[0];
    const a01 = model[4];
    const a02 = model[8];
    const a10 = model[1];
    const a11 = model[5];
    const a12 = model[9];
    const a20 = model[2];
    const a21 = model[6];
    const a22 = model[10];
    const c00 = a11 * a22 - a12 * a21;
    const c01 = a12 * a20 - a10 * a22;
    const c02 = a10 * a21 - a11 * a20;
    const c10 = a02 * a21 - a01 * a22;
    const c11 = a00 * a22 - a02 * a20;
    const c12 = a01 * a20 - a00 * a21;
    const c20 = a01 * a12 - a02 * a11;
    const c21 = a02 * a10 - a00 * a12;
    const c22 = a00 * a11 - a01 * a10;
    const det = a00 * c00 + a01 * c01 + a02 * c02;
    if (@abs(det) <= 1e-12) return error.SingularModelTransform;
    const inv_det = 1.0 / det;
    return .{
        .m00 = c00 * inv_det,
        .m01 = c01 * inv_det,
        .m02 = c02 * inv_det,
        .m10 = c10 * inv_det,
        .m11 = c11 * inv_det,
        .m12 = c12 * inv_det,
        .m20 = c20 * inv_det,
        .m21 = c21 * inv_det,
        .m22 = c22 * inv_det,
    };
}

fn effectiveAlpha(mesh: wire.WireMesh3D) f32 {
    return mesh.opacity * (@as(f32, @floatFromInt(mesh.color_rgba & 0xff)) / 255.0);
}

fn unpackColor(rgba: u32, opacity: f32) [4]f32 {
    const scale: f32 = 1.0 / 255.0;
    return .{
        @as(f32, @floatFromInt((rgba >> 24) & 0xff)) * scale,
        @as(f32, @floatFromInt((rgba >> 16) & 0xff)) * scale,
        @as(f32, @floatFromInt((rgba >> 8) & 0xff)) * scale,
        @as(f32, @floatFromInt(rgba & 0xff)) * scale * opacity,
    };
}

fn toU8(value: f32) u8 {
    return @intFromFloat(@round(@max(0.0, @min(255.0, value * 255.0))));
}

fn writeOpaque(pixels: []u8, pixel: usize, src: [4]f32) void {
    const base = pixel * 4;
    pixels[base] = toU8(src[0]);
    pixels[base + 1] = toU8(src[1]);
    pixels[base + 2] = toU8(src[2]);
    pixels[base + 3] = 255;
}

fn blendSourceOver(pixels: []u8, pixel: usize, src: [4]f32) void {
    const sa = @max(0.0, @min(1.0, src[3]));
    if (sa <= 0) return;
    const base = pixel * 4;
    const da = @as(f32, @floatFromInt(pixels[base + 3])) / 255.0;
    const out_a = sa + da * (1.0 - sa);
    if (out_a <= 1e-8) return;
    const inv = 1.0 - sa;
    inline for (0..3) |channel| {
        const dst = @as(f32, @floatFromInt(pixels[base + channel])) / 255.0;
        pixels[base + channel] = toU8((src[channel] * sa + dst * da * inv) / out_a);
    }
    pixels[base + 3] = toU8(out_a);
}

test "web rasterizer clip volume contains origin" {
    const v = Vec4{ .x = 0, .y = 0, .z = 0, .w = 1 };
    inline for (0..6) |plane| try std.testing.expect(planeDistance(v, plane) > 0);
}
