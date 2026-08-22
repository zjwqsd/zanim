from __future__ import annotations

from math import pi, sqrt
from typing import Iterable

from .batch import BatchObject2D, LineSet
from .geometry import (
    ArcGeometry,
    CircleGeometry,
    Color,
    CubicBezierGeometry,
    EllipseGeometry,
    LineGeometry,
    Object2D,
    PolygonGeometry,
    PolylineGeometry,
    RectangleGeometry,
    RegularPolygonGeometry,
    SquareGeometry,
)
from .group import Group
from .space import SE2, Point2, Transform2D, Vec2, as_vec2


def _points(values: Iterable[Point2], *, name: str) -> tuple[Vec2, ...]:
    return tuple(as_vec2(value, name=name) for value in values)


class Shape(Object2D):
    """Base class for ordinary renderable 2D geometry objects."""


class Circle(Shape):
    def __init__(self, radius: float = 1.0, **kwargs) -> None:
        super().__init__(CircleGeometry(radius), **kwargs)


class Square(Shape):
    def __init__(self, side: float = 1.0, **kwargs) -> None:
        super().__init__(SquareGeometry(side), **kwargs)


class Rectangle(Shape):
    def __init__(self, width: float = 2.0, height: float = 1.0, **kwargs) -> None:
        super().__init__(RectangleGeometry(width, height), **kwargs)


class Ellipse(Shape):
    def __init__(self, radius_x: float = 1.0, radius_y: float = 0.6, **kwargs) -> None:
        super().__init__(EllipseGeometry(radius_x, radius_y), **kwargs)


class Arc(Shape):
    def __init__(
        self,
        radius: float = 1.0,
        start_angle: float = 0.0,
        sweep_angle: float = pi / 2,
        **kwargs,
    ) -> None:
        super().__init__(ArcGeometry(radius, start_angle, sweep_angle), **kwargs)


class RegularPolygon(Shape):
    def __init__(
        self,
        sides: int = 6,
        radius: float = 1.0,
        phase: float = pi / 2,
        **kwargs,
    ) -> None:
        super().__init__(RegularPolygonGeometry(sides, radius, phase), **kwargs)


class Line(Shape):
    def __init__(self, start: Point2 = (-1.0, 0.0), end: Point2 = (1.0, 0.0), **kwargs) -> None:
        super().__init__(
            LineGeometry(as_vec2(start, name="start"), as_vec2(end, name="end")), **kwargs
        )


class Polyline(Shape):
    def __init__(self, points: Iterable[Point2], **kwargs) -> None:
        super().__init__(PolylineGeometry(_points(points, name="point")), **kwargs)


class Polygon(Shape):
    def __init__(self, points: Iterable[Point2], **kwargs) -> None:
        super().__init__(PolygonGeometry(_points(points, name="point")), **kwargs)


class CubicBezier(Shape):
    def __init__(self, p0: Point2, p1: Point2, p2: Point2, p3: Point2, **kwargs) -> None:
        super().__init__(
            CubicBezierGeometry(
                as_vec2(p0, name="p0"),
                as_vec2(p1, name="p1"),
                as_vec2(p2, name="p2"),
                as_vec2(p3, name="p3"),
            ),
            **kwargs,
        )


class Dot(Circle):
    def __init__(
        self,
        point: Point2 = (0.0, 0.0),
        *,
        radius: float = 0.06,
        color: Color = Color(240, 242, 248),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        p = as_vec2(point, name="point")
        super().__init__(
            radius,
            position=p,
            fill=color,
            opacity=opacity,
            z_index=z_index,
        )


class Arrow(Group):
    def __init__(
        self,
        start: Point2,
        end: Point2,
        *,
        color: Color = Color(230, 232, 238),
        stroke_width: float = 0.035,
        tip_length: float = 0.18,
        tip_width: float = 0.14,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        start = as_vec2(start, name="start")
        end = as_vec2(end, name="end")
        dx, dy = end.x - start.x, end.y - start.y
        length = sqrt(dx * dx + dy * dy)
        if length <= 1e-12:
            raise ValueError("Arrow start and end must differ")
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        tip_length = min(tip_length, length * 0.45)
        base = Vec2(end.x - ux * tip_length, end.y - uy * tip_length)
        left = Vec2(base.x + nx * tip_width * 0.5, base.y + ny * tip_width * 0.5)
        right = Vec2(base.x - nx * tip_width * 0.5, base.y - ny * tip_width * 0.5)
        shaft = Line(start, base, stroke=color, stroke_width=stroke_width)
        tip = Polygon((end, left, right), fill=color)
        super().__init__([shaft, tip], opacity=opacity, z_index=z_index)
        self.start = start
        self.end = end


class NumberLine(Group):
    def __init__(
        self,
        x_range: tuple[float, float] = (-5.0, 5.0),
        *,
        length: float = 10.0,
        tick_step: float = 1.0,
        tick_size: float = 0.12,
        color: Color = Color(180, 188, 208),
        stroke_width: float = 0.025,
        include_numbers: bool = False,
        label_font_size: float = 18.0,
        label_buff: float = 0.14,
        transform: Transform2D | SE2 = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        x0, x1 = x_range
        if not x0 < x1 or length <= 0 or tick_step <= 0 or tick_size <= 0:
            raise ValueError("invalid NumberLine configuration")
        self.x_range = (float(x0), float(x1))
        self.length = float(length)
        base = Line((-length / 2, 0), (length / 2, 0), stroke=color, stroke_width=stroke_width)
        starts: list[Vec2] = []
        ends: list[Vec2] = []
        colors: list[Color] = []
        widths: list[float] = []
        import math

        value = math.ceil(x0 / tick_step) * tick_step
        while value <= x1 + 1e-12:
            x = (value - (x0 + x1) / 2) / (x1 - x0) * length
            starts.append(Vec2(x, -tick_size / 2))
            ends.append(Vec2(x, tick_size / 2))
            colors.append(color)
            widths.append(stroke_width)
            value += tick_step
        ticks = BatchObject2D(LineSet(tuple(starts), tuple(ends), tuple(colors), tuple(widths)))
        children = [base, ticks]
        if include_numbers:
            from .typst import Math

            value = math.ceil(x0 / tick_step) * tick_step
            while value <= x1 + 1e-12:
                x = (value - (x0 + x1) / 2) / (x1 - x0) * length
                text = str(int(round(value))) if abs(value - round(value)) < 1e-9 else f"{value:g}"
                label = Math(
                    text,
                    font_size=label_font_size,
                    transform=Transform2D.translation(x, -tick_size / 2 - label_buff),
                )
                label.shift(0, -label.bounds().height / 2)
                children.append(label)
                value += tick_step
        super().__init__(children, transform=transform, opacity=opacity, z_index=z_index)

    def n2p(self, value: float) -> Vec2:
        x0, x1 = self.x_range
        x = (float(value) - (x0 + x1) / 2) / (x1 - x0) * self.length
        return self.transform.apply(Vec2(x, 0))
