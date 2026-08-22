from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .batch import BatchObject2D, LineSet
from .geometry import (
    Color,
    Geometry,
    LineGeometry,
    Object2D,
    PolygonGeometry,
    PolylineGeometry,
    StrokeStyle,
    Style,
)
from .space import Transform2D, Vec2

ScalarFunction = Callable[[float], float]


@dataclass(frozen=True, slots=True)
class Axes:
    """Mathematical 2D axes with an explicit coordinate-to-scene mapping."""

    x_range: tuple[float, float]
    y_range: tuple[float, float]
    width: float = 10.0
    height: float = 6.0
    center: Vec2 = Vec2()

    def __post_init__(self) -> None:
        x0, x1 = self.x_range
        y0, y1 = self.y_range
        if not x0 < x1 or not y0 < y1:
            raise ValueError("axis ranges must be increasing")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("axis dimensions must be positive")

    @property
    def x_scale(self) -> float:
        return self.width / (self.x_range[1] - self.x_range[0])

    @property
    def y_scale(self) -> float:
        return self.height / (self.y_range[1] - self.y_range[0])

    def c2p(self, x: float, y: float) -> Vec2:
        x0, x1 = self.x_range
        y0, y1 = self.y_range
        return Vec2(
            self.center.x + (x - (x0 + x1) * 0.5) * self.x_scale,
            self.center.y + (y - (y0 + y1) * 0.5) * self.y_scale,
        )

    def p2c(self, point: Vec2) -> Vec2:
        x0, x1 = self.x_range
        y0, y1 = self.y_range
        return Vec2(
            (point.x - self.center.x) / self.x_scale + (x0 + x1) * 0.5,
            (point.y - self.center.y) / self.y_scale + (y0 + y1) * 0.5,
        )

    def axes_object(
        self,
        *,
        color: Color = Color(132, 142, 166, 210),
        width: float = 0.018,
    ) -> BatchObject2D:
        x0, x1 = self.x_range
        y0, y1 = self.y_range
        starts: list[Vec2] = []
        ends: list[Vec2] = []
        # Only draw an axis when zero is inside the corresponding range.
        if y0 <= 0 <= y1:
            starts.append(self.c2p(x0, 0))
            ends.append(self.c2p(x1, 0))
        if x0 <= 0 <= x1:
            starts.append(self.c2p(0, y0))
            ends.append(self.c2p(0, y1))
        if not starts:
            raise ValueError("Axes axes_object requires x=0 or y=0 inside the configured ranges")
        return BatchObject2D(
            LineSet(
                tuple(starts),
                tuple(ends),
                tuple(color for _ in starts),
                tuple(width for _ in starts),
            )
        )

    def grid_object(
        self,
        *,
        x_step: float = 1.0,
        y_step: float = 1.0,
        color: Color = Color(85, 95, 116, 65),
        width: float = 0.01,
    ) -> BatchObject2D:
        if x_step <= 0 or y_step <= 0:
            raise ValueError("grid steps must be positive")
        x0, x1 = self.x_range
        y0, y1 = self.y_range
        starts: list[Vec2] = []
        ends: list[Vec2] = []

        x = _first_multiple(x0, x_step)
        while x <= x1 + 1e-12:
            if abs(x) > 1e-12:
                starts.append(self.c2p(x, y0))
                ends.append(self.c2p(x, y1))
            x += x_step
        y = _first_multiple(y0, y_step)
        while y <= y1 + 1e-12:
            if abs(y) > 1e-12:
                starts.append(self.c2p(x0, y))
                ends.append(self.c2p(x1, y))
            y += y_step
        return BatchObject2D(
            LineSet(
                tuple(starts),
                tuple(ends),
                tuple(color for _ in starts),
                tuple(width for _ in starts),
            )
        )

    def plot(
        self,
        function: ScalarFunction,
        *,
        x_range: tuple[float, float] | None = None,
        samples: int = 240,
        color: Color = Color(103, 181, 255),
        stroke_width: float = 0.035,
    ) -> Object2D:
        if samples < 2:
            raise ValueError("plot requires at least two samples")
        a, b = x_range or self.x_range
        if not a < b:
            raise ValueError("plot range must be increasing")
        points = tuple(self.c2p(x, float(function(x))) for x in _linspace(a, b, samples))
        return Object2D(
            PolylineGeometry(points),
            style=Style(fill=None, stroke=StrokeStyle(color, stroke_width)),
        )

    def axis_labels(
        self,
        x_label: str = "x",
        y_label: str = "y",
        *,
        font_size: float = 24.0,
        color: Color = Color(220, 225, 238),
        buff: float = 0.16,
    ):
        """Return Typst math labels positioned at the positive axis ends."""
        from .group import Group
        from .typst import Math

        x0, x1 = self.x_range
        y0, y1 = self.y_range
        labels = []
        if y0 <= 0 <= y1:
            x_obj = Math(x_label, font_size=font_size, color=color)
            target = self.c2p(x1, 0)
            x_obj.move_to(Vec2(target.x + x_obj.bounds().width / 2 + buff, target.y))
            labels.append(x_obj)
        if x0 <= 0 <= x1:
            y_obj = Math(y_label, font_size=font_size, color=color)
            target = self.c2p(0, y1)
            y_obj.move_to(Vec2(target.x, target.y + y_obj.bounds().height / 2 + buff))
            labels.append(y_obj)
        return Group(labels)

    def sample_function(
        self,
        function: ScalarFunction,
        lower: float,
        upper: float,
        *,
        samples: int = 120,
    ) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Sample ``function`` on an inclusive interval.

        Area rendering and numeric integration intentionally share this helper
        so the displayed region and reported value are based on the same
        discretization.
        """
        if samples < 2:
            raise ValueError("function sampling requires at least two samples")
        xs = tuple(_linspace(float(lower), float(upper), samples))
        ys = tuple(float(function(x)) for x in xs)
        return xs, ys

    def area_polygon(
        self,
        function: ScalarFunction,
        lower: float,
        upper: float,
        *,
        baseline: float = 0.0,
        samples: int = 120,
    ) -> PolygonGeometry:
        if lower > upper:
            lower, upper = upper, lower
        xs, ys = self.sample_function(function, lower, upper, samples=samples)
        points = [self.c2p(lower, baseline)]
        points.extend(self.c2p(x, y) for x, y in zip(xs, ys))
        points.append(self.c2p(upper, baseline))
        return PolygonGeometry(tuple(points))

    def integral_value(
        self,
        function: ScalarFunction,
        lower: float,
        upper: float,
        *,
        samples: int = 120,
    ) -> float:
        """Numerically integrate with the trapezoidal rule.

        The same sampled points can therefore drive both ``area_polygon`` and
        the displayed integral value. Reversed limits preserve the standard
        oriented-integral sign.
        """
        if lower == upper:
            return 0.0
        sign = 1.0
        if lower > upper:
            lower, upper = upper, lower
            sign = -1.0
        xs, ys = self.sample_function(function, lower, upper, samples=samples)
        total = 0.0
        for i in range(len(xs) - 1):
            total += 0.5 * (ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i])
        return sign * total

    def boundary_line(
        self,
        function: ScalarFunction,
        x: float,
        *,
        baseline: float = 0.0,
    ) -> LineGeometry:
        return LineGeometry(self.c2p(x, baseline), self.c2p(x, float(function(x))))


class DynamicGeometryObject2D(Object2D):
    """Persistent Object2D whose geometry is a pure function of absolute time."""

    def __init__(
        self,
        provider: Callable[[float], object],
        *,
        style: Style = Style(),
        transform: Transform2D = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        if not callable(provider):
            raise TypeError("dynamic geometry provider must be callable")
        self.provider = provider
        initial = provider(0.0)
        if not isinstance(initial, Geometry):
            raise TypeError("dynamic geometry provider must return a Zanim Geometry")
        super().__init__(
            initial, transform=transform, style=style, opacity=opacity, z_index=z_index
        )

    def geometry_at(self, time: float):
        geometry = self.provider(float(time))
        if not isinstance(geometry, Geometry):
            raise TypeError("dynamic geometry provider returned unsupported geometry")
        return geometry

    def _geometry_at(self, time: float, initial):
        _ = initial
        return self.geometry_at(time)


def _first_multiple(low: float, step: float) -> float:
    from math import ceil

    return ceil(low / step) * step


def _linspace(a: float, b: float, count: int):
    if count == 1:
        yield a
        return
    scale = (b - a) / (count - 1)
    for i in range(count):
        yield a + i * scale
