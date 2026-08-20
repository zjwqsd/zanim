from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .batch import BatchGeometry, BatchObject2D
from .geometry import Color, Geometry, Object2D, Style
from .space import Transform2D
from .raster import RasterFrame, RasterObject2D
from .vector import VectorDocument, VectorObject2D
from .camera3d import Camera3D
from .mesh3d import MeshObject3D, TriangleMesh
from .space3d import Transform3D, Vec3

if TYPE_CHECKING:
    from .interpolation import ObjectInterpolation


@dataclass(frozen=True, slots=True)
class NodeSnapshot:
    transform: Transform2D
    opacity: float = 1.0
    z_index: int = 0


@dataclass(frozen=True, slots=True)
class ObjectSnapshot:
    geometry: Geometry
    transform: Transform2D
    style: Style
    opacity: float = 1.0
    z_index: int = 0
    trim: float = 1.0

    @staticmethod
    def from_object(obj: Object2D) -> "ObjectSnapshot":
        return ObjectSnapshot(obj.geometry, obj.transform, obj.style, obj.opacity, obj.z_index, obj.trim)


@dataclass(frozen=True, slots=True)
class BatchSnapshot:
    batch: BatchGeometry
    transform: Transform2D
    opacity: float = 1.0
    z_index: int = 0

    @staticmethod
    def from_object(obj: BatchObject2D) -> "BatchSnapshot":
        return BatchSnapshot(obj.batch, obj.transform, obj.opacity, obj.z_index)


@dataclass(frozen=True, slots=True)
class VectorSnapshot:
    document: VectorDocument
    transform: Transform2D
    reveal: float = 1.0
    opacity: float = 1.0
    z_index: int = 0

    @staticmethod
    def from_object(obj: VectorObject2D) -> "VectorSnapshot":
        return VectorSnapshot(obj.document, obj.transform, obj.reveal, obj.opacity, obj.z_index)


@dataclass(frozen=True, slots=True)
class RasterState:
    """Frozen authoring state; intentionally contains no decoded frame."""

    width: float
    height: float
    transform: Transform2D
    opacity: float = 1.0
    z_index: int = 0

    @staticmethod
    def from_object(obj: RasterObject2D) -> "RasterState":
        return RasterState(obj.width, obj.height, obj.transform, obj.opacity, obj.z_index)


@dataclass(frozen=True, slots=True)
class RasterSnapshot:
    """Complete per-frame raster render value."""

    frame: RasterFrame
    width: float
    height: float
    transform: Transform2D
    opacity: float = 1.0
    z_index: int = 0


@dataclass(frozen=True, slots=True)
class Camera3DSnapshot:
    position: Vec3
    target: Vec3
    up: Vec3
    fov_y_degrees: float
    near: float
    far: float
    orthographic_height: float | None
    layer_z_index: int

    @staticmethod
    def from_camera(camera: Camera3D) -> "Camera3DSnapshot":
        return Camera3DSnapshot(
            camera.position, camera.target, camera.up, camera.fov_y_degrees,
            camera.near, camera.far, camera.orthographic_height, camera.layer_z_index,
        )


@dataclass(frozen=True, slots=True)
class Mesh3DSnapshot:
    mesh: TriangleMesh
    transform: Transform3D
    color: Color
    opacity: float = 1.0
    geometry_transform: Transform3D = Transform3D()

    @staticmethod
    def from_object(obj: MeshObject3D) -> "Mesh3DSnapshot":
        return Mesh3DSnapshot(
            obj.mesh, obj.transform, obj.color, obj.opacity, obj.geometry_transform
        )


@dataclass(frozen=True, slots=True)
class RenderObject:
    object_id: int
    snapshot: ObjectSnapshot


@dataclass(frozen=True, slots=True)
class RenderBatch:
    object_id: int
    snapshot: BatchSnapshot
    target: BatchSnapshot | None = None
    alpha: float = 0.0


@dataclass(frozen=True, slots=True)
class RenderVector:
    object_id: int
    snapshot: VectorSnapshot


@dataclass(frozen=True, slots=True)
class RenderRaster:
    object_id: int
    snapshot: RasterSnapshot


@dataclass(frozen=True, slots=True)
class RenderMesh3D:
    object_id: int
    snapshot: Mesh3DSnapshot


@dataclass(frozen=True, slots=True)
class TransientInterpolation:
    interpolation: "ObjectInterpolation"
    alpha: float


@dataclass(frozen=True, slots=True)
class RenderSnapshot:
    time: float
    objects: tuple[RenderObject, ...]
    batches: tuple[RenderBatch, ...]
    vectors: tuple[RenderVector, ...]
    rasters: tuple[RenderRaster, ...]
    transients: tuple[TransientInterpolation, ...]
    meshes3d: tuple[RenderMesh3D, ...] = ()
    camera3d: Camera3DSnapshot | None = None
