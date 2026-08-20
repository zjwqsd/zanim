const std = @import("std");
const z2d = @import("z2d");
const wire = @import("render3d/wire.zig");
const rasterizer = @import("render3d/rasterizer.zig");

pub const WireCamera3D = wire.WireCamera3D;
pub const WireMesh3D = wire.WireMesh3D;
pub const WireScene3DLayer = wire.WireScene3DLayer;

pub fn drawLayer(
    surface: *z2d.Surface,
    width: u32,
    height: u32,
    layer: WireScene3DLayer,
) !void {
    if (layer.mesh_count > 0 and layer.meshes == null) return error.InvalidMeshLayer;
    const meshes = if (layer.mesh_count == 0) &.{} else layer.meshes.?[0..layer.mesh_count];
    try rasterizer.drawSurface(surface, width, height, layer.camera, meshes);
}

test {
    std.testing.refAllDecls(@import("render3d/math3d.zig"));
    std.testing.refAllDecls(rasterizer);
}
