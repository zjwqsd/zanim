from __future__ import annotations

from typing import TYPE_CHECKING

from .space import LOCAL, PARENT, SE2, WORLD, Point2, Transform2D, TransformFrame, Vec2, as_vec2

if TYPE_CHECKING:
    from .bounds import Bounds2D


class SceneObject2D:
    """Common initial-authoring surface shared by every 2D scene object."""

    transform: Transform2D
    opacity: float
    z_index: int

    def __setattr__(self, name: str, value) -> None:
        if not name.startswith("_") and getattr(self, "_zanim_scene_registered", False):
            raise RuntimeError(
                f"cannot assign {name!r} after Scene.add(); animate the bound handle instead"
            )
        object.__setattr__(self, name, value)

    def _validate_scene_state(self) -> None:
        if isinstance(self.transform, SE2):
            self.transform = self.transform.as_affine()
        elif not isinstance(self.transform, Transform2D):
            raise TypeError("2D object transform must be Transform2D or SE2")
        if not 0.0 <= float(self.opacity) <= 1.0:
            raise ValueError("opacity must be in [0, 1]")
        self.z_index = int(self.z_index)

    def _mark_scene_registered(self) -> None:
        self._zanim_scene_registered = True

    def _require_layout_mutable(self) -> None:
        if getattr(self, "_zanim_scene_registered", False):
            raise RuntimeError(
                "object is already registered in a Scene; animate the bound handle instead"
            )

    def _translate_parent(self, delta: Point2):
        self._require_layout_mutable()
        delta = as_vec2(delta, name="delta")
        self.transform = Transform2D.translation(delta.x, delta.y) @ self.transform
        return self

    def bounds(self) -> "Bounds2D":
        from .bounds import bounds_of

        return bounds_of(self)

    @property
    def center(self) -> Vec2:
        return self.bounds().center

    @property
    def origin(self) -> Vec2:
        return self.transform.apply(Vec2())

    def anchor(self, anchor) -> Vec2:
        from .layout import _anchor

        a = _anchor(anchor)
        bounds = self.bounds()
        return Vec2(
            bounds.center.x + a.x * bounds.width * 0.5,
            bounds.center.y + a.y * bounds.height * 0.5,
        )

    def place(self, *, anchor, at: Point2):
        """Place one visual anchor at a point in the current parent layout space."""
        at = as_vec2(at, name="at")
        return self._translate_parent(at - self.anchor(anchor))

    def move(
        self,
        *,
        by: Point2 | None = None,
        to: Point2 | None = None,
        frame: TransformFrame | None = None,
        anchor=None,
    ):
        """Set initial translation with the same vocabulary as bound animation."""
        self._require_layout_mutable()
        if (by is None) == (to is None):
            raise ValueError("move() requires exactly one of by= or to=")
        if by is not None:
            if anchor is not None:
                raise ValueError("move(by=...) does not accept anchor=")
            if frame is None:
                raise ValueError("move(by=...) requires LOCAL or PARENT")
            if frame is WORLD:
                raise ValueError("WORLD motion requires Scene ownership; call Scene.add() first")
            if frame not in (LOCAL, PARENT):
                raise TypeError("frame must be LOCAL, PARENT, or WORLD")
            delta = as_vec2(by, name="by")
            op = Transform2D.translation(delta.x, delta.y)
            self.transform = self.transform @ op if frame is LOCAL else op @ self.transform
            return self

        if frame is not None:
            raise ValueError("move(to=...) does not accept frame=")
        from .layout import CENTER

        return self.place(anchor=CENTER if anchor is None else anchor, at=as_vec2(to, name="to"))

    def rotate(
        self,
        *,
        by: float,
        frame: TransformFrame | None = None,
        about: Point2 | None = None,
    ):
        """Set initial rotation in LOCAL/PARENT, or around one explicit pivot."""
        self._require_layout_mutable()
        angle = float(by)
        if about is not None:
            if frame is not None:
                raise ValueError("rotate() accepts either frame= or about=, not both")
            pivot = as_vec2(about, name="about")
            self.transform = (
                Transform2D.translation(pivot.x, pivot.y)
                @ Transform2D.rotation(angle)
                @ Transform2D.translation(-pivot.x, -pivot.y)
                @ self.transform
            )
            return self
        if frame is None:
            raise ValueError("rotate() requires LOCAL/PARENT or about=")
        if frame is WORLD:
            raise ValueError("WORLD rotation requires Scene ownership; call Scene.add() first")
        if frame not in (LOCAL, PARENT):
            raise TypeError("frame must be LOCAL, PARENT, or WORLD")
        op = Transform2D.rotation(angle)
        self.transform = self.transform @ op if frame is LOCAL else op @ self.transform
        return self

    def scale(
        self,
        *,
        by: float,
        frame: TransformFrame | None = None,
        about: Point2 | None = None,
    ):
        """Set initial scale in LOCAL/PARENT, or around one explicit pivot."""
        self._require_layout_mutable()
        factor = float(by)
        if factor < 0:
            raise ValueError("scale(by=...) must be >= 0")
        if about is not None:
            if frame is not None:
                raise ValueError("scale() accepts either frame= or about=, not both")
            pivot = as_vec2(about, name="about")
            self.transform = (
                Transform2D.translation(pivot.x, pivot.y)
                @ Transform2D.scaling(factor)
                @ Transform2D.translation(-pivot.x, -pivot.y)
                @ self.transform
            )
            return self
        if frame is None:
            raise ValueError("scale() requires LOCAL/PARENT or about=")
        if frame is WORLD:
            raise ValueError("WORLD scaling requires Scene ownership; call Scene.add() first")
        if frame not in (LOCAL, PARENT):
            raise TypeError("frame must be LOCAL, PARENT, or WORLD")
        op = Transform2D.scaling(factor)
        self.transform = self.transform @ op if frame is LOCAL else op @ self.transform
        return self

    def next_to(
        self,
        other: "SceneObject2D | Point2",
        direction: Vec2 = Vec2(1, 0),
        buff: float = 0.25,
    ):
        """Place this object next to another object or point."""
        if buff < 0:
            raise ValueError("buff must be >= 0")
        norm = direction.length
        if norm <= 1e-12:
            raise ValueError("next_to direction must be non-zero")
        d = direction / norm
        source = self.bounds().point(-d)
        target = (
            other.bounds().point(d)
            if isinstance(other, SceneObject2D)
            else as_vec2(other, name="other")
        )
        return self._translate_parent(target + d * float(buff) - source)
