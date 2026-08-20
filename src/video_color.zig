const std = @import("std");

/// Convert packed RGB0/RGBx pixels to limited-range BT.601 NV12.
///
/// This is intentionally a video-output boundary operation rather than part of
/// the scene renderer. 2D/3D compositing stays in RGB; only finished frames are
/// subsampled for encoders that accept NV12 directly.
pub fn rgb0ToNv12(width: u32, height: u32, rgb0: []const u8, nv12: []u8) !void {
    if (width == 0 or height == 0 or (width & 1) != 0 or (height & 1) != 0) {
        return error.InvalidDimensions;
    }
    const w: usize = width;
    const h: usize = height;
    const pixel_count = w * h;
    const rgb_bytes = pixel_count * 4;
    const nv12_bytes = pixel_count + pixel_count / 2;
    if (rgb0.len < rgb_bytes or nv12.len < nv12_bytes) return error.BufferTooSmall;

    const y_plane = nv12[0..pixel_count];
    const uv_plane = nv12[pixel_count..nv12_bytes];

    var y: usize = 0;
    while (y < h) : (y += 2) {
        const row0 = y * w;
        const row1 = row0 + w;
        var x: usize = 0;
        while (x < w) : (x += 2) {
            const p00 = (row0 + x) * 4;
            const p01 = p00 + 4;
            const p10 = (row1 + x) * 4;
            const p11 = p10 + 4;

            const r00: i32 = rgb0[p00];
            const g00: i32 = rgb0[p00 + 1];
            const b00: i32 = rgb0[p00 + 2];
            const r01: i32 = rgb0[p01];
            const g01: i32 = rgb0[p01 + 1];
            const b01: i32 = rgb0[p01 + 2];
            const r10: i32 = rgb0[p10];
            const g10: i32 = rgb0[p10 + 1];
            const b10: i32 = rgb0[p10 + 2];
            const r11: i32 = rgb0[p11];
            const g11: i32 = rgb0[p11 + 1];
            const b11: i32 = rgb0[p11 + 2];

            y_plane[row0 + x] = luma(r00, g00, b00);
            y_plane[row0 + x + 1] = luma(r01, g01, b01);
            y_plane[row1 + x] = luma(r10, g10, b10);
            y_plane[row1 + x + 1] = luma(r11, g11, b11);

            // 4:2:0 chroma is sampled from the 2x2 block average. This matches
            // FFmpeg's default RGB -> yuv420p/NV12 conversion to within normal
            // integer rounding (<= 1 code value in our regression comparison).
            const r = @divTrunc(r00 + r01 + r10 + r11 + 2, 4);
            const g = @divTrunc(g00 + g01 + g10 + g11 + 2, 4);
            const b = @divTrunc(b00 + b01 + b10 + b11 + 2, 4);
            const uv = (y / 2) * w + x;
            uv_plane[uv] = chromaU(r, g, b);
            uv_plane[uv + 1] = chromaV(r, g, b);
        }
    }
}

inline fn luma(r: i32, g: i32, b: i32) u8 {
    return clampByte(((66 * r + 129 * g + 25 * b + 128) >> 8) + 16);
}

inline fn chromaU(r: i32, g: i32, b: i32) u8 {
    return clampByte(((-38 * r - 74 * g + 112 * b + 128) >> 8) + 128);
}

inline fn chromaV(r: i32, g: i32, b: i32) u8 {
    return clampByte(((112 * r - 94 * g - 18 * b + 128) >> 8) + 128);
}

inline fn clampByte(value: i32) u8 {
    return @intCast(@max(0, @min(255, value)));
}

test "rgb0 to nv12 black and white" {
    const black = [_]u8{0, 0, 0, 0} ** 4;
    var black_nv12: [6]u8 = undefined;
    try rgb0ToNv12(2, 2, &black, &black_nv12);
    try std.testing.expectEqualSlices(u8, &.{ 16, 16, 16, 16, 128, 128 }, &black_nv12);

    const white = [_]u8{255, 255, 255, 0} ** 4;
    var white_nv12: [6]u8 = undefined;
    try rgb0ToNv12(2, 2, &white, &white_nv12);
    try std.testing.expectEqualSlices(u8, &.{ 235, 235, 235, 235, 128, 128 }, &white_nv12);
}

test "rgb0 to nv12 requires even dimensions" {
    const rgb = [_]u8{0} ** 12;
    var out: [8]u8 = undefined;
    try std.testing.expectError(error.InvalidDimensions, rgb0ToNv12(3, 1, &rgb, &out));
}
