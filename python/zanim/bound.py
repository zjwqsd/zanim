from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from .geometry import DEFAULT_STROKE_WIDTH, Color, StrokeStyle, Style
from .space import Point2, Transform2D, TransformFrame, Vec2, affine2d, as_vec2
from .space3d import Transform3D, Vec3
from .timeline import Easing

if TYPE_CHECKING:
    from .scene import Scene

T = TypeVar("T")
Scale2 = float | tuple[float, float]
_UNSET = object()


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
        return self.scene._authored_get(self.raw, "transform")

    @property
    def opacity_value(self) -> float:
        return float(self.scene._authored_get(self.raw, "opacity"))

    @property
    def center(self) -> Vec2:
        return self.scene._world_anchor(self.raw)  # type: ignore[arg-type]

    @property
    def origin(self) -> Vec2:
        return self.scene._world_point(self.raw)  # type: ignore[arg-type]

    def anchor(self, anchor=None) -> Vec2:
        return self.scene._world_anchor(self.raw, anchor)  # type: ignore[arg-type]

    def world_transform(self, *, time: float | None = None) -> Transform2D:
        return self.scene._world_transform(self.raw, time=time)  # type: ignore[arg-type]

    def world_point(self, point: Point2 = Vec2(), *, time: float | None = None) -> Vec2:
        return self.scene._world_point(
            self.raw,
            as_vec2(point, name="point"),
            time=time,  # type: ignore[arg-type]
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
        return self.scene._transform(
            self.raw,
            by=by,
            to=to,
            frame=frame,
            duration=duration,
            easing=easing,
            at=at,
        )

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
        delta = None if by is None else as_vec2(by, name="by")
        target = None if to is None else as_vec2(to, name="to")
        return self.scene._move(
            self.raw,
            by=delta,
            to=target,
            frame=frame,
            anchor=anchor,
            duration=duration,
            easing=easing,
            at=at,
        )

    def move_along(
        self,
        path,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
        samples: int = 256,
        tolerance: float = 1e-3,
    ):
        return self.scene._move_along(
            self.raw,
            path,
            duration=duration,
            easing=easing,
            at=at,
            samples=samples,
            tolerance=tolerance,
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
        pivot = None if about is None else as_vec2(about, name="about")
        return self.scene._rotate(
            self.raw,
            by=by,
            frame=frame,
            about=pivot,
            duration=duration,
            easing=easing,
            at=at,
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
        pivot = None if about is None else as_vec2(about, name="about")
        return self.scene._scale(
            self.raw,
            by=by,
            frame=frame,
            about=pivot,
            duration=duration,
            easing=easing,
            at=at,
        )

    def affine(
        self,
        *,
        position: Point2,
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
        scale use their identity values; ``position`` is required so this never
        silently preserves an unspecified translation component.
        """
        target = affine2d(position=position, rotation=rotation, scale=scale, shear=shear)
        return self.scene._transform(self.raw, to=target, duration=duration, easing=easing, at=at)

    def transform_function(
        self,
        provider,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene._transform_function(
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
        return self.scene._opacity_to(self.raw, to, duration=duration, easing=easing, at=at)

    def fade_in(
        self,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene._fade_in(self.raw, duration=duration, easing=easing, at=at)

    def fade_out(
        self,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene._fade_out(self.raw, duration=duration, easing=easing, at=at)


@dataclass(frozen=True, slots=True)
class BoundObject2D(Bound2D[T]):
    @property
    def style_value(self):
        return self.scene._authored_get(self.raw, "style")

    @property
    def trim_value(self) -> float:
        return float(self.scene._authored_get(self.raw, "trim"))

    def create(
        self,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene._create(self.raw, duration=duration, easing=easing, at=at)

    def style(
        self,
        *,
        fill=_UNSET,
        stroke=_UNSET,
        stroke_width: float | None = None,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate selected visual style fields while preserving omitted fields."""
        current = self.style_value

        if fill is _UNSET:
            next_fill = current.fill
        else:
            if fill is not None and not isinstance(fill, Color):
                raise TypeError("fill must be Color or None")
            next_fill = fill

        if stroke is _UNSET:
            next_stroke = current.stroke
            if stroke_width is not None:
                if next_stroke is None:
                    raise ValueError("stroke_width requires an existing or explicit stroke")
                next_stroke = StrokeStyle(next_stroke.color, float(stroke_width))
        else:
            if stroke is not None and not isinstance(stroke, Color):
                raise TypeError("stroke must be Color or None")
            if stroke is None:
                if stroke_width is not None:
                    raise ValueError("stroke_width cannot be used with stroke=None")
                next_stroke = None
            else:
                width = (
                    float(stroke_width)
                    if stroke_width is not None
                    else current.stroke.width
                    if current.stroke is not None
                    else DEFAULT_STROKE_WIDTH
                )
                next_stroke = StrokeStyle(stroke, width)

        target = Style(fill=next_fill, stroke=next_stroke)
        return self.scene._style_to(self.raw, target, duration=duration, easing=easing, at=at)

    def trim(
        self,
        *,
        to: float,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene._trim_to(self.raw, to, duration=duration, easing=easing, at=at)


@dataclass(frozen=True, slots=True)
class BoundVector2D(Bound2D[T]):
    @property
    def document_value(self):
        return self.scene._authored_get(self.raw, "document")

    def morph(
        self,
        *,
        to,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene._morph_vector(self.raw, to, duration=duration, easing=easing, at=at)

    def create(
        self,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene._create(self.raw, duration=duration, easing=easing, at=at)


@dataclass(frozen=True, slots=True)
class BoundBatch2D(Bound2D[T]):
    @property
    def batch_value(self):
        return self.scene._authored_get(self.raw, "batch")

    def batch(
        self,
        *,
        to,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        return self.scene._batch_to(self.raw, to, duration=duration, easing=easing, at=at)


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
        return self.scene._media(
            self.raw, duration, source_start=source_start, speed=speed, loop=loop, at=at
        )


@dataclass(frozen=True, slots=True)
class BoundGroup(Bound2D[T]):
    @property
    def children(self):
        return tuple(self.scene._handle(child) for child in self.raw.children)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class Bound3D(BoundItem[T]):
    @property
    def transform_value(self) -> Transform3D:
        return self.scene._authored_get(self.raw, "transform")

    def world_transform(self, *, time: float | None = None) -> Transform3D:
        return self.scene._world_transform3d(self.raw, time=time)

    def world_point(self, point: Vec3 = Vec3(), *, time: float | None = None) -> Vec3:
        return self.world_transform(time=time).apply(point)

    def transform(
        self,
        *,
        by=None,
        to=None,
        frame=None,
        duration: float | None = None,
        easing=Easing.SMOOTHSTEP,
        at=0.0,
    ):
        return self.scene._transform(
            self.raw,
            by=by,
            to=to,
            frame=frame,
            duration=duration,
            easing=easing,
            at=at,
        )

    def transform_function(
        self, provider, *, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        return self.scene._transform_function(
            self.raw, provider, duration=duration, easing=easing, at=at
        )

    def opacity(
        self, *, to: float, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        return self.scene._opacity_to(self.raw, to, duration=duration, easing=easing, at=at)

    def fade_in(self, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self.scene._fade_in(self.raw, duration=duration, easing=easing, at=at)

    def fade_out(self, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self.scene._fade_out(self.raw, duration=duration, easing=easing, at=at)


@dataclass(frozen=True, slots=True)
class BoundGroup3D(Bound3D[T]):
    @property
    def children(self):
        return tuple(self.scene._handle(child) for child in self.raw.children)  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class BoundMesh3D(Bound3D[T]):
    pass


@dataclass(frozen=True, slots=True)
class BoundValue(BoundItem[T]):
    @property
    def current(self) -> float:
        return float(self.scene._authored_get(self.raw, "value"))

    def value(self, *, to: float, duration: float | None = None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self.scene._value_to(self.raw, to, duration=duration, easing=easing, at=at)

    def at(self, time: float) -> float:
        return self.scene.value_at(self.raw, time)


@dataclass(frozen=True, slots=True)
class BoundAudio(BoundItem[T]):
    @property
    def duration(self) -> float:
        return self.raw.duration

    def media(
        self,
        duration: float | None = None,
        *,
        source_start: float = 0.0,
        speed: float = 1.0,
        loop: bool = False,
        at: float = 0.0,
    ):
        return self.scene._media(
            self.raw, duration, source_start=source_start, speed=speed, loop=loop, at=at
        )
