from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

from .batch import BatchGeometry
from .geometry import Color, StrokeStyle, Style
from .interpolation import ObjectInterpolation
from .space import Transform2D


class Easing(str, Enum):
    LINEAR = "linear"
    SMOOTHSTEP = "smoothstep"

    def apply(self, alpha: float) -> float:
        t = max(0.0, min(1.0, alpha))
        if self is Easing.LINEAR:
            return t
        if self is Easing.SMOOTHSTEP:
            return t * t * (3.0 - 2.0 * t)
        raise AssertionError(f"unhandled easing: {self}")


@dataclass(frozen=True, slots=True)
class TimeSpan:
    start: float
    duration: float

    def __post_init__(self) -> None:
        if self.duration < 0:
            raise ValueError("duration must be >= 0")

    @property
    def end(self) -> float:
        return self.start + self.duration

    def alpha(self, time: float, easing: Easing) -> float:
        if self.duration == 0:
            return 1.0 if time >= self.start else 0.0
        return easing.apply((time - self.start) / self.duration)

    def contains(self, time: float) -> bool:
        return time == self.start if self.duration == 0 else self.start <= time < self.end

    def overlaps(self, other: "TimeSpan") -> bool:
        if self.duration == 0 or other.duration == 0:
            return False
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True, slots=True)
class TransformClip:
    object_id: int
    span: TimeSpan
    before: Transform2D
    after: Transform2D
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> Transform2D:
        return lerp_transform(self.before, self.after, self.span.alpha(time, self.easing))


@dataclass(frozen=True, slots=True)
class OpacityClip:
    object_id: int
    span: TimeSpan
    before: float
    after: float
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> float:
        return _lerp(self.before, self.after, self.span.alpha(time, self.easing))


@dataclass(frozen=True, slots=True)
class StyleClip:
    object_id: int
    span: TimeSpan
    before: Style
    after: Style
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> Style:
        return lerp_style(self.before, self.after, self.span.alpha(time, self.easing))


@dataclass(frozen=True, slots=True)
class PathTrimClip:
    object_id: int
    span: TimeSpan
    before: float
    after: float
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> float:
        return _lerp(self.before, self.after, self.span.alpha(time, self.easing))


@dataclass(frozen=True, slots=True)
class BatchClip:
    object_id: int
    span: TimeSpan
    before: BatchGeometry
    after: BatchGeometry
    easing: Easing = Easing.SMOOTHSTEP

    def alpha(self, time: float) -> float:
        return self.span.alpha(time, self.easing)


@dataclass(frozen=True, slots=True)
class RevealClip:
    object_id: int
    span: TimeSpan
    before: float = 0.0
    after: float = 1.0
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> float:
        return _lerp(self.before, self.after, self.span.alpha(time, self.easing))


@dataclass(frozen=True, slots=True)
class ValueClip:
    value_id: int
    span: TimeSpan
    before: float
    after: float
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> float:
        return _lerp(self.before, self.after, self.span.alpha(time, self.easing))


@dataclass(frozen=True, slots=True)
class InterpolationClip:
    interpolation: ObjectInterpolation
    span: TimeSpan
    easing: Easing = Easing.SMOOTHSTEP

    def alpha(self, time: float) -> float:
        return self.span.alpha(time, self.easing)


Clip = (
    TransformClip | OpacityClip | StyleClip | PathTrimClip | BatchClip |
    RevealClip | ValueClip | InterpolationClip
)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_transform(a: Transform2D, b: Transform2D, t: float) -> Transform2D:
    return Transform2D(
        xx=_lerp(a.xx, b.xx, t), xy=_lerp(a.xy, b.xy, t),
        yx=_lerp(a.yx, b.yx, t), yy=_lerp(a.yy, b.yy, t),
        tx=_lerp(a.tx, b.tx, t), ty=_lerp(a.ty, b.ty, t),
    )


def _transparent(color: Color) -> Color:
    return Color(color.r, color.g, color.b, 0)


def _lerp_color(a: Color, b: Color, t: float) -> Color:
    return Color(*(
        max(0, min(255, round(_lerp(x, y, t))))
        for x, y in zip((a.r, a.g, a.b, a.a), (b.r, b.g, b.b, b.a))
    ))


def lerp_style(a: Style, b: Style, t: float) -> Style:
    if a.fill is None and b.fill is None:
        fill = None
    else:
        ca = a.fill if a.fill is not None else _transparent(b.fill)  # type: ignore[arg-type]
        cb = b.fill if b.fill is not None else _transparent(a.fill)  # type: ignore[arg-type]
        fill = _lerp_color(ca, cb, t)

    if a.stroke is None and b.stroke is None:
        stroke = None
    else:
        sa = a.stroke if a.stroke is not None else StrokeStyle(_transparent(b.stroke.color), b.stroke.width)  # type: ignore[union-attr]
        sb = b.stroke if b.stroke is not None else StrokeStyle(_transparent(a.stroke.color), a.stroke.width)  # type: ignore[union-attr]
        stroke = StrokeStyle(
            _lerp_color(sa.color, sb.color, t),
            max(1e-9, _lerp(sa.width, sb.width, t)),
        )
    return Style(fill=fill, stroke=stroke)


@dataclass(slots=True)
class Timeline:
    cursor: float = 0.0
    clips: list[Clip] = field(default_factory=list)
    _parallel_base: float | None = field(default=None, init=False, repr=False)
    _parallel_end: float | None = field(default=None, init=False, repr=False)

    def _span(self, duration: float, at: float) -> TimeSpan:
        return TimeSpan(self._schedule_base() + at, duration)

    def _append(self, clip, *, key_name: str | None = "object_id"):
        if key_name is not None:
            self._check_channel_conflict(clip, key_name)
        self.clips.append(clip)
        self._advance_after_schedule(clip.span.end)
        return clip

    def add_transform(self, object_id, before, after, duration=1.0, easing=Easing.SMOOTHSTEP, at=0.0):
        return self._append(TransformClip(object_id, self._span(duration, at), before, after, easing))

    def add_opacity(self, object_id, before, after, duration=1.0, easing=Easing.SMOOTHSTEP, at=0.0):
        if not (0 <= before <= 1 and 0 <= after <= 1):
            raise ValueError("opacity endpoints must be in [0, 1]")
        return self._append(OpacityClip(object_id, self._span(duration, at), before, after, easing))

    def add_style(self, object_id, before, after, duration=1.0, easing=Easing.SMOOTHSTEP, at=0.0):
        return self._append(StyleClip(object_id, self._span(duration, at), before, after, easing))

    def add_path_trim(self, object_id, before, after, duration=1.0, easing=Easing.SMOOTHSTEP, at=0.0):
        if not (0 <= before <= 1 and 0 <= after <= 1):
            raise ValueError("path trim endpoints must be in [0, 1]")
        return self._append(PathTrimClip(object_id, self._span(duration, at), before, after, easing))

    def add_batch(self, object_id, before, after, duration=1.0, easing=Easing.SMOOTHSTEP, at=0.0):
        if type(before) is not type(after) or len(before) != len(after):
            raise ValueError("batch clips require the same batch type and element count")
        return self._append(BatchClip(object_id, self._span(duration, at), before, after, easing))

    def add_reveal(self, object_id, duration=1.0, easing=Easing.SMOOTHSTEP, at=0.0, before=0.0, after=1.0):
        if not (0 <= before <= 1 and 0 <= after <= 1):
            raise ValueError("reveal endpoints must be in [0, 1]")
        return self._append(RevealClip(object_id, self._span(duration, at), before, after, easing))

    def add_value(self, value_id, before, after, duration=1.0, easing=Easing.SMOOTHSTEP, at=0.0):
        return self._append(ValueClip(value_id, self._span(duration, at), float(before), float(after), easing), key_name="value_id")

    def add_interpolation(self, interpolation, duration=1.0, easing=Easing.SMOOTHSTEP, at=0.0):
        return self._append(InterpolationClip(interpolation, self._span(duration, at), easing), key_name=None)

    def wait(self, duration: float = 1.0) -> TimeSpan:
        if self._parallel_base is not None:
            raise ValueError("wait() is not allowed inside parallel()")
        span = TimeSpan(self.cursor, duration)
        self.cursor = span.end
        return span

    @contextmanager
    def parallel(self) -> Iterator[None]:
        if self._parallel_base is not None:
            raise ValueError("nested parallel() blocks are not supported")
        self._parallel_base = self.cursor
        self._parallel_end = self.cursor
        try:
            yield
        finally:
            assert self._parallel_end is not None
            self.cursor = max(self.cursor, self._parallel_end)
            self._parallel_base = None
            self._parallel_end = None

    def _schedule_base(self) -> float:
        return self.cursor if self._parallel_base is None else self._parallel_base

    def _advance_after_schedule(self, end: float) -> None:
        if self._parallel_base is None:
            self.cursor = end
        else:
            assert self._parallel_end is not None
            self._parallel_end = max(self._parallel_end, end)

    def _check_channel_conflict(self, candidate, key_name: str) -> None:
        key = getattr(candidate, key_name)
        clip_type = type(candidate)
        for clip in self.clips:
            if (
                isinstance(clip, clip_type)
                and getattr(clip, key_name) == key
                and clip.span.overlaps(candidate.span)
            ):
                channel = clip_type.__name__.removesuffix("Clip").lower()
                raise ValueError(
                    f"overlapping {channel} clips for {key_name} {key}: "
                    f"[{clip.span.start}, {clip.span.end}) and "
                    f"[{candidate.span.start}, {candidate.span.end})"
                )
