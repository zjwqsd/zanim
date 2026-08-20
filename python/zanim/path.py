from __future__ import annotations

from math import cos, pi, sin

from .geometry import (
    Arc, Circle, CubicBezier, Ellipse, Geometry, Line, Polygon, Polyline,
    Rectangle, RegularPolygon, Square, StrokeStyle, Style,
)
from .space import Vec2


def _lerp(a: Vec2, b: Vec2, t: float) -> Vec2:
    return Vec2(a.x + (b.x-a.x)*t, a.y + (b.y-a.y)*t)


def _cubic_point(c: CubicBezier, t: float) -> Vec2:
    u = 1-t
    return Vec2(
        u**3*c.p0.x + 3*u*u*t*c.p1.x + 3*u*t*t*c.p2.x + t**3*c.p3.x,
        u**3*c.p0.y + 3*u*u*t*c.p1.y + 3*u*t*t*c.p2.y + t**3*c.p3.y,
    )


def geometry_points(geometry: Geometry, samples: int = 96) -> tuple[Vec2, ...]:
    if isinstance(geometry, Line):
        return (geometry.start, geometry.end)
    if isinstance(geometry, Polyline):
        return geometry.points
    if isinstance(geometry, Polygon):
        return (*geometry.points, geometry.points[0])
    if isinstance(geometry, Rectangle):
        hx, hy = geometry.width/2, geometry.height/2
        p=(Vec2(-hx,-hy),Vec2(hx,-hy),Vec2(hx,hy),Vec2(-hx,hy))
        return (*p,p[0])
    if isinstance(geometry, Square):
        h=geometry.side/2
        p=(Vec2(-h,-h),Vec2(h,-h),Vec2(h,h),Vec2(-h,h))
        return (*p,p[0])
    if isinstance(geometry, Circle):
        return tuple(Vec2(geometry.radius*cos(2*pi*i/samples), geometry.radius*sin(2*pi*i/samples)) for i in range(samples+1))
    if isinstance(geometry, Ellipse):
        return tuple(Vec2(geometry.radius_x*cos(2*pi*i/samples), geometry.radius_y*sin(2*pi*i/samples)) for i in range(samples+1))
    if isinstance(geometry, Arc):
        count=max(2,int(samples*abs(geometry.sweep_angle)/(2*pi))+1)
        return tuple(Vec2(geometry.radius*cos(geometry.start_angle+geometry.sweep_angle*i/(count-1)), geometry.radius*sin(geometry.start_angle+geometry.sweep_angle*i/(count-1))) for i in range(count))
    if isinstance(geometry, RegularPolygon):
        p=tuple(Vec2(geometry.radius*cos(geometry.phase+2*pi*i/geometry.sides), geometry.radius*sin(geometry.phase+2*pi*i/geometry.sides)) for i in range(geometry.sides))
        return (*p,p[0])
    if isinstance(geometry, CubicBezier):
        return tuple(_cubic_point(geometry, i/(samples-1)) for i in range(samples))
    raise TypeError(f"unsupported geometry for path trim: {type(geometry).__name__}")


def trim_geometry(geometry: Geometry, fraction: float) -> Geometry:
    t=max(0.0,min(1.0,float(fraction)))
    if t >= 1.0:
        return geometry
    points=geometry_points(geometry)
    if t <= 0.0:
        return Line(points[0], points[0])
    lengths=[]
    total=0.0
    for a,b in zip(points,points[1:]):
        length=((b.x-a.x)**2+(b.y-a.y)**2)**0.5
        lengths.append(length); total+=length
    if total <= 1e-12:
        return Line(points[0], points[0])
    target=total*t
    out=[points[0]]
    walked=0.0
    for a,b,length in zip(points,points[1:],lengths):
        if walked+length <= target+1e-12:
            out.append(b); walked+=length; continue
        local=0.0 if length<=1e-12 else (target-walked)/length
        out.append(_lerp(a,b,max(0.0,min(1.0,local))))
        break
    if len(out) < 2:
        out.append(out[0])
    return Polyline(tuple(out))


def trim_style(style: Style, fraction: float) -> Style:
    if fraction >= 1.0:
        return style
    stroke=style.stroke
    if stroke is None and style.fill is not None:
        stroke=StrokeStyle(style.fill, 0.035)
    return Style(fill=None, stroke=stroke)


# ---------------------------------------------------------------------------
# Cubic/vector contour sampling
#
# These helpers are deliberately renderer-independent.  SVG import, motion
# along a path, curve analysis, and future geometry tools can all share the same
# arc-length parameterization without introducing task-specific concepts into
# Scene or Timeline.


def cubic_point(cubic: CubicBezier, t: float) -> Vec2:
    """Evaluate one cubic Bezier at ``t`` in [0, 1]."""
    t = max(0.0, min(1.0, float(t)))
    return _cubic_point(cubic, t)


def _point_line_distance(point: Vec2, a: Vec2, b: Vec2) -> float:
    dx, dy = b.x - a.x, b.y - a.y
    denom = (dx * dx + dy * dy) ** 0.5
    if denom <= 1e-15:
        return ((point.x - a.x) ** 2 + (point.y - a.y) ** 2) ** 0.5
    return abs(dy * point.x - dx * point.y + b.x * a.y - b.y * a.x) / denom


def _split_cubic(cubic: CubicBezier) -> tuple[CubicBezier, CubicBezier]:
    p01 = _lerp(cubic.p0, cubic.p1, 0.5)
    p12 = _lerp(cubic.p1, cubic.p2, 0.5)
    p23 = _lerp(cubic.p2, cubic.p3, 0.5)
    p012 = _lerp(p01, p12, 0.5)
    p123 = _lerp(p12, p23, 0.5)
    mid = _lerp(p012, p123, 0.5)
    return (
        CubicBezier(cubic.p0, p01, p012, mid),
        CubicBezier(mid, p123, p23, cubic.p3),
    )


def flatten_cubic(
    cubic: CubicBezier,
    *,
    tolerance: float = 1e-3,
    max_depth: int = 12,
) -> tuple[Vec2, ...]:
    """Approximate a cubic by a polyline with bounded geometric flatness.

    The returned tuple includes both endpoints. ``tolerance`` is measured in
    Zanim logical units and controls only analysis/sampling quality; it is not a
    renderer tessellation setting.
    """
    if tolerance <= 0:
        raise ValueError("flatten tolerance must be positive")
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")

    out: list[Vec2] = [cubic.p0]

    def visit(curve: CubicBezier, depth: int) -> None:
        flatness = max(
            _point_line_distance(curve.p1, curve.p0, curve.p3),
            _point_line_distance(curve.p2, curve.p0, curve.p3),
        )
        if flatness <= tolerance or depth >= max_depth:
            out.append(curve.p3)
            return
        left, right = _split_cubic(curve)
        visit(left, depth + 1)
        visit(right, depth + 1)

    visit(cubic, 0)
    return tuple(out)


def flatten_vector_contour(
    contour,
    *,
    tolerance: float = 1e-3,
) -> tuple[Vec2, ...]:
    """Flatten a ``VectorContour`` while preserving its contour topology."""
    from .vector import VectorContour
    if not isinstance(contour, VectorContour):
        raise TypeError("flatten_vector_contour requires VectorContour")
    points: list[Vec2] = []
    for segment in contour.segments:
        flat = flatten_cubic(segment, tolerance=tolerance)
        if points and flat and points[-1] == flat[0]:
            points.extend(flat[1:])
        else:
            points.extend(flat)
    if contour.closed and points:
        first, last = points[0], points[-1]
        if ((first.x-last.x)**2 + (first.y-last.y)**2) ** 0.5 > 1e-12:
            points.append(first)
    return tuple(points)


def resample_polyline_by_arclength(
    points: tuple[Vec2, ...] | list[Vec2],
    count: int,
    *,
    closed: bool,
) -> tuple[Vec2, ...]:
    """Resample a polyline at uniformly spaced arc-length positions.

    Closed curves return exactly ``count`` periodic samples and intentionally do
    not duplicate the first point at the end. Open curves include both
    endpoints.
    """
    source = tuple(points)
    if count < 2:
        raise ValueError("resample count must be >= 2")
    if len(source) < 2:
        raise ValueError("resampling requires at least two source points")

    if closed:
        first, last = source[0], source[-1]
        if ((first.x-last.x)**2 + (first.y-last.y)**2) ** 0.5 > 1e-12:
            source = (*source, first)

    lengths: list[float] = []
    cumulative = [0.0]
    for a, b in zip(source, source[1:]):
        length = ((b.x-a.x)**2 + (b.y-a.y)**2) ** 0.5
        lengths.append(length)
        cumulative.append(cumulative[-1] + length)
    total = cumulative[-1]
    if total <= 1e-12:
        raise ValueError("cannot resample a zero-length path")

    if closed:
        targets = [total * i / count for i in range(count)]
    else:
        targets = [total * i / (count - 1) for i in range(count)]

    out: list[Vec2] = []
    segment = 0
    for target in targets:
        while segment + 1 < len(cumulative) - 1 and cumulative[segment + 1] < target:
            segment += 1
        a, b = source[segment], source[segment + 1]
        length = lengths[segment]
        local = 0.0 if length <= 1e-15 else (target - cumulative[segment]) / length
        out.append(_lerp(a, b, max(0.0, min(1.0, local))))
    return tuple(out)


def sample_vector_contour_by_arclength(
    contour,
    count: int,
    *,
    tolerance: float = 1e-3,
) -> tuple[Vec2, ...]:
    """Uniform arc-length samples of a cubic ``VectorContour``."""
    flattened = flatten_vector_contour(contour, tolerance=tolerance)
    return resample_polyline_by_arclength(flattened, count, closed=contour.closed)
