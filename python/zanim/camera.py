from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .object import SceneObject2D
from .space import Transform2D, Vec2

CameraTransformProvider = Callable[[float], Transform2D]


@dataclass(slots=True)
class Camera2D(SceneObject2D):
    """2D world-to-view transform.

    A camera is either timeline-driven (the default) or driven by a pure
    absolute-time ``transform_provider``.  Keeping these modes exclusive makes
    random-access evaluation unambiguous.
    """

    transform: Transform2D = Transform2D()
    opacity: float = 1.0
    z_index: int = 0
    transform_provider: CameraTransformProvider | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._validate_scene_state()
        if self.transform_provider is not None and not callable(self.transform_provider):
            raise TypeError("camera transform_provider must be callable")

    @property
    def is_dynamic(self) -> bool:
        return self.transform_provider is not None

    def transform_at(self, time: float, initial: Transform2D | None = None) -> Transform2D:
        if self.transform_provider is None:
            return self.transform if initial is None else initial
        value = self.transform_provider(float(time))
        if not isinstance(value, Transform2D):
            raise TypeError("camera transform_provider must return Transform2D")
        return value

    def bounds(self):
        raise TypeError("Camera2D has no object bounds")

    def pan(self, x: float, y: float) -> "Camera2D":
        if self.is_dynamic:
            raise TypeError("dynamic Camera2D transform is owned by transform_provider")
        # Camera motion is opposite to the world-to-view translation.
        self.transform = Transform2D.translation(-x, -y) @ self.transform
        return self

    def zoom(self, factor: float, center: Vec2 = Vec2()) -> "Camera2D":
        if self.is_dynamic:
            raise TypeError("dynamic Camera2D transform is owned by transform_provider")
        if factor <= 0:
            raise ValueError("camera zoom must be positive")
        self.transform = (
            Transform2D.translation(center.x, center.y)
            @ Transform2D.scaling(factor)
            @ Transform2D.translation(-center.x, -center.y)
            @ self.transform
        )
        return self

    def rotate_view(self, radians: float, center: Vec2 = Vec2()) -> "Camera2D":
        if self.is_dynamic:
            raise TypeError("dynamic Camera2D transform is owned by transform_provider")
        self.transform = (
            Transform2D.translation(center.x, center.y)
            @ Transform2D.rotation(-radians)
            @ Transform2D.translation(-center.x, -center.y)
            @ self.transform
        )
        return self
