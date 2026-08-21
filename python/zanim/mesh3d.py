from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from math import isfinite
from typing import Callable

from .geometry import Color
from .space3d import Transform3D, Vec3


@dataclass(frozen=True, slots=True, weakref_slot=True)
class TriangleMesh:
    vertices: tuple[Vec3, ...]
    normals: tuple[Vec3, ...]
    indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.vertices) < 3:
            raise ValueError("TriangleMesh requires at least 3 vertices")
        if len(self.normals) != len(self.vertices):
            raise ValueError("TriangleMesh normals must match vertices")
        if not self.indices or len(self.indices) % 3:
            raise ValueError("TriangleMesh indices must contain complete triangles")
        if min(self.indices) < 0 or max(self.indices) >= len(self.vertices):
            raise ValueError("TriangleMesh index is outside vertex range")
        if any(v.length <= 1e-12 for v in self.normals):
            raise ValueError("TriangleMesh normals must be non-zero")


@dataclass(slots=True)
class MeshObject3D:
    mesh: TriangleMesh
    transform: Transform3D = Transform3D()
    color: Color = Color(104, 184, 255)
    opacity: float = 1.0
    # Immutable object-local geometry placement. Primitive dimensions live here
    # so authoring ``transform`` keeps its original pose-only semantics while
    # canonical meshes remain shareable by the renderer and wire cache.
    geometry_transform: Transform3D = Transform3D()
    _zanim_scene_registered: bool = field(default=False, init=False, repr=False)

    def __setattr__(self, name: str, value) -> None:
        if not name.startswith("_") and getattr(self, "_zanim_scene_registered", False):
            raise RuntimeError(
                f"cannot assign {name!r} after Scene.add(); use a Scene timeline operation"
            )
        object.__setattr__(self, name, value)

    def _mark_scene_registered(self) -> None:
        object.__setattr__(self, "_zanim_scene_registered", True)

    def _set_scene_state(self, name: str, value) -> None:
        object.__setattr__(self, name, value)

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.opacity) <= 1.0:
            raise ValueError("opacity must be in [0, 1]")

    def set_opacity(self, opacity: float) -> "MeshObject3D":
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be in [0, 1]")
        self.opacity = float(opacity)
        return self


@lru_cache(maxsize=1)
def unit_box_mesh() -> TriangleMesh:
    """Canonical unit box centered at the origin.

    Box dimensions belong in the object transform rather than geometry so all
    boxes can share one immutable GPU mesh and participate in instanced draws.
    """
    h = 0.5
    faces = (
        (Vec3(0, 0, 1),  (Vec3(-h,-h,h), Vec3(h,-h,h), Vec3(h,h,h), Vec3(-h,h,h))),
        (Vec3(0, 0,-1),  (Vec3(h,-h,-h), Vec3(-h,-h,-h), Vec3(-h,h,-h), Vec3(h,h,-h))),
        (Vec3(1, 0, 0),  (Vec3(h,-h,h), Vec3(h,-h,-h), Vec3(h,h,-h), Vec3(h,h,h))),
        (Vec3(-1,0, 0),  (Vec3(-h,-h,-h), Vec3(-h,-h,h), Vec3(-h,h,h), Vec3(-h,h,-h))),
        (Vec3(0, 1, 0),  (Vec3(-h,h,h), Vec3(h,h,h), Vec3(h,h,-h), Vec3(-h,h,-h))),
        (Vec3(0,-1, 0),  (Vec3(-h,-h,-h), Vec3(h,-h,-h), Vec3(h,-h,h), Vec3(-h,-h,h))),
    )
    vertices: list[Vec3] = []
    normals: list[Vec3] = []
    indices: list[int] = []
    for normal, corners in faces:
        base = len(vertices)
        vertices.extend(corners)
        normals.extend((normal, normal, normal, normal))
        indices.extend((base, base+1, base+2, base, base+2, base+3))
    return TriangleMesh(tuple(vertices), tuple(normals), tuple(indices))


def box_mesh(size: Vec3 = Vec3(2.0, 2.0, 2.0)) -> TriangleMesh:
    """Compatibility helper returning the canonical box mesh.

    New Box3D objects encode dimensions in Transform3D. Callers that need
    baked dimensions should construct TriangleMesh explicitly.
    """
    if size.x <= 0 or size.y <= 0 or size.z <= 0:
        raise ValueError("box dimensions must be positive")
    return unit_box_mesh()


def cube_mesh(side: float = 2.0) -> TriangleMesh:
    if side <= 0:
        raise ValueError("cube side must be positive")
    return unit_box_mesh()


def Box3D(
    size: Vec3 = Vec3(2.0, 2.0, 2.0),
    *,
    color: Color = Color(104, 184, 255),
    transform: Transform3D = Transform3D(),
) -> MeshObject3D:
    if size.x <= 0 or size.y <= 0 or size.z <= 0:
        raise ValueError("box dimensions must be positive")
    return MeshObject3D(
        unit_box_mesh(),
        transform=transform,
        color=color,
        geometry_transform=Transform3D.scaling(size.x, size.y, size.z),
    )


def Cube3D(
    side: float = 2.0,
    *,
    color: Color = Color(104, 184, 255),
    transform: Transform3D = Transform3D(),
) -> MeshObject3D:
    if side <= 0:
        raise ValueError("cube side must be positive")
    return Box3D(Vec3(side, side, side), color=color, transform=transform)


def Surface3D(
    function: Callable[[float, float], float],
    *,
    x_range: tuple[float, float] = (-3.0, 3.0),
    y_range: tuple[float, float] = (-3.0, 3.0),
    resolution: tuple[int, int] = (81, 81),
    color: Color = Color(82, 196, 150),
    transform: Transform3D = Transform3D(),
) -> MeshObject3D:
    """Create z=f(x,y) as a shared-vertex indexed triangle mesh."""
    x0, x1 = map(float, x_range)
    y0, y1 = map(float, y_range)
    nx, ny = map(int, resolution)
    if not x0 < x1 or not y0 < y1:
        raise ValueError("surface ranges must be increasing")
    if nx < 2 or ny < 2:
        raise ValueError("surface resolution must be at least 2x2")

    dx = (x1 - x0) / (nx - 1)
    dy = (y1 - y0) / (ny - 1)
    heights: list[float] = []
    vertices: list[Vec3] = []
    for j in range(ny):
        y = y0 + j * dy
        for i in range(nx):
            x = x0 + i * dx
            z = float(function(x, y))
            if not isfinite(z):
                raise ValueError(f"surface function returned non-finite value at ({x}, {y})")
            heights.append(z)
            vertices.append(Vec3(x, z, y))  # y-up world: function height is world Y

    normals: list[Vec3] = []
    for j in range(ny):
        jm = max(0, j - 1); jp = min(ny - 1, j + 1)
        for i in range(nx):
            im = max(0, i - 1); ip = min(nx - 1, i + 1)
            dzdx = (heights[j*nx + ip] - heights[j*nx + im]) / ((ip - im) * dx)
            dzdy = (heights[jp*nx + i] - heights[jm*nx + i]) / ((jp - jm) * dy)
            # world coordinates are (x, height, source-y)
            normals.append(Vec3(-dzdx, 1.0, -dzdy).normalized())

    indices: list[int] = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j*nx + i
            b = a + 1
            c = a + nx
            d = c + 1
            indices.extend((a, c, b, b, c, d))
    return MeshObject3D(TriangleMesh(tuple(vertices), tuple(normals), tuple(indices)), transform=transform, color=color)
