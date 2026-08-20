from __future__ import annotations

from typing import TYPE_CHECKING
from .space import Transform2D, Vec2

ORIGIN = Vec2(0, 0)
RIGHT = Vec2(1, 0)
LEFT = Vec2(-1, 0)
UP = Vec2(0, 1)
DOWN = Vec2(0, -1)

if TYPE_CHECKING:
    from .bounds import Bounds2D


class SceneObject2D:
    """Small common authoring surface shared by every 2D scene object.

    Render representation remains specialized (geometry, batch, vector).  This
    class only unifies state and spatial authoring operations; it is not a
    renderer-side scene graph node.
    """

    transform: Transform2D
    opacity: float
    z_index: int

    def _validate_scene_state(self) -> None:
        if not 0.0 <= float(self.opacity) <= 1.0:
            raise ValueError("opacity must be in [0, 1]")
        self.z_index = int(self.z_index)

    def bounds(self) -> "Bounds2D":
        from .bounds import bounds_of
        return bounds_of(self)

    def shift(self, x: float | Vec2, y: float | None = None):
        if isinstance(x, Vec2):
            if y is not None:
                raise TypeError("y must be omitted when shifting by Vec2")
            delta = x
        else:
            if y is None:
                raise TypeError("shift(x, y) requires both coordinates")
            delta = Vec2(float(x), float(y))
        self.transform = Transform2D.translation(delta.x, delta.y) @ self.transform
        return self

    def move_to(self, target: Vec2 | "SceneObject2D"):
        point = target.bounds().center if isinstance(target, SceneObject2D) else target
        current = self.bounds().center
        return self.shift(point.x - current.x, point.y - current.y)

    def align_to(self, other: "SceneObject2D", direction: Vec2):
        source = self.bounds().point(direction)
        target = other.bounds().point(direction)
        if abs(direction.x) >= abs(direction.y):
            return self.shift(target.x - source.x, 0.0)
        return self.shift(0.0, target.y - source.y)

    def next_to(self, other: "SceneObject2D", direction: Vec2 = Vec2(1, 0), buff: float = 0.25):
        if buff < 0:
            raise ValueError("buff must be >= 0")
        norm = (direction.x * direction.x + direction.y * direction.y) ** 0.5
        if norm <= 1e-12:
            raise ValueError("next_to direction must be non-zero")
        d = Vec2(direction.x / norm, direction.y / norm)
        source = self.bounds().point(Vec2(-d.x, -d.y))
        target = other.bounds().point(d)
        return self.shift(target.x + d.x * buff - source.x, target.y + d.y * buff - source.y)

    def to_edge(self, canvas, direction: Vec2, buff: float = 0.25):
        if buff < 0:
            raise ValueError("buff must be >= 0")
        norm = (direction.x * direction.x + direction.y * direction.y) ** 0.5
        if norm <= 1e-12:
            raise ValueError("to_edge direction must be non-zero")
        d = Vec2(direction.x / norm, direction.y / norm)
        half_w = canvas.width / (2.0 * canvas.unit_size)
        half_h = canvas.height / (2.0 * canvas.unit_size)
        bounds = self.bounds()
        dx = dy = 0.0
        if d.x > 1e-12:
            dx = half_w - buff - bounds.right
        elif d.x < -1e-12:
            dx = -half_w + buff - bounds.left
        if d.y > 1e-12:
            dy = half_h - buff - bounds.top
        elif d.y < -1e-12:
            dy = -half_h + buff - bounds.bottom
        return self.shift(dx, dy)

    def scale_about(self, factor: float, about: Vec2 | None = None):
        if factor < 0:
            raise ValueError("scale factor must be >= 0")
        center = self.bounds().center if about is None else about
        op = (
            Transform2D.translation(center.x, center.y)
            @ Transform2D.scaling(float(factor))
            @ Transform2D.translation(-center.x, -center.y)
        )
        self.transform = op @ self.transform
        return self

    def rotate_about(self, radians: float, about: Vec2 | None = None):
        center = self.bounds().center if about is None else about
        op = (
            Transform2D.translation(center.x, center.y)
            @ Transform2D.rotation(float(radians))
            @ Transform2D.translation(-center.x, -center.y)
        )
        self.transform = op @ self.transform
        return self

    def set_opacity(self, opacity: float):
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be in [0, 1]")
        self.opacity = float(opacity)
        return self

    def set_z_index(self, z_index: int):
        self.z_index = int(z_index)
        return self
