from __future__ import annotations

from dataclasses import dataclass

from .space3d import Vec3


@dataclass(slots=True)
class Camera3D:
    """Simple right-handed 3D camera; default view looks toward the origin."""

    position: Vec3 = Vec3(4.5, 3.2, 5.5)
    target: Vec3 = Vec3()
    up: Vec3 = Vec3(0.0, 1.0, 0.0)
    fov_y_degrees: float = 45.0
    near: float = 0.05
    far: float = 100.0
    orthographic_height: float | None = None
    layer_z_index: int = 0

    def __post_init__(self) -> None:
        if self.near <= 0 or self.far <= self.near:
            raise ValueError("Camera3D requires 0 < near < far")
        if not 1.0 <= self.fov_y_degrees < 179.0:
            raise ValueError("Camera3D fov_y_degrees must be in [1, 179)")
        if self.orthographic_height is not None and self.orthographic_height <= 0:
            raise ValueError("Camera3D orthographic_height must be positive")
        if (self.target - self.position).length <= 1e-12:
            raise ValueError("Camera3D position and target must differ")
        if self.up.length <= 1e-12:
            raise ValueError("Camera3D up vector must be non-zero")
