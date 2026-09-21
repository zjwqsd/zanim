from __future__ import annotations

from math import pi, sqrt
from typing import Iterable

from .batch import BatchObject2D, LineSet
from .geometry import (
    ArcGeometry,
    CircleGeometry,
    Color,
    CubicBezierGeometry,
    DEFAULT_STROKE_WIDTH,
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


class SurroundingRectangle(Rectangle):
    def __init__(
        self,
        target,
        *,
        buff: float = 0.1,
        color: Color = Color(255, 214, 105),
        **kwargs,
    ) -> None:
        if buff < 0:
            raise ValueError("SurroundingRectangle buff must be >= 0")
        bounds = target.bounds()
        super().__init__(
            bounds.width + 2 * buff,
            bounds.height + 2 * buff,
            position=bounds.center,
            fill=None,
            stroke=color,
            **kwargs,
        )


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



class Brace(Polyline):
    def __init__(
        self,
        target,
        *,
        direction: Point2 = (0.0, -1.0),
        buff: float = 0.2,
        depth: float = 0.12,
        color: Color = Color(255, 255, 255),
        stroke_width: float = 0.025,
        samples: int = 8,
        **kwargs,
    ) -> None:
        d = as_vec2(direction, name="direction").normalized()
        t = Vec2(-d.y, d.x)
        b = target.bounds()
        geometry = getattr(target, "geometry", None)
        if isinstance(geometry, LineGeometry):
            support_points = (
                target.transform.apply(geometry.start),
                target.transform.apply(geometry.end),
            )
        elif isinstance(geometry, PolylineGeometry):
            support_points = tuple(target.transform.apply(p) for p in geometry.points)
        else:
            support_points = (
                Vec2(b.left, b.bottom),
                Vec2(b.left, b.top),
                Vec2(b.right, b.bottom),
                Vec2(b.right, b.top),
            )
        proj_t = tuple(p.x * t.x + p.y * t.y for p in support_points)
        proj_n = tuple(p.x * d.x + p.y * d.y for p in support_points)
        u0, u1 = min(proj_t), max(proj_t)
        span = max(1e-6, u1 - u0)
        center_u = (u0 + u1) * 0.5
        base_v = max(proj_n) + float(buff)

        half = span * 0.5
        hook_w = min(0.22, max(0.09, span * 0.065))
        notch_w = min(0.20, max(0.10, span * 0.055))
        end_y = -float(depth) * 0.52
        segments = (
            ((-half, end_y), (-half, -depth * 0.18), (-half + hook_w * 0.25, 0.0), (-half + hook_w, 0.0)),
            ((-half + hook_w, 0.0), (-half + span * 0.22, 0.0), (-notch_w * 1.8, 0.0), (-notch_w, 0.0)),
            ((-notch_w, 0.0), (-notch_w * 0.58, 0.0), (-notch_w * 0.34, depth * 0.72), (0.0, depth)),
            ((0.0, depth), (notch_w * 0.34, depth * 0.72), (notch_w * 0.58, 0.0), (notch_w, 0.0)),
            ((notch_w, 0.0), (notch_w * 1.8, 0.0), (half - span * 0.22, 0.0), (half - hook_w, 0.0)),
            ((half - hook_w, 0.0), (half - hook_w * 0.25, 0.0), (half, -depth * 0.18), (half, end_y)),
        )

        def cubic(p0, p1, p2, p3, alpha):
            u = 1.0 - alpha
            return (
                u**3 * p0[0] + 3*u*u*alpha*p1[0] + 3*u*alpha*alpha*p2[0] + alpha**3*p3[0],
                u**3 * p0[1] + 3*u*u*alpha*p1[1] + 3*u*alpha*alpha*p2[1] + alpha**3*p3[1],
            )

        local_points = []
        count = max(2, int(samples))
        for segment_index, seg in enumerate(segments):
            start = 0 if segment_index == 0 else 1
            for i in range(start, count + 1):
                local_points.append(cubic(*seg, i / count))

        def world(p):
            x, y = p
            u, v = center_u + x, base_v + y
            return Vec2(t.x*u + d.x*v, t.y*u + d.y*v)

        self.direction = d
        self.tangent = t
        self.depth = float(depth)
        self._brace_center_u = center_u
        self._brace_base_v = base_v
        super().__init__(
            tuple(world(p) for p in local_points),
            stroke=color,
            stroke_width=stroke_width,
            **kwargs,
        )

    def label_point(self, buff: float = 0.25) -> Vec2:
        u = self._brace_center_u
        v = self._brace_base_v + self.depth + float(buff)
        return Vec2(
            self.tangent.x*u + self.direction.x*v,
            self.tangent.y*u + self.direction.y*v,
        )


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
        radius: float = 0.08,
        color: Color = Color(255, 255, 255),
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
        start: Point2 = (0.0, 0.0),
        end: Point2 = (1.0, 0.0),
        *,
        color: Color = Color(255, 255, 255),
        stroke_width: float = DEFAULT_STROKE_WIDTH,
        tip_length: float = 0.35,
        tip_width: float = 0.35,
        buff: float = 0.25,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        start = as_vec2(start, name="start")
        end = as_vec2(end, name="end")
        dx, dy = end.x - start.x, end.y - start.y
        length = sqrt(dx * dx + dy * dy)
        if length <= 1e-12:
            raise ValueError("Arrow start and end must differ")
        if buff < 0:
            raise ValueError("Arrow buff must be >= 0")
        if 2 * buff >= length:
            raise ValueError("Arrow buff is too large for its length")

        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        rendered_start = Vec2(start.x + ux * buff, start.y + uy * buff)
        rendered_end = Vec2(end.x - ux * buff, end.y - uy * buff)
        rendered_length = length - 2 * buff

        actual_tip_length = min(float(tip_length), rendered_length * 0.25)
        actual_tip_width = min(float(tip_width), actual_tip_length)
        base = Vec2(
            rendered_end.x - ux * actual_tip_length,
            rendered_end.y - uy * actual_tip_length,
        )
        left = Vec2(base.x + nx * actual_tip_width * 0.5, base.y + ny * actual_tip_width * 0.5)
        right = Vec2(base.x - nx * actual_tip_width * 0.5, base.y - ny * actual_tip_width * 0.5)

        shaft = Line(rendered_start, base, stroke=color, stroke_width=stroke_width)
        tip = Polygon((rendered_end, left, right), fill=color, stroke=None)
        super().__init__([shaft, tip], opacity=opacity, z_index=z_index)
        self.start = start
        self.end = end
        self.buff = float(buff)


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
