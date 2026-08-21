from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from .geometry import Color, Style
from .space import SE2, Transform2D, TransformFrame, Vec2, affine2d, pose2d
from .timeline import Easing

if TYPE_CHECKING:
    from .scene import Scene, SceneItem

T = TypeVar("T")
Point2 = Vec2 | tuple[float, float]
Scale2 = float | tuple[float, float]


def _vec2(value: Point2, *, name: str) -> Vec2:
    if isinstance(value, Vec2):
        return value
    if isinstance(value, tuple) and len(value) == 2:
        x, y = value
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            return Vec2(float(x), float(y))
    raise TypeError(f"{name} must be Vec2 or a numeric (x, y) tuple")



@dataclass(frozen=True, slots=True)
class BoundItem(Generic[T]):
    """A Scene-bound authoring handle for one already-registered item.

    The handle owns no render state and does not replace object identity. It only
    binds an existing object to the Scene timeline so post-add operations no
    longer need to repeat ``scene`` and ``object`` at every call.
    """

    scene: "Scene"
    raw: T

    @property
    def object_id(self) -> int:
        return self.scene._require_registered(self.raw).object_id  # type: ignore[arg-type]

    def remove(self) -> None:
        self.scene.remove(self)


@dataclass(frozen=True, slots=True)
class Bound2D(BoundItem[T]):
    """Bound handle for a 2D object/group with transform and opacity channels."""

    @property
    def transform_value(self) -> Transform2D:
        return self.raw.transform  # type: ignore[attr-defined]

    @property
    def opacity_value(self) -> float:
        return float(self.raw.opacity)  # type: ignore[attr-defined]

    @property
    def center(self) -> Vec2:
        return self.scene.world_anchor(self.raw)  # type: ignore[arg-type]

    @property
    def origin(self) -> Vec2:
        return self.scene.world_point(self.raw)  # type: ignore[arg-type]

    def anchor(self, anchor=None) -> Vec2:
        return self.scene.world_anchor(self.raw, anchor)  # type: ignore[arg-type]

    def world_transform(self, *, time: float | None = None) -> Transform2D:
        return self.scene.world_transform(self.raw, time=time)  # type: ignore[arg-type]

    def world_point(self, point: Point2 = Vec2(), *, time: float | None = None) -> Vec2:
        return self.scene.world_point(
            self.raw, _vec2(point, name="point"), time=time  # type: ignore[arg-type]
        )

    def transform(
        self,
        *,
        by=None,
        to=None,
        frame: TransformFrame | None = None,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.transform(
            self.raw, by=by, to=to, frame=frame,
            duration=duration, easing=easing, at=at,
        )

    def set_transform(self, *, to, at: float = 0.0):
        return self.scene.set_transform(self.raw, to=to, at=at)

    def move(
        self,
        *,
        by: Point2 | None = None,
        to: Point2 | None = None,
        frame: TransformFrame | None = None,
        anchor=None,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        delta = None if by is None else _vec2(by, name="by")
        target = None if to is None else _vec2(to, name="to")
        return self.scene.move(
            self.raw, by=delta, to=target, frame=frame, anchor=anchor,
            duration=duration, easing=easing, at=at,
        )

    def rotate(
        self,
        *,
        by: float,
        frame: TransformFrame | None = None,
        about: Point2 | None = None,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        pivot = None if about is None else _vec2(about, name="about")
        return self.scene.rotate(
            self.raw, by=by, frame=frame, about=pivot,
            duration=duration, easing=easing, at=at,
        )

    def scale(
        self,
        *,
        by: float,
        frame: TransformFrame | None = None,
        about: Point2 | None = None,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        pivot = None if about is None else _vec2(about, name="about")
        return self.scene.scale(
            self.raw, by=by, frame=frame, about=pivot,
            duration=duration, easing=easing, at=at,
        )

    def pose(
        self,
        *,
        to: Point2,
        rotation: float = 0.0,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate to one complete rigid pose ``SE2(rotation, to)``."""
        return self.scene.transform(
            self.raw,
            to=pose2d(to=to, rotation=rotation),
            duration=duration, easing=easing, at=at,
        )

    def affine(
        self,
        *,
        to: Point2,
        rotation: float = 0.0,
        scale: Scale2 = 1.0,
        shear: Point2 = (0.0, 0.0),
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate to one complete affine pose.

        The target is constructed in the fixed order
        ``Translation @ Rotation @ Shear @ Scale``. Omitted rotation, shear and
        scale use their identity values; ``to`` is required so this never
        silently preserves an unspecified translation component.
        """
        target = affine2d(to=to, rotation=rotation, scale=scale, shear=shear)
        return self.scene.transform(
            self.raw, to=target, duration=duration, easing=easing, at=at
        )

    def transform_function(
        self,
        provider,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.transform_function(
            self.raw, provider, duration=duration, easing=easing, at=at
        )

    def opacity(
        self,
        *,
        to: float,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.opacity(
            self.raw, to=to, duration=duration, easing=easing, at=at
        )

    def fade_in(
        self,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.fade_in(
            self.raw, duration=duration, easing=easing, at=at
        )

    def fade_out(
        self,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.fade_out(
            self.raw, duration=duration, easing=easing, at=at
        )


@dataclass(frozen=True, slots=True)
class BoundObject2D(Bound2D[T]):
    def create(
        self,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.create(
            self.raw, duration=duration, easing=easing, at=at
        )

    def style(
        self,
        *,
        to,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.style(
            self.raw, to=to, duration=duration, easing=easing, at=at
        )

    def fill(
        self,
        color: Color,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate to a fill-only style."""
        if not isinstance(color, Color):
            raise TypeError("fill() requires Color")
        return self.style(
            to=Style.solid(color), duration=duration, easing=easing, at=at
        )

    def outline(
        self,
        color: Color,
        *,
        width: float = 0.035,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate to an outline-only style."""
        if not isinstance(color, Color):
            raise TypeError("outline() requires Color")
        return self.style(
            to=Style.outline(color, float(width)),
            duration=duration, easing=easing, at=at,
        )

    def paint(
        self,
        *,
        fill: Color,
        stroke: Color,
        stroke_width: float = 0.035,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate to an explicit fill + outline style."""
        if not isinstance(fill, Color) or not isinstance(stroke, Color):
            raise TypeError("paint() fill and stroke must be Color")
        return self.style(
            to=Style.paint(fill, stroke, float(stroke_width)),
            duration=duration, easing=easing, at=at,
        )

    def trim(
        self,
        *,
        to: float,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.trim(
            self.raw, to=to, duration=duration, easing=easing, at=at
        )


@dataclass(frozen=True, slots=True)
class BoundVector2D(Bound2D[T]):
    def create(
        self,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.create(
            self.raw, duration=duration, easing=easing, at=at
        )

    def reveal(
        self,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.reveal(
            self.raw, duration=duration, easing=easing, at=at
        )


@dataclass(frozen=True, slots=True)
class BoundBatch2D(Bound2D[T]):
    def batch(
        self,
        *,
        to,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene.batch(
            self.raw, to=to, duration=duration, easing=easing, at=at
        )


@dataclass(frozen=True, slots=True)
class BoundRaster2D(Bound2D[T]):
    def media(
        self,
        duration: float | None = None,
        *,
        source_start: float = 0.0,
        speed: float = 1.0,
        loop: bool = False,
        at: float = 0.0,
    ):
        return self.scene.media(
            self.raw, duration, source_start=source_start, speed=speed, loop=loop, at=at
        )


@dataclass(frozen=True, slots=True)
class BoundGroup2D(Bound2D[T]):
    @property
    def children(self):
        return tuple(self.scene.on(child) for child in self.raw.children)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class BoundMesh3D(BoundItem[T]):
    @property
    def transform_value(self):
        return self.raw.transform  # type: ignore[attr-defined]

    def transform(self, *, by=None, to=None, frame=None, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self.scene.transform(
            self.raw, by=by, to=to, frame=frame,
            duration=duration, easing=easing, at=at,
        )

    def transform_function(self, provider, *, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self.scene.transform_function(
            self.raw, provider, duration=duration, easing=easing, at=at
        )

    def opacity(self, *, to: float, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self.scene.opacity(
            self.raw, to=to, duration=duration, easing=easing, at=at
        )

    def fade_in(self, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self.scene.fade_in(self.raw, duration=duration, easing=easing, at=at)

    def fade_out(self, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self.scene.fade_out(self.raw, duration=duration, easing=easing, at=at)


@dataclass(frozen=True, slots=True)
class BoundValue(BoundItem[T]):
    @property
    def current(self) -> float:
        return float(self.raw.value)  # type: ignore[attr-defined]

    def value(self, *, to: float, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self.scene.value(
            self.raw, to=to, duration=duration, easing=easing, at=at
        )

    def at(self, time: float) -> float:
        return self.raw.value_at(time)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class BoundAudio(BoundItem[T]):
    def media(
        self,
        duration: float | None = None,
        *,
        source_start: float = 0.0,
        speed: float = 1.0,
        loop: bool = False,
        at: float = 0.0,
    ):
        return self.scene.media(
            self.raw, duration, source_start=source_start, speed=speed, loop=loop, at=at
        )
