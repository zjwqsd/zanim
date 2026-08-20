from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin, sqrt

from .space import Transform2D, Vec2


@dataclass(frozen=True, slots=True)
class Bounds2D:
    left: float
    bottom: float
    right: float
    top: float

    def __post_init__(self) -> None:
        if self.left > self.right or self.bottom > self.top:
            raise ValueError("invalid bounds")

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def center(self) -> Vec2:
        return Vec2((self.left + self.right) * 0.5, (self.bottom + self.top) * 0.5)

    def point(self, direction: Vec2) -> Vec2:
        cx, cy = self.center.x, self.center.y
        x = self.right if direction.x > 1e-12 else self.left if direction.x < -1e-12 else cx
        y = self.top if direction.y > 1e-12 else self.bottom if direction.y < -1e-12 else cy
        return Vec2(x, y)

    def expanded(self, amount: float) -> "Bounds2D":
        if amount < 0 and (-2 * amount > self.width or -2 * amount > self.height):
            raise ValueError("bounds contraction is too large")
        return Bounds2D(self.left - amount, self.bottom - amount, self.right + amount, self.top + amount)

    @staticmethod
    def union(*bounds: "Bounds2D") -> "Bounds2D":
        if not bounds:
            raise ValueError("Bounds2D.union requires at least one bounds")
        return Bounds2D(
            min(b.left for b in bounds), min(b.bottom for b in bounds),
            max(b.right for b in bounds), max(b.top for b in bounds),
        )


def _points_bounds(points) -> Bounds2D:
    pts = tuple(points)
    if not pts:
        raise ValueError("cannot bound an empty point set")
    return Bounds2D(
        min(p.x for p in pts), min(p.y for p in pts),
        max(p.x for p in pts), max(p.y for p in pts),
    )


def _cubic_bounds(cubic, transform: Transform2D) -> Bounds2D:
    from .geometry import CubicBezier
    from .vector import VectorContour, VectorPath, vector_path_bounds
    seg = CubicBezier(
        transform.apply(cubic.p0), transform.apply(cubic.p1),
        transform.apply(cubic.p2), transform.apply(cubic.p3),
    )
    left, bottom, right, top = vector_path_bounds(VectorPath((VectorContour((seg,), False),)))
    return Bounds2D(left, bottom, right, top)


def _geometry_bounds(geometry, transform: Transform2D) -> Bounds2D:
    from .geometry import (
        Arc, Circle, CubicBezier, Ellipse, Line, Polygon, Polyline,
        Rectangle, RegularPolygon, Square,
    )
    if isinstance(geometry, Line):
        return _points_bounds((transform.apply(geometry.start), transform.apply(geometry.end)))
    if isinstance(geometry, (Polyline, Polygon)):
        return _points_bounds(transform.apply(p) for p in geometry.points)
    if isinstance(geometry, Rectangle):
        hx, hy = geometry.width * 0.5, geometry.height * 0.5
        return _points_bounds(transform.apply(Vec2(x, y)) for x in (-hx, hx) for y in (-hy, hy))
    if isinstance(geometry, Square):
        h = geometry.side * 0.5
        return _points_bounds(transform.apply(Vec2(x, y)) for x in (-h, h) for y in (-h, h))
    if isinstance(geometry, Circle):
        cx, cy = transform.tx, transform.ty
        ex = geometry.radius * sqrt(transform.xx**2 + transform.xy**2)
        ey = geometry.radius * sqrt(transform.yx**2 + transform.yy**2)
        return Bounds2D(cx - ex, cy - ey, cx + ex, cy + ey)
    if isinstance(geometry, Ellipse):
        cx, cy = transform.tx, transform.ty
        ex = sqrt((transform.xx * geometry.radius_x)**2 + (transform.xy * geometry.radius_y)**2)
        ey = sqrt((transform.yx * geometry.radius_x)**2 + (transform.yy * geometry.radius_y)**2)
        return Bounds2D(cx - ex, cy - ey, cx + ex, cy + ey)
    if isinstance(geometry, Arc):
        count = max(16, int(abs(geometry.sweep_angle) / (2*pi) * 96) + 2)
        points = (
            transform.apply(Vec2(
                geometry.radius * cos(geometry.start_angle + geometry.sweep_angle * i / (count - 1)),
                geometry.radius * sin(geometry.start_angle + geometry.sweep_angle * i / (count - 1)),
            ))
            for i in range(count)
        )
        return _points_bounds(points)
    if isinstance(geometry, RegularPolygon):
        return _points_bounds(
            transform.apply(Vec2(
                geometry.radius * cos(geometry.phase + 2*pi*i/geometry.sides),
                geometry.radius * sin(geometry.phase + 2*pi*i/geometry.sides),
            )) for i in range(geometry.sides)
        )
    if isinstance(geometry, CubicBezier):
        return _cubic_bounds(geometry, transform)
    raise TypeError(f"unsupported geometry for bounds: {type(geometry).__name__}")


def _batch_bounds(batch, transform: Transform2D) -> Bounds2D:
    from .batch import CircleSet, LineSet, RectSet
    if isinstance(batch, LineSet):
        return _points_bounds(transform.apply(p) for pair in zip(batch.starts, batch.ends) for p in pair)
    if isinstance(batch, CircleSet):
        pieces = []
        for center, radius in zip(batch.centers, batch.radii):
            c = transform.apply(center)
            ex = radius * sqrt(transform.xx**2 + transform.xy**2)
            ey = radius * sqrt(transform.yx**2 + transform.yy**2)
            pieces.append(Bounds2D(c.x-ex, c.y-ey, c.x+ex, c.y+ey))
        return Bounds2D.union(*pieces)
    if isinstance(batch, RectSet):
        pieces = []
        for center, size in zip(batch.centers, batch.sizes):
            hx, hy = size.x*0.5, size.y*0.5
            pieces.append(_points_bounds(
                transform.apply(Vec2(center.x+x, center.y+y))
                for x in (-hx, hx) for y in (-hy, hy)
            ))
        return Bounds2D.union(*pieces)
    raise TypeError(f"unsupported batch for bounds: {type(batch).__name__}")


def _vector_bounds(document, transform: Transform2D) -> Bounds2D:
    from .geometry import CubicBezier
    from .vector import VectorContour, VectorPath, vector_path_bounds
    if not document.paths:
        p = transform.apply(Vec2())
        return Bounds2D(p.x, p.y, p.x, p.y)
    pieces = []
    for path in document.paths:
        contours = tuple(
            VectorContour(tuple(CubicBezier(
                transform.apply(s.p0), transform.apply(s.p1),
                transform.apply(s.p2), transform.apply(s.p3),
            ) for s in contour.segments), contour.closed)
            for contour in path.contours
        )
        left, bottom, right, top = vector_path_bounds(VectorPath(contours, path.fill, path.stroke, path.group))
        pieces.append(Bounds2D(left, bottom, right, top))
    return Bounds2D.union(*pieces)


def bounds_of(obj, extra_transform: Transform2D = Transform2D()) -> Bounds2D:
    from .batch import BatchObject2D
    from .geometry import Object2D
    from .group import Group2D
    from .raster import RasterObject2D
    from .vector import VectorObject2D

    if isinstance(obj, Group2D):
        if not obj.children:
            p = (extra_transform @ obj.transform).apply(Vec2())
            return Bounds2D(p.x, p.y, p.x, p.y)
        child_extra = extra_transform @ obj.transform
        return Bounds2D.union(*(bounds_of(child, child_extra) for child in obj.children))
    transform = extra_transform @ obj.transform
    if isinstance(obj, Object2D):
        return _geometry_bounds(obj.geometry, transform)
    if isinstance(obj, BatchObject2D):
        return _batch_bounds(obj.batch, transform)
    if isinstance(obj, VectorObject2D):
        return _vector_bounds(obj.document, transform)
    if isinstance(obj, RasterObject2D):
        hx, hy = obj.width * 0.5, obj.height * 0.5
        return _points_bounds(
            transform.apply(Vec2(x, y)) for x in (-hx, hx) for y in (-hy, hy)
        )
    raise TypeError(f"object has no 2D bounds: {type(obj).__name__}")
