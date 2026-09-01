from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Callable, Iterable, Literal

from .batch import BatchObject2D, CircleSet, DynamicBatchObject2D, LineSet
from .constants import BLUE, MUTED
from .geometry import Color
from .group import Group
from .shapes import Polyline
from .space import SE2, Point2, Transform2D, Vec2, as_vec2

VectorFunction = Callable[[Vec2], Point2]
DynamicVectorFunction = Callable[[Vec2, float], Point2]
ColorFunction = Callable[[Vec2, Vec2, float], Color]
StopPredicate = Callable[[Vec2], bool]
DynamicStopPredicate = Callable[[Vec2, float], bool]


@dataclass(frozen=True, slots=True)
class VectorSample:
    point: Vec2
    vector: Vec2
    magnitude: float


def _axis_samples(limits: tuple[float, float], step: float) -> tuple[float, ...]:
    lo, hi = map(float, limits)
    if not lo < hi:
        raise ValueError("vector field ranges must be increasing")
    if step <= 0:
        raise ValueError("vector field step must be positive")
    first = ceil(lo / step) * step
    values: list[float] = []
    value = first
    while value <= hi + 1e-12:
        values.append(value)
        value += step
    return tuple(values)


def _resolve_step(step: float | Point2) -> Vec2:
    if isinstance(step, (int, float)):
        value = float(step)
        return Vec2(value, value)
    return as_vec2(step, name="step")


def _color(value: Color | ColorFunction, sample: VectorSample) -> Color:
    result = value(sample.point, sample.vector, sample.magnitude) if callable(value) else value
    if not isinstance(result, Color):
        raise TypeError("vector field color function must return Color")
    return result


class VectorField(Group):
    """A sampled 2D vector field rendered with batched points and arrows.

    ``field`` is evaluated in field coordinates. The object itself is a normal
    Group, so Scene hierarchy, transforms, opacity and Scene IR reuse existing
    primitives rather than introducing a renderer-specific field type.

    ``streamlines()`` integrates the same function and returns a separate Group
    of polylines. This keeps sampled arrows and integral curves as two explicit
    views of one mathematical field.
    """

    def __init__(
        self,
        field: VectorFunction,
        *,
        x_range: tuple[float, float] = (-5.0, 5.0),
        y_range: tuple[float, float] = (-3.0, 3.0),
        step: float | Point2 = 0.8,
        show_points: bool = True,
        point_radius: float = 0.025,
        point_color: Color = MUTED,
        color: Color | ColorFunction = BLUE,
        stroke_width: float = 0.018,
        vector_length: float = 0.42,
        normalize: bool = True,
        vector_scale: float = 0.25,
        max_vector_length: float | None = None,
        min_magnitude: float = 1e-9,
        tip_length: float = 0.11,
        tip_width: float = 0.10,
        transform: Transform2D | SE2 = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        if not callable(field):
            raise TypeError("VectorField field must be callable")
        resolved_step = _resolve_step(step)
        if resolved_step.x <= 0 or resolved_step.y <= 0:
            raise ValueError("VectorField step components must be positive")
        if point_radius <= 0 or stroke_width <= 0 or vector_length <= 0:
            raise ValueError("VectorField visual sizes must be positive")
        if vector_scale <= 0 or min_magnitude < 0 or tip_length <= 0 or tip_width <= 0:
            raise ValueError("invalid VectorField scaling configuration")
        if max_vector_length is not None and max_vector_length <= 0:
            raise ValueError("max_vector_length must be positive")

        self.field = field
        self.x_range = tuple(map(float, x_range))
        self.y_range = tuple(map(float, y_range))
        self.step = resolved_step
        self.min_magnitude = float(min_magnitude)
        self.samples = self._sample_field()

        children = []
        if show_points and self.samples:
            points = BatchObject2D(
                CircleSet(
                    tuple(sample.point for sample in self.samples),
                    tuple(float(point_radius) for _ in self.samples),
                    tuple(point_color for _ in self.samples),
                )
            )
            children.append(points)
            self.points = points
        else:
            self.points = None

        starts: list[Vec2] = []
        ends: list[Vec2] = []
        colors: list[Color] = []
        widths: list[float] = []
        for sample in self.samples:
            if sample.magnitude <= self.min_magnitude:
                continue
            direction = sample.vector / sample.magnitude
            if normalize:
                length = float(vector_length)
            else:
                length = sample.magnitude * float(vector_scale)
                limit = float(max_vector_length or vector_length)
                length = min(length, limit)
            if length <= 1e-12:
                continue

            end = sample.point + direction * length
            head_length = min(float(tip_length), length * 0.45)
            base = end - direction * head_length
            normal = Vec2(-direction.y, direction.x)
            left = base + normal * (float(tip_width) * 0.5)
            right = base - normal * (float(tip_width) * 0.5)
            resolved_color = _color(color, sample)
            for a, b in ((sample.point, end), (end, left), (end, right)):
                starts.append(a)
                ends.append(b)
                colors.append(resolved_color)
                widths.append(float(stroke_width))

        if starts:
            arrows = BatchObject2D(
                LineSet(tuple(starts), tuple(ends), tuple(colors), tuple(widths))
            )
            children.append(arrows)
            self.arrows = arrows
        else:
            self.arrows = None

        super().__init__(children, transform=transform, opacity=opacity, z_index=z_index)

    def _sample_field(self) -> tuple[VectorSample, ...]:
        xs = _axis_samples(self.x_range, self.step.x)
        ys = _axis_samples(self.y_range, self.step.y)
        samples: list[VectorSample] = []
        for y in ys:
            for x in xs:
                point = Vec2(x, y)
                vector = as_vec2(self.field(point), name="vector field value")
                samples.append(VectorSample(point, vector, vector.length))
        return tuple(samples)

    def value_at(self, point: Point2) -> Vec2:
        p = as_vec2(point, name="point")
        return as_vec2(self.field(p), name="vector field value")

    def _inside(self, point: Vec2) -> bool:
        return (
            self.x_range[0] <= point.x <= self.x_range[1]
            and self.y_range[0] <= point.y <= self.y_range[1]
        )

    def _flow_direction(self, point: Vec2, *, normalize: bool, direction: float) -> Vec2 | None:
        value = self.value_at(point)
        magnitude = value.length
        if magnitude <= self.min_magnitude:
            return None
        return value * (direction / magnitude) if normalize else value * direction

    def _rk4_step(
        self,
        point: Vec2,
        step: float,
        *,
        normalize: bool,
        direction: float,
    ) -> Vec2 | None:
        def flow(p: Vec2) -> Vec2 | None:
            return self._flow_direction(p, normalize=normalize, direction=direction)

        k1 = flow(point)
        if k1 is None:
            return None
        k2 = flow(point + k1 * (step * 0.5))
        if k2 is None:
            return None
        k3 = flow(point + k2 * (step * 0.5))
        if k3 is None:
            return None
        k4 = flow(point + k3 * step)
        if k4 is None:
            return None
        return point + (k1 + k2 * 2.0 + k3 * 2.0 + k4) * (step / 6.0)

    def trace_streamline(
        self,
        seed: Point2,
        *,
        direction: Literal["forward", "backward", "both"] = "both",
        step: float = 0.055,
        max_steps: int = 800,
        normalize: bool = True,
        stop: StopPredicate | None = None,
    ) -> tuple[Vec2, ...]:
        """Integrate one field line with fixed-step RK4.

        Normalized integration traces geometric field lines independent of
        magnitude, which is usually the desired representation for electric and
        flow fields. ``stop`` is evaluated after each accepted point.
        """
        if step <= 0 or max_steps < 1:
            raise ValueError("streamline step and max_steps must be positive")
        if direction not in {"forward", "backward", "both"}:
            raise ValueError("direction must be 'forward', 'backward', or 'both'")
        seed_point = as_vec2(seed, name="seed")
        if not self._inside(seed_point):
            raise ValueError("streamline seed must lie inside VectorField ranges")

        def trace(sign: float) -> list[Vec2]:
            points = [seed_point]
            current = seed_point
            for _ in range(int(max_steps)):
                next_point = self._rk4_step(
                    current, float(step), normalize=normalize, direction=sign
                )
                if next_point is None or not self._inside(next_point):
                    break
                points.append(next_point)
                current = next_point
                if stop is not None and stop(current):
                    break
            return points

        if direction == "forward":
            return tuple(trace(1.0))
        if direction == "backward":
            return tuple(trace(-1.0))
        backward = trace(-1.0)
        forward = trace(1.0)
        return tuple((*reversed(backward[1:]), *forward))

    def streamlines(
        self,
        seeds: Iterable[Point2],
        *,
        direction: Literal["forward", "backward", "both"] = "both",
        step: float = 0.055,
        max_steps: int = 800,
        normalize: bool = True,
        stop: StopPredicate | None = None,
        color: Color = BLUE,
        stroke_width: float = 0.026,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> Group:
        """Return integral curves of the field as ordinary Zanim polylines."""
        if stroke_width <= 0:
            raise ValueError("streamline stroke_width must be positive")
        lines = []
        for seed in seeds:
            points = self.trace_streamline(
                seed,
                direction=direction,
                step=step,
                max_steps=max_steps,
                normalize=normalize,
                stop=stop,
            )
            if len(points) >= 2:
                lines.append(
                    Polyline(
                        points,
                        stroke=color,
                        stroke_width=stroke_width,
                    )
                )
        return Group(lines, opacity=opacity, z_index=z_index)


class DynamicVectorField(Group):
    """A time-dependent sampled 2D vector field ``field(point, time)``.

    The sampling lattice is fixed while the batched arrows are regenerated from
    absolute scene time.  ``streamlines()`` freezes the vector field at each
    requested scene time and integrates its instantaneous field lines with RK4.
    Both views therefore remain deterministic under arbitrary seeking.
    """

    def __init__(
        self,
        field: DynamicVectorFunction,
        *,
        x_range: tuple[float, float] = (-5.0, 5.0),
        y_range: tuple[float, float] = (-3.0, 3.0),
        step: float | Point2 = 0.8,
        show_points: bool = True,
        point_radius: float = 0.025,
        point_color: Color = MUTED,
        color: Color | ColorFunction = BLUE,
        stroke_width: float = 0.018,
        vector_length: float = 0.42,
        normalize: bool = True,
        vector_scale: float = 0.25,
        max_vector_length: float | None = None,
        min_magnitude: float = 1e-9,
        tip_length: float = 0.11,
        tip_width: float = 0.10,
        transform: Transform2D | SE2 = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        if not callable(field):
            raise TypeError("DynamicVectorField field must be callable")
        resolved_step = _resolve_step(step)
        if resolved_step.x <= 0 or resolved_step.y <= 0:
            raise ValueError("DynamicVectorField step components must be positive")
        if point_radius <= 0 or stroke_width <= 0 or vector_length <= 0:
            raise ValueError("DynamicVectorField visual sizes must be positive")
        if vector_scale <= 0 or min_magnitude < 0 or tip_length <= 0 or tip_width <= 0:
            raise ValueError("invalid DynamicVectorField scaling configuration")
        if max_vector_length is not None and max_vector_length <= 0:
            raise ValueError("max_vector_length must be positive")

        self.field = field
        self.x_range = tuple(map(float, x_range))
        self.y_range = tuple(map(float, y_range))
        self.step = resolved_step
        self.min_magnitude = float(min_magnitude)
        self.sample_points = tuple(
            Vec2(x, y)
            for y in _axis_samples(self.y_range, self.step.y)
            for x in _axis_samples(self.x_range, self.step.x)
        )

        children = []
        if show_points and self.sample_points:
            points = BatchObject2D(
                CircleSet(
                    self.sample_points,
                    tuple(float(point_radius) for _ in self.sample_points),
                    tuple(point_color for _ in self.sample_points),
                )
            )
            children.append(points)
            self.points = points
        else:
            self.points = None

        def arrows_at(time: float) -> LineSet:
            samples = self.samples_at(time)
            starts: list[Vec2] = []
            ends: list[Vec2] = []
            colors: list[Color] = []
            widths: list[float] = []
            for sample in samples:
                if sample.magnitude <= self.min_magnitude:
                    continue
                direction = sample.vector / sample.magnitude
                if normalize:
                    length = float(vector_length)
                else:
                    length = sample.magnitude * float(vector_scale)
                    limit = float(max_vector_length or vector_length)
                    length = min(length, limit)
                if length <= 1e-12:
                    continue
                end = sample.point + direction * length
                head_length = min(float(tip_length), length * 0.45)
                base = end - direction * head_length
                normal = Vec2(-direction.y, direction.x)
                left = base + normal * (float(tip_width) * 0.5)
                right = base - normal * (float(tip_width) * 0.5)
                resolved_color = _color(color, sample)
                for a, b in ((sample.point, end), (end, left), (end, right)):
                    starts.append(a)
                    ends.append(b)
                    colors.append(resolved_color)
                    widths.append(float(stroke_width))
            if not starts:
                # DynamicBatchObject2D requires a non-empty batch. A fully zero
                # field is represented by one transparent degenerate segment.
                starts.append(Vec2())
                ends.append(Vec2())
                colors.append(Color(0, 0, 0, 0))
                widths.append(float(stroke_width))
            return LineSet(tuple(starts), tuple(ends), tuple(colors), tuple(widths))

        arrows = DynamicBatchObject2D(arrows_at)
        children.append(arrows)
        self.arrows = arrows
        super().__init__(children, transform=transform, opacity=opacity, z_index=z_index)

    def samples_at(self, time: float) -> tuple[VectorSample, ...]:
        t = float(time)
        samples = []
        for point in self.sample_points:
            vector = as_vec2(self.field(point, t), name="dynamic vector field value")
            samples.append(VectorSample(point, vector, vector.length))
        return tuple(samples)

    def value_at(self, point: Point2, time: float) -> Vec2:
        p = as_vec2(point, name="point")
        return as_vec2(self.field(p, float(time)), name="dynamic vector field value")

    def _inside(self, point: Vec2) -> bool:
        return (
            self.x_range[0] <= point.x <= self.x_range[1]
            and self.y_range[0] <= point.y <= self.y_range[1]
        )

    def _flow_direction(
        self, point: Vec2, time: float, *, normalize: bool, direction: float
    ) -> Vec2 | None:
        value = self.value_at(point, time)
        magnitude = value.length
        if magnitude <= self.min_magnitude:
            return None
        return value * (direction / magnitude) if normalize else value * direction

    def _rk4_step(
        self,
        point: Vec2,
        time: float,
        step: float,
        *,
        normalize: bool,
        direction: float,
    ) -> Vec2 | None:
        def flow(p: Vec2) -> Vec2 | None:
            return self._flow_direction(p, time, normalize=normalize, direction=direction)

        k1 = flow(point)
        if k1 is None:
            return None
        k2 = flow(point + k1 * (step * 0.5))
        if k2 is None:
            return None
        k3 = flow(point + k2 * (step * 0.5))
        if k3 is None:
            return None
        k4 = flow(point + k3 * step)
        if k4 is None:
            return None
        return point + (k1 + k2 * 2.0 + k3 * 2.0 + k4) * (step / 6.0)

    def trace_streamline(
        self,
        seed: Point2,
        time: float,
        *,
        direction: Literal["forward", "backward", "both"] = "both",
        step: float = 0.055,
        max_steps: int = 800,
        normalize: bool = True,
        stop: DynamicStopPredicate | None = None,
    ) -> tuple[Vec2, ...]:
        if step <= 0 or max_steps < 1:
            raise ValueError("streamline step and max_steps must be positive")
        if direction not in {"forward", "backward", "both"}:
            raise ValueError("direction must be 'forward', 'backward', or 'both'")
        seed_point = as_vec2(seed, name="seed")
        if not self._inside(seed_point):
            raise ValueError("streamline seed must lie inside DynamicVectorField ranges")
        t = float(time)

        def trace(sign: float) -> list[Vec2]:
            points = [seed_point]
            current = seed_point
            for _ in range(int(max_steps)):
                next_point = self._rk4_step(
                    current, t, float(step), normalize=normalize, direction=sign
                )
                if next_point is None or not self._inside(next_point):
                    break
                points.append(next_point)
                current = next_point
                if stop is not None and stop(current, t):
                    break
            return points

        if direction == "forward":
            return tuple(trace(1.0))
        if direction == "backward":
            return tuple(trace(-1.0))
        backward = trace(-1.0)
        forward = trace(1.0)
        return tuple((*reversed(backward[1:]), *forward))

    def streamlines(
        self,
        seeds: Callable[[float], Iterable[Point2]] | Iterable[Point2],
        *,
        direction: Literal["forward", "backward", "both"] = "both",
        step: float = 0.055,
        max_steps: int = 800,
        normalize: bool = True,
        stop: DynamicStopPredicate | None = None,
        color: Color = BLUE,
        stroke_width: float = 0.026,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> DynamicBatchObject2D:
        """Return instantaneous field lines as one dynamic batched line object."""
        if stroke_width <= 0:
            raise ValueError("streamline stroke_width must be positive")

        def batch_at(time: float) -> LineSet:
            seed_values = seeds(float(time)) if callable(seeds) else seeds
            starts: list[Vec2] = []
            ends: list[Vec2] = []
            for seed in seed_values:
                points = self.trace_streamline(
                    seed,
                    time,
                    direction=direction,
                    step=step,
                    max_steps=max_steps,
                    normalize=normalize,
                    stop=stop,
                )
                for a, b in zip(points, points[1:]):
                    starts.append(a)
                    ends.append(b)
            if not starts:
                starts.append(Vec2())
                ends.append(Vec2())
                line_color = Color(0, 0, 0, 0)
            else:
                line_color = color
            return LineSet(
                tuple(starts),
                tuple(ends),
                tuple(line_color for _ in starts),
                tuple(float(stroke_width) for _ in starts),
            )

        return DynamicBatchObject2D(batch_at, opacity=opacity, z_index=z_index)
