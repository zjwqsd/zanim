from __future__ import annotations

from math import cos, pi, sin, tau
from typing import Callable

from zanim import (
    Camera3D,
    Canvas,
    Color,
    Easing,
    MeshObject3D,
    Object2D,
    Rectangle,
    Scene,
    Style,
    Transform2D,
    Transform3D,
    TriangleMesh,
    Vec3,
)

# This is intentionally an effect-level recreation of JAnim's
# ThreeDShapesExample, not a surface-style compatibility layer.
DURATION_PER_SHAPE = 4.0

PointFn = Callable[[float, float], Vec3]
NormalFn = Callable[[float, float], Vec3]


class _Grid:
    __slots__ = ("nu", "nv", "points", "normals", "periodic_v")

    def __init__(
        self,
        point: PointFn,
        normal: NormalFn,
        *,
        nu: int,
        nv: int,
        periodic_v: bool,
    ) -> None:
        self.nu = nu
        self.nv = nv
        self.periodic_v = periodic_v
        self.points: list[Vec3] = []
        self.normals: list[Vec3] = []
        for j in range(nv):
            v = j / nv if periodic_v else j / (nv - 1)
            for i in range(nu):
                u = i / nu
                self.points.append(point(u, v))
                self.normals.append(normal(u, v).normalized())

    def idx(self, i: int, j: int) -> int:
        return (j % self.nv) * self.nu + (i % self.nu)

    def cells(self):
        j_count = self.nv if self.periodic_v else self.nv - 1
        for j in range(j_count):
            for i in range(self.nu):
                yield i, j, (
                    self.idx(i, j),
                    self.idx(i + 1, j),
                    self.idx(i, j + 1),
                    self.idx(i + 1, j + 1),
                )


def _smooth_mesh(grid: _Grid) -> TriangleMesh:
    indices: list[int] = []
    for _, _, (a, b, c, d) in grid.cells():
        indices.extend((a, c, b, b, c, d))
    return TriangleMesh(tuple(grid.points), tuple(grid.normals), tuple(indices))


def _checker_meshes(grid: _Grid) -> tuple[TriangleMesh, TriangleMesh]:
    vertices = ([], [])
    normals = ([], [])
    indices = ([], [])
    for i, j, (a, b, c, d) in grid.cells():
        side = (i + j) & 1
        out_v = vertices[side]
        out_n = normals[side]
        out_i = indices[side]
        base = len(out_v)
        for index in (a, b, c, d):
            out_v.append(grid.points[index])
            out_n.append(grid.normals[index])
        out_i.extend((base, base + 2, base + 1, base + 1, base + 2, base + 3))
    return tuple(
        TriangleMesh(tuple(vertices[k]), tuple(normals[k]), tuple(indices[k]))
        for k in range(2)
    )  # type: ignore[return-value]


def _ribbon_segment(
    vertices: list[Vec3], normals: list[Vec3], indices: list[int],
    a: Vec3, b: Vec3, width: float,
) -> None:
    delta = b - a
    if delta.length <= 1e-9:
        return
    direction = delta.normalized()
    reference = Vec3(0, 1, 0) if abs(direction.y) < 0.85 else Vec3(1, 0, 0)
    side = direction.cross(reference).normalized() * (width * 0.5)
    up = direction.cross(side.normalized()).normalized() * (width * 0.5)

    for offset in (side, up):
        quad = (a + offset, b + offset, b - offset, a - offset)
        normal = (quad[1] - quad[0]).cross(quad[3] - quad[0]).normalized()
        base = len(vertices)
        vertices.extend(quad)
        normals.extend((normal,) * 4)
        # Double-sided ribbons keep the line visible as the object rotates.
        indices.extend((
            base, base + 1, base + 2,
            base, base + 2, base + 3,
            base + 2, base + 1, base,
            base + 3, base + 2, base,
        ))


def _wire_mesh(grid: _Grid, width: float = 0.025) -> TriangleMesh:
    vertices: list[Vec3] = []
    normals: list[Vec3] = []
    indices: list[int] = []

    # u-isolines
    for j in range(grid.nv):
        for i in range(grid.nu):
            _ribbon_segment(
                vertices, normals, indices,
                grid.points[grid.idx(i, j)],
                grid.points[grid.idx(i + 1, j)],
                width,
            )

    # v-isolines. Use a sparser set of columns to keep the visual readable.
    step = max(1, grid.nu // 12)
    j_count = grid.nv if grid.periodic_v else grid.nv - 1
    for i in range(0, grid.nu, step):
        for j in range(j_count):
            _ribbon_segment(
                vertices, normals, indices,
                grid.points[grid.idx(i, j)],
                grid.points[grid.idx(i, j + 1)],
                width,
            )
    return TriangleMesh(tuple(vertices), tuple(normals), tuple(indices))


def _dot_mesh(grid: _Grid, radius: float = 0.045) -> TriangleMesh:
    vertices: list[Vec3] = []
    normals: list[Vec3] = []
    indices: list[int] = []
    # Sample rather than drawing every high-resolution vertex.
    istep = max(1, grid.nu // 14)
    jstep = max(1, grid.nv // 8)
    faces = (
        (Vec3(radius, 0, 0), Vec3(0, radius, 0), Vec3(0, 0, radius)),
        (Vec3(0, radius, 0), Vec3(-radius, 0, 0), Vec3(0, 0, radius)),
        (Vec3(-radius, 0, 0), Vec3(0, -radius, 0), Vec3(0, 0, radius)),
        (Vec3(0, -radius, 0), Vec3(radius, 0, 0), Vec3(0, 0, radius)),
        (Vec3(0, radius, 0), Vec3(radius, 0, 0), Vec3(0, 0, -radius)),
        (Vec3(-radius, 0, 0), Vec3(0, radius, 0), Vec3(0, 0, -radius)),
        (Vec3(0, -radius, 0), Vec3(-radius, 0, 0), Vec3(0, 0, -radius)),
        (Vec3(radius, 0, 0), Vec3(0, -radius, 0), Vec3(0, 0, -radius)),
    )
    for j in range(0, grid.nv, jstep):
        for i in range(0, grid.nu, istep):
            center = grid.points[grid.idx(i, j)]
            for oa, ob, oc in faces:
                a, b, c = center + oa, center + ob, center + oc
                normal = (b - a).cross(c - a).normalized()
                base = len(vertices)
                vertices.extend((a, b, c))
                normals.extend((normal, normal, normal))
                indices.extend((base, base + 1, base + 2))
    return TriangleMesh(tuple(vertices), tuple(normals), tuple(indices))


def _torus_grid() -> _Grid:
    major, minor = 0.78, 0.31
    return _Grid(
        lambda u, v: Vec3(
            (major + minor * cos(tau * v)) * cos(tau * u),
            (major + minor * cos(tau * v)) * sin(tau * u),
            minor * sin(tau * v),
        ),
        lambda u, v: Vec3(
            cos(tau * v) * cos(tau * u),
            cos(tau * v) * sin(tau * u),
            sin(tau * v),
        ),
        nu=28, nv=14, periodic_v=True,
    )


def _cylinder_grid() -> _Grid:
    radius, height = 0.82, 2.15
    return _Grid(
        lambda u, v: Vec3(radius * cos(tau * u), height * (v - 0.5), radius * sin(tau * u)),
        lambda u, v: Vec3(cos(tau * u), 0, sin(tau * u)),
        nu=28, nv=9, periodic_v=False,
    )


def _cone_grid() -> _Grid:
    radius, height = 0.92, 2.25
    # Avoid a fully degenerate zero-radius ring at the tip; visually it is still a cone.
    return _Grid(
        lambda u, v: Vec3(
            radius * (0.025 + 0.975 * v) * cos(tau * u),
            height * (0.5 - v),
            radius * (0.025 + 0.975 * v) * sin(tau * u),
        ),
        lambda u, v: Vec3(height * cos(tau * u), radius, height * sin(tau * u)),
        nu=28, nv=9, periodic_v=False,
    )


def _style_objects(grid: _Grid, style_name: str, transform: Transform3D) -> list[MeshObject3D]:
    if style_name == "checker":
        a, b = _checker_meshes(grid)
        return [
            MeshObject3D(a, transform=transform, color=Color(42, 100, 205), opacity=0.0),
            MeshObject3D(b, transform=transform, color=Color(105, 177, 255), opacity=0.0),
        ]
    if style_name == "wire":
        return [MeshObject3D(_wire_mesh(grid), transform=transform, color=Color(104, 178, 255), opacity=0.0)]
    if style_name == "smooth":
        return [MeshObject3D(_smooth_mesh(grid), transform=transform, color=Color(88, 166, 242), opacity=0.0)]
    if style_name == "dots":
        return [MeshObject3D(_dot_mesh(grid), transform=transform, color=Color(125, 188, 255), opacity=0.0)]
    raise ValueError(style_name)


def build_three_d_shapes_example() -> Scene:
    canvas = Canvas(width=1920, height=1080, unit_size=135)
    scene = Scene(canvas=canvas, fps=30)
    scene.camera3d = Camera3D(
        position=Vec3(0, 0, 15),
        target=Vec3(),
        up=Vec3(0, 1, 0),
        orthographic_height=8.0,
        layer_z_index=0,
    )

    # Match JAnim's four dark sub-scene backgrounds and quadrant composition.
    panel_w = canvas.width / canvas.unit_size / 2
    panel_h = canvas.height / canvas.unit_size / 2
    centers = (
        Vec3(-panel_w / 2, panel_h / 2, 0),
        Vec3(panel_w / 2, panel_h / 2, 0),
        Vec3(-panel_w / 2, -panel_h / 2, 0),
        Vec3(panel_w / 2, -panel_h / 2, 0),
    )
    backgrounds = (Color(0, 0, 34), Color(0, 0, 51), Color(0, 0, 51), Color(0, 0, 34))
    for center, color in zip(centers, backgrounds):
        scene.add(Object2D(
            Rectangle(panel_w + 0.01, panel_h + 0.01),
            style=Style(fill=color),
            transform=Transform2D.translation(center.x, center.y),
            z_index=-10,
        ))

    styles = ("checker", "wire", "smooth", "dots")
    grids = (_torus_grid(), _cylinder_grid(), _cone_grid())

    with scene.parallel():
        for shape_index, grid in enumerate(grids):
            start = shape_index * DURATION_PER_SHAPE
            for style_name, center in zip(styles, centers):
                base = (
                    Transform3D.translation(center.x, center.y, 0)
                    @ Transform3D.rotation_x(-0.38)
                    @ Transform3D.rotation_y(0.45)
                )
                objects = _style_objects(grid, style_name, base)
                for obj in objects:
                    scene.add(obj)
                    scene.fade_in(obj, duration=0.12, at=start)
                    scene.play_transform_function(
                        obj,
                        lambda a, c=center: (
                            Transform3D.translation(c.x, c.y, 0)
                            @ Transform3D.rotation_z(tau * a)
                            @ Transform3D.rotation_x(tau * a - 0.38)
                            @ Transform3D.rotation_y(0.45)
                        ),
                        duration=DURATION_PER_SHAPE,
                        easing=Easing.LINEAR,
                        at=start,
                    )
                    scene.fade_out(obj, duration=0.12, at=start + DURATION_PER_SHAPE - 0.12)

    return scene
