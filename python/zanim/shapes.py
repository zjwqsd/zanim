from __future__ import annotations

from math import sqrt

from .batch import BatchObject2D, LineSet
from .geometry import Circle, Color, Line, Object2D, Polygon, StrokeStyle, Style
from .group import Group2D
from .space import Transform2D, Vec2


class Dot(Object2D):
    def __init__(
        self,
        point: Vec2 = Vec2(),
        *,
        radius: float = 0.06,
        color: Color = Color(240, 242, 248),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        super().__init__(
            Circle(radius),
            transform=Transform2D.translation(point.x, point.y),
            style=Style(fill=color, stroke=None),
            opacity=opacity,
            z_index=z_index,
        )


class Arrow(Group2D):
    def __init__(
        self,
        start: Vec2,
        end: Vec2,
        *,
        color: Color = Color(230, 232, 238),
        stroke_width: float = 0.035,
        tip_length: float = 0.18,
        tip_width: float = 0.14,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        dx, dy = end.x - start.x, end.y - start.y
        length = sqrt(dx*dx + dy*dy)
        if length <= 1e-12:
            raise ValueError("Arrow start and end must differ")
        ux, uy = dx/length, dy/length
        nx, ny = -uy, ux
        tip_length = min(tip_length, length * 0.45)
        base = Vec2(end.x - ux*tip_length, end.y - uy*tip_length)
        left = Vec2(base.x + nx*tip_width*0.5, base.y + ny*tip_width*0.5)
        right = Vec2(base.x - nx*tip_width*0.5, base.y - ny*tip_width*0.5)
        shaft = Object2D(
            Line(start, base),
            style=Style(fill=None, stroke=StrokeStyle(color, stroke_width)),
        )
        tip = Object2D(Polygon((end, left, right)), style=Style(fill=color, stroke=None))
        super().__init__([shaft, tip], opacity=opacity, z_index=z_index)
        self.start = start
        self.end = end


class NumberLine(Group2D):
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
        transform: Transform2D = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        x0, x1 = x_range
        if not x0 < x1 or length <= 0 or tick_step <= 0 or tick_size <= 0:
            raise ValueError("invalid NumberLine configuration")
        self.x_range = (float(x0), float(x1))
        self.length = float(length)
        base = Object2D(
            Line(Vec2(-length/2, 0), Vec2(length/2, 0)),
            style=Style(fill=None, stroke=StrokeStyle(color, stroke_width)),
        )
        starts=[]; ends=[]; colors=[]; widths=[]
        import math
        value = math.ceil(x0/tick_step)*tick_step
        while value <= x1 + 1e-12:
            x = (value - (x0+x1)/2) / (x1-x0) * length
            starts.append(Vec2(x, -tick_size/2)); ends.append(Vec2(x, tick_size/2))
            colors.append(color); widths.append(stroke_width)
            value += tick_step
        ticks = BatchObject2D(LineSet(tuple(starts), tuple(ends), tuple(colors), tuple(widths)))
        children = [base, ticks]
        if include_numbers:
            from .typst import Math
            value = math.ceil(x0/tick_step)*tick_step
            while value <= x1 + 1e-12:
                x = (value - (x0+x1)/2) / (x1-x0) * length
                text = str(int(round(value))) if abs(value-round(value)) < 1e-9 else f"{value:g}"
                label = Math(text, font_size=label_font_size, transform=Transform2D.translation(x, -tick_size/2-label_buff))
                # Typst document is centered; shift by half its height so its top
                # sits label_buff below the tick.
                label.shift(0, -label.bounds().height/2)
                children.append(label)
                value += tick_step
        super().__init__(children, transform=transform, opacity=opacity, z_index=z_index)

    def n2p(self, value: float) -> Vec2:
        x0, x1 = self.x_range
        x = (float(value) - (x0+x1)/2) / (x1-x0) * self.length
        return self.transform.apply(Vec2(x, 0))
