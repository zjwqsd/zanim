from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .space3d import Vec3

if TYPE_CHECKING:
    from .scene import Scene


@dataclass(frozen=True, slots=True)
class Camera3DState:
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

    def interpolate(self, other: "Camera3DState", alpha: float) -> "Camera3DState":
        t = max(0.0, min(1.0, float(alpha)))
        if self.layer_z_index != other.layer_z_index and 0.0 < t < 1.0:
            raise ValueError(
                "Camera3D layer_z_index cannot be interpolated; set it instantaneously"
            )
        if (self.orthographic_height is None) != (
            other.orthographic_height is None
        ) and 0.0 < t < 1.0:
            raise ValueError(
                "Camera3D projection mode cannot change during a positive-duration clip"
            )

        def mix(a: float, b: float) -> float:
            return a + (b - a) * t

        def mix3(a: Vec3, b: Vec3) -> Vec3:
            return Vec3(mix(a.x, b.x), mix(a.y, b.y), mix(a.z, b.z))

        if self.orthographic_height is None:
            ortho = None
        elif other.orthographic_height is None:
            ortho = None
        else:
            ortho = mix(self.orthographic_height, other.orthographic_height)
        return Camera3DState(
            position=mix3(self.position, other.position),
            target=mix3(self.target, other.target),
            up=mix3(self.up, other.up),
            fov_y_degrees=mix(self.fov_y_degrees, other.fov_y_degrees),
            near=mix(self.near, other.near),
            far=mix(self.far, other.far),
            orthographic_height=ortho,
            layer_z_index=self.layer_z_index if t < 1.0 else other.layer_z_index,
        )


@dataclass(slots=True)
class Camera3D:
    """Scene-owned 3D camera. Direct field mutation stops once attached to a Scene."""

    position: Vec3 = Vec3(4.5, 3.2, 5.5)
    target: Vec3 = Vec3()
    up: Vec3 = Vec3(0.0, 1.0, 0.0)
    fov_y_degrees: float = 45.0
    near: float = 0.05
    far: float = 100.0
    orthographic_height: float | None = None
    layer_z_index: int = 0
    _scene: "Scene | None" = field(default=None, init=False, repr=False, compare=False)
    _zanim_scene_registered: bool = field(default=False, init=False, repr=False, compare=False)

    def __setattr__(self, name: str, value) -> None:
        if not name.startswith("_") and getattr(self, "_zanim_scene_registered", False):
            raise RuntimeError(
                f"cannot assign {name!r} after Camera3D is attached to Scene; use camera3d.configure(...)"
            )
        object.__setattr__(self, name, value)

    def __post_init__(self) -> None:
        self.state()

    def state(self) -> Camera3DState:
        if self._scene is not None:
            return self._scene._camera3d_authored
        return Camera3DState(
            self.position,
            self.target,
            self.up,
            float(self.fov_y_degrees),
            float(self.near),
            float(self.far),
            self.orthographic_height,
            int(self.layer_z_index),
        )

    def _bind_scene(self, scene: "Scene") -> None:
        if self._scene is not None and self._scene is not scene:
            raise ValueError("Camera3D is already bound to a different Scene")
        object.__setattr__(self, "_scene", scene)
        object.__setattr__(self, "_zanim_scene_registered", True)

    def configure(
        self,
        to: "Camera3D | Camera3DState",
        *,
        duration: float | None = None,
        easing=None,
        at: float = 0.0,
    ):
        """Animate to one complete 3D camera state."""
        if self._scene is None:
            raise RuntimeError("Camera3D.configure() requires a Scene-bound camera")
        target = to.state() if isinstance(to, Camera3D) else to
        if not isinstance(target, Camera3DState):
            raise TypeError("camera3d.configure(to=...) requires Camera3D or Camera3DState")
        return self._scene._camera3d_to(target, duration=duration, easing=easing, at=at)
