pub const WireCamera3D = extern struct {
    px: f32,
    py: f32,
    pz: f32,
    tx: f32,
    ty: f32,
    tz: f32,
    ux: f32,
    uy: f32,
    uz: f32,
    fov_y_degrees: f32,
    near_plane: f32,
    far_plane: f32,
    orthographic_height: f32,
    projection_kind: u32,
};

pub const WireMesh3D = extern struct {
    vertex_count: u32,
    positions: ?[*]const f32,
    normals: ?[*]const f32,
    index_count: u32,
    indices: ?[*]const u32,
    model: [16]f32,
    color_rgba: u32,
    opacity: f32,
};

/// One ordered 3D layer in the heterogeneous scene draw stream.
/// All meshes share one camera and one depth buffer, then compositing resumes
/// on the same 2D framebuffer for later draw items.
pub const WireScene3DLayer = extern struct {
    camera: WireCamera3D,
    meshes: ?[*]const WireMesh3D,
    mesh_count: u32,
};
