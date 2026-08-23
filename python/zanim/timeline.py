from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Iterator

from .batch import BatchGeometry
from .geometry import Color, StrokeStyle, Style
from .interpolation import ObjectInterpolation
from .space import SE2, Transform2D
from .space3d import SE3, Transform3D


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
class SE2TransformClip:
    """Group-preserving rigid 2D transform interpolation."""

    object_id: int
    span: TimeSpan
    before: SE2
    after: SE2
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> Transform2D:
        return self.before.interpolate(self.after, self.span.alpha(time, self.easing)).as_affine()


@dataclass(frozen=True, slots=True)
class TransformFunctionClip:
    """Random-access transform animation driven by eased normalized time.

    The provider receives alpha in [0, 1] and returns the complete object
    transform for that instant.  Unlike a stateful updater, sampling does not
    depend on earlier frames.
    """

    object_id: int
    span: TimeSpan
    provider: Callable[[float], Transform2D]
    before: Transform2D
    after: Transform2D
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> Transform2D:
        value = self.provider(self.span.alpha(time, self.easing))
        if not isinstance(value, Transform2D):
            raise TypeError("transform function must return Transform2D")
        return value


@dataclass(frozen=True, slots=True)
class Transform3DClip:
    object_id: int
    span: TimeSpan
    before: Transform3D
    after: Transform3D
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> Transform3D:
        return lerp_transform3d(self.before, self.after, self.span.alpha(time, self.easing))


@dataclass(frozen=True, slots=True)
class SE3TransformClip:
    object_id: int
    span: TimeSpan
    before: SE3
    after: SE3
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> Transform3D:
        return self.before.interpolate(self.after, self.span.alpha(time, self.easing)).as_affine()


@dataclass(frozen=True, slots=True)
class Transform3DFunctionClip:
    object_id: int
    span: TimeSpan
    provider: Callable[[float], Transform3D]
    before: Transform3D
    after: Transform3D
    easing: Easing = Easing.SMOOTHSTEP

    def sample(self, time: float) -> Transform3D:
        value = self.provider(self.span.alpha(time, self.easing))
        if not isinstance(value, Transform3D):
            raise TypeError("3D transform function must return Transform3D")
        return value


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
class PlaybackClip:
    object_id: int
    span: TimeSpan
    source_start: float
    speed: float
    loop: bool
    source_duration: float | None

    def source_time(self, time: float) -> float:
        if not self.span.contains(time):
            raise ValueError("time is outside PlaybackClip span")
        if self.source_duration is None:
            return 0.0
        elapsed = max(0.0, float(time) - self.span.start) * self.speed
        if self.loop:
            loop_length = self.source_duration - self.source_start
            if loop_length <= 0:
                return self.source_start
            return self.source_start + (elapsed % loop_length)
        return min(self.source_duration, self.source_start + elapsed)


@dataclass(frozen=True, slots=True)
class InterpolationClip:
    interpolation: ObjectInterpolation
    span: TimeSpan
    easing: Easing = Easing.SMOOTHSTEP

    def alpha(self, time: float) -> float:
        return self.span.alpha(time, self.easing)


Clip = (
    TransformClip
    | SE2TransformClip
    | TransformFunctionClip
    | Transform3DClip
    | SE3TransformClip
    | Transform3DFunctionClip
    | OpacityClip
    | StyleClip
    | PathTrimClip
    | BatchClip
    | RevealClip
    | ValueClip
    | PlaybackClip
    | InterpolationClip
)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_transform(a: Transform2D, b: Transform2D, t: float) -> Transform2D:
    return Transform2D(
        xx=_lerp(a.xx, b.xx, t),
        xy=_lerp(a.xy, b.xy, t),
        yx=_lerp(a.yx, b.yx, t),
        yy=_lerp(a.yy, b.yy, t),
        tx=_lerp(a.tx, b.tx, t),
        ty=_lerp(a.ty, b.ty, t),
    )


def lerp_transform3d(a: Transform3D, b: Transform3D, t: float) -> Transform3D:
    return Transform3D(*(_lerp(x, y, t) for x, y in zip(a.as_tuple(), b.as_tuple())))


def _transparent(color: Color) -> Color:
    return Color(color.r, color.g, color.b, 0)


def _lerp_color(a: Color, b: Color, t: float) -> Color:
    return Color(
        *(
            max(0, min(255, round(_lerp(x, y, t))))
            for x, y in zip((a.r, a.g, a.b, a.a), (b.r, b.g, b.b, b.a))
        )
    )


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
        sa = (
            a.stroke
            if a.stroke is not None
            else StrokeStyle(_transparent(b.stroke.color), b.stroke.width)
        )  # type: ignore[union-attr]
        sb = (
            b.stroke
            if b.stroke is not None
            else StrokeStyle(_transparent(a.stroke.color), a.stroke.width)
        )  # type: ignore[union-attr]
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
    _parallel_duration: float | None = field(default=None, init=False, repr=False)
    _channels: dict[tuple[object, int], list[Clip]] = field(
        default_factory=dict, init=False, repr=False
    )

    @staticmethod
    def _channel_token(clip_or_type) -> object:
        transform_types = (
            TransformClip,
            SE2TransformClip,
            TransformFunctionClip,
            Transform3DClip,
            SE3TransformClip,
            Transform3DFunctionClip,
        )
        if isinstance(clip_or_type, type):
            return "transform" if clip_or_type in transform_types else clip_or_type
        return "transform" if isinstance(clip_or_type, transform_types) else type(clip_or_type)

    def _channel_clips(self, clip_type, key: int):
        """Return one object's clips for a logical channel in start-time order."""
        return self._channels.get((self._channel_token(clip_type), int(key)), ())

    def _resolve_duration(self, duration: float | None) -> float:
        """Resolve an omitted clip duration against the nearest authoring default."""
        if duration is not None:
            return float(duration)
        if self._parallel_base is not None and self._parallel_duration is not None:
            return self._parallel_duration
        return 1.0

    def _span(self, duration: float | None, at: float) -> TimeSpan:
        return TimeSpan(self._schedule_base() + at, self._resolve_duration(duration))

    def _append(self, clip, *, key_name: str | None = "object_id"):
        if key_name is not None:
            key = int(getattr(clip, key_name))
            channel_key = (self._channel_token(clip), key)
            entries = self._channels.setdefault(channel_key, [])
            self._check_channel_conflict(clip, key_name, entries)
            if entries and clip.span.start < entries[-1].span.start:
                raise ValueError(
                    "clips on the same channel must be authored in chronological order"
                )
            entries.append(clip)
        self.clips.append(clip)
        self._advance_after_schedule(clip.span.end)
        return clip

    def add_transform(
        self, object_id, before, after, duration=None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        return self._append(
            TransformClip(object_id, self._span(duration, at), before, after, easing)
        )

    def add_se2_transform(
        self, object_id, before, after, duration=None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        if not isinstance(before, SE2) or not isinstance(after, SE2):
            raise TypeError("SE2 transform clips require SE2 endpoints")
        return self._append(
            SE2TransformClip(object_id, self._span(duration, at), before, after, easing)
        )

    def add_transform_function(
        self, object_id, provider, before, duration=None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        span = self._span(duration, at)
        after = provider(1.0)
        if not isinstance(after, Transform2D):
            raise TypeError("transform function must return Transform2D")
        return self._append(TransformFunctionClip(object_id, span, provider, before, after, easing))

    def add_transform3d(
        self, object_id, before, after, duration=None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        return self._append(
            Transform3DClip(object_id, self._span(duration, at), before, after, easing)
        )

    def add_se3_transform(
        self, object_id, before, after, duration=None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        if not isinstance(before, SE3) or not isinstance(after, SE3):
            raise TypeError("SE3 transform clips require SE3 endpoints")
        return self._append(
            SE3TransformClip(object_id, self._span(duration, at), before, after, easing)
        )

    def add_transform3d_function(
        self, object_id, provider, before, duration=None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        span = self._span(duration, at)
        after = provider(1.0)
        if not isinstance(after, Transform3D):
            raise TypeError("3D transform function must return Transform3D")
        return self._append(
            Transform3DFunctionClip(object_id, span, provider, before, after, easing)
        )

    def add_opacity(
        self, object_id, before, after, duration=None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        if not (0 <= before <= 1 and 0 <= after <= 1):
            raise ValueError("opacity endpoints must be in [0, 1]")
        return self._append(OpacityClip(object_id, self._span(duration, at), before, after, easing))

    def add_style(self, object_id, before, after, duration=None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self._append(StyleClip(object_id, self._span(duration, at), before, after, easing))

    def add_path_trim(
        self, object_id, before, after, duration=None, easing=Easing.SMOOTHSTEP, at=0.0
    ):
        if not (0 <= before <= 1 and 0 <= after <= 1):
            raise ValueError("path trim endpoints must be in [0, 1]")
        return self._append(
            PathTrimClip(object_id, self._span(duration, at), before, after, easing)
        )

    def add_batch(self, object_id, before, after, duration=None, easing=Easing.SMOOTHSTEP, at=0.0):
        if type(before) is not type(after) or len(before) != len(after):
            raise ValueError("batch clips require the same batch type and element count")
        return self._append(BatchClip(object_id, self._span(duration, at), before, after, easing))

    def add_reveal(
        self, object_id, duration=None, easing=Easing.SMOOTHSTEP, at=0.0, before=0.0, after=1.0
    ):
        if not (0 <= before <= 1 and 0 <= after <= 1):
            raise ValueError("reveal endpoints must be in [0, 1]")
        return self._append(RevealClip(object_id, self._span(duration, at), before, after, easing))

    def add_value(self, value_id, before, after, duration=None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self._append(
            ValueClip(value_id, self._span(duration, at), float(before), float(after), easing),
            key_name="value_id",
        )

    def add_playback(
        self,
        object_id,
        duration,
        *,
        source_start=0.0,
        speed=1.0,
        loop=False,
        source_duration=None,
        at=0.0,
    ):
        duration = float(duration)
        source_start = float(source_start)
        speed = float(speed)
        if duration <= 0:
            raise ValueError("playback duration must be positive")
        if speed <= 0:
            raise ValueError("playback speed must be positive")
        if source_start < 0:
            raise ValueError("source_start must be >= 0")
        if source_duration is not None:
            source_duration = float(source_duration)
            if source_duration <= 0 or source_start >= source_duration:
                raise ValueError("source_start must lie inside source duration")
            if not loop and source_start + duration * speed > source_duration + 1e-9:
                raise ValueError("non-looping playback exceeds source duration")
        elif source_start != 0.0 or speed != 1.0 or loop:
            raise ValueError("static media playback does not use source offsets, speed, or looping")
        span = self._span(duration, at)
        if span.start < 0:
            raise ValueError("media playback cannot start before scene time 0")
        return self._append(
            PlaybackClip(object_id, span, source_start, speed, bool(loop), source_duration)
        )

    def add_interpolation(self, interpolation, duration=None, easing=Easing.SMOOTHSTEP, at=0.0):
        return self._append(
            InterpolationClip(interpolation, self._span(duration, at), easing), key_name=None
        )

    def wait(self, duration: float = 1.0) -> TimeSpan:
        if self._parallel_base is not None:
            raise ValueError("wait() is not allowed inside parallel()")
        span = TimeSpan(self.cursor, duration)
        self.cursor = span.end
        return span

    @contextmanager
    def parallel(self, duration: float | None = None) -> Iterator[None]:
        if self._parallel_base is not None:
            raise ValueError("nested parallel() blocks are not supported")
        resolved_default = None if duration is None else float(duration)
        if resolved_default is not None and resolved_default < 0:
            raise ValueError("parallel duration must be >= 0")
        self._parallel_base = self.cursor
        self._parallel_end = self.cursor
        self._parallel_duration = resolved_default
        try:
            yield
        finally:
            assert self._parallel_end is not None
            self.cursor = max(self.cursor, self._parallel_end)
            self._parallel_base = None
            self._parallel_end = None
            self._parallel_duration = None

    def _schedule_base(self) -> float:
        return self.cursor if self._parallel_base is None else self._parallel_base

    def _advance_after_schedule(self, end: float) -> None:
        if self._parallel_base is None:
            self.cursor = end
        else:
            assert self._parallel_end is not None
            self._parallel_end = max(self._parallel_end, end)

    def _check_channel_conflict(self, candidate, key_name: str, entries) -> None:
        key = getattr(candidate, key_name)
        clip_type = type(candidate)
        for clip in entries:
            if clip.span.overlaps(candidate.span):
                channel = (
                    "transform"
                    if self._channel_token(candidate) == "transform"
                    else clip_type.__name__.removesuffix("Clip").lower()
                )
                raise ValueError(
                    f"overlapping {channel} clips for {key_name} {key}: "
                    f"[{clip.span.start}, {clip.span.end}) and "
                    f"[{candidate.span.start}, {candidate.span.end})"
                )
