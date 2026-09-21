from __future__ import annotations

import ctypes
from math import acos, ceil, cos, hypot, pi, sin

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
    StrokeStyle,
)
from .group import Group
from .path import flatten_vector_contour
from .render.abi import load_library
from .space import Transform2D, Vec2
from .vector import VectorContour, VectorDocument, VectorObject2D, VectorPath


_OPERATION_IDS = {
    "intersection": 0,
    "union": 1,
    "difference": 2,
    "exclusion": 3,
}


def _linear_scale_bound(transform: Transform2D) -> float:
    # Upper bound on affine linear magnification; cheap and conservative enough
    # for converting world-space flatten tolerance into local coordinates.
    c0 = hypot(transform.xx, transform.yx)
    c1 = hypot(transform.xy, transform.yy)
    return max(1e-12, (c0 * c0 + c1 * c1) ** 0.5)


def _ellipse_sample_count(radius: float, tolerance: float) -> int:
    if radius <= 0:
        return 24
    if tolerance >= radius:
        return 24
    value = max(-1.0, min(1.0, 1.0 - tolerance / radius))
    half_angle = acos(value)
    if half_angle <= 1e-12:
        return 512
    return max(24, min(512, int(ceil(pi / half_angle))))


def _dedupe_closed(points: tuple[Vec2, ...] | list[Vec2], epsilon: float) -> tuple[Vec2, ...]:
    out: list[Vec2] = []
    eps2 = epsilon * epsilon
    for point in points:
        if out:
            dx, dy = point.x - out[-1].x, point.y - out[-1].y
            if dx * dx + dy * dy <= eps2:
                continue
        out.append(point)
    if len(out) >= 2:
        dx, dy = out[-1].x - out[0].x, out[-1].y - out[0].y
        if dx * dx + dy * dy <= eps2:
            out.pop()
    if len(out) < 3:
        raise ValueError("boolean operands require closed contours with at least 3 points")
    return tuple(out)


def _geometry_contour(geometry, *, tolerance: float) -> tuple[Vec2, ...]:
    if isinstance(geometry, PolygonGeometry):
        return geometry.points
    if isinstance(geometry, RectangleGeometry):
        hx, hy = geometry.width * 0.5, geometry.height * 0.5
        return (Vec2(-hx, -hy), Vec2(hx, -hy), Vec2(hx, hy), Vec2(-hx, hy))
    if isinstance(geometry, SquareGeometry):
        h = geometry.side * 0.5
        return (Vec2(-h, -h), Vec2(h, -h), Vec2(h, h), Vec2(-h, h))
    if isinstance(geometry, CircleGeometry):
        count = _ellipse_sample_count(geometry.radius, tolerance)
        return tuple(
            Vec2(
                geometry.radius * cos(2 * pi * i / count),
                geometry.radius * sin(2 * pi * i / count),
            )
            for i in range(count)
        )
    if isinstance(geometry, EllipseGeometry):
        count = _ellipse_sample_count(max(geometry.radius_x, geometry.radius_y), tolerance)
        return tuple(
            Vec2(
                geometry.radius_x * cos(2 * pi * i / count),
                geometry.radius_y * sin(2 * pi * i / count),
            )
            for i in range(count)
        )
    if isinstance(geometry, RegularPolygonGeometry):
        return tuple(
            Vec2(
                geometry.radius * cos(geometry.phase + 2 * pi * i / geometry.sides),
                geometry.radius * sin(geometry.phase + 2 * pi * i / geometry.sides),
            )
            for i in range(geometry.sides)
        )
    if isinstance(geometry, PolylineGeometry):
        points = geometry.points
        if len(points) >= 4:
            dx, dy = points[-1].x - points[0].x, points[-1].y - points[0].y
            if dx * dx + dy * dy <= tolerance * tolerance:
                return tuple(points[:-1])
        raise TypeError("open Polyline cannot be used as a boolean area")
    if isinstance(geometry, (LineGeometry, ArcGeometry, CubicBezierGeometry)):
        raise TypeError(f"open {type(geometry).__name__} cannot be used as a boolean area")
    raise TypeError(f"unsupported boolean geometry: {type(geometry).__name__}")


def _collect_contours(
    obj,
    *,
    parent_transform: Transform2D,
    tolerance: float,
) -> list[tuple[Vec2, ...]]:
    transform = parent_transform @ obj.transform

    if isinstance(obj, Group):
        contours: list[tuple[Vec2, ...]] = []
        for child in obj.children:
            contours.extend(
                _collect_contours(
                    child,
                    parent_transform=transform,
                    tolerance=tolerance,
                )
            )
        if not contours:
            raise ValueError("boolean operand Group must contain finite closed 2D geometry")
        return contours

    if isinstance(obj, Object2D):
        local_tolerance = tolerance / _linear_scale_bound(transform)
        local = _geometry_contour(obj.geometry, tolerance=local_tolerance)
        world = tuple(transform.apply(point) for point in local)
        return [_dedupe_closed(world, tolerance * 1e-3)]

    if isinstance(obj, VectorObject2D):
        contours = []
        local_tolerance = tolerance / _linear_scale_bound(transform)
        for path in obj.document.paths:
            for contour in path.contours:
                if not contour.closed:
                    continue
                flat = flatten_vector_contour(contour, tolerance=local_tolerance)
                world = tuple(transform.apply(point) for point in flat)
                contours.append(_dedupe_closed(world, tolerance * 1e-3))
        if not contours:
            raise ValueError("boolean VectorObject2D operand has no closed contours")
        return contours

    raise TypeError(
        "boolean operands support Shape/Object2D, VectorObject2D, and Group; "
        f"got {type(obj).__name__}"
    )


def _pack_contours(contours: list[tuple[Vec2, ...]]):
    flat: list[float] = []
    ends: list[int] = []
    count = 0
    for contour in contours:
        for point in contour:
            flat.extend((point.x, point.y))
        count += len(contour)
        ends.append(count)
    points_array = (ctypes.c_double * len(flat))(*flat)
    ends_array = (ctypes.c_uint32 * len(ends))(*ends)
    return points_array, count, ends_array, len(ends)


def _native_boolean(
    a_contours: list[tuple[Vec2, ...]],
    b_contours: list[tuple[Vec2, ...]],
    operation: str,
    epsilon: float,
) -> list[tuple[Vec2, ...]]:
    lib = load_library()
    a_points, a_count, a_ends, a_end_count = _pack_contours(a_contours)
    b_points, b_count, b_ends, b_end_count = _pack_contours(b_contours)

    # Every segment can be split by every segment of the other operand. This is
    # a safe one-pass upper bound; common curve booleans use only a tiny fraction.
    capacity = max(16, 2 * a_count * b_count + a_count + b_count + 16)
    capacity = min(capacity, 2_000_000)
    out_points = (ctypes.c_double * (capacity * 2))()
    out_ends = (ctypes.c_uint32 * capacity)()
    out_point_count = ctypes.c_uint32(0)
    out_contour_count = ctypes.c_uint32(0)

    def call(points_buf, point_capacity, ends_buf, contour_capacity):
        return int(
            lib.zanim_path_boolean(
                a_points,
                a_count,
                a_ends,
                a_end_count,
                b_points,
                b_count,
                b_ends,
                b_end_count,
                _OPERATION_IDS[operation],
                float(epsilon),
                points_buf,
                point_capacity,
                ends_buf,
                contour_capacity,
                ctypes.byref(out_point_count),
                ctypes.byref(out_contour_count),
            )
        )

    code = call(out_points, capacity, out_ends, capacity)
    if code == 5:
        capacity = max(int(out_point_count.value), int(out_contour_count.value), 1)
        out_points = (ctypes.c_double * (capacity * 2))()
        out_ends = (ctypes.c_uint32 * capacity)()
        code = call(out_points, capacity, out_ends, capacity)

    if code != 0:
        messages = {
            2: "invalid vector boolean input",
            3: "vector boolean topology could not be resolved",
            4: "vector boolean allocator failed",
            5: "vector boolean output exceeded capacity",
        }
        raise RuntimeError(messages.get(code, f"vector boolean backend failed with code {code}"))

    points = tuple(
        Vec2(out_points[i * 2], out_points[i * 2 + 1])
        for i in range(out_point_count.value)
    )
    contours: list[tuple[Vec2, ...]] = []
    start = 0
    for i in range(out_contour_count.value):
        end = int(out_ends[i])
        contour = points[start:end]
        if len(contour) >= 3:
            contours.append(contour)
        start = end
    return contours


def _line_cubic(a: Vec2, b: Vec2) -> CubicBezierGeometry:
    return CubicBezierGeometry(
        a,
        Vec2(a.x + (b.x - a.x) / 3.0, a.y + (b.y - a.y) / 3.0),
        Vec2(a.x + 2.0 * (b.x - a.x) / 3.0, a.y + 2.0 * (b.y - a.y) / 3.0),
        b,
    )


def _document_from_contours(
    contours: list[tuple[Vec2, ...]],
    *,
    color: Color,
    fill_opacity: float,
    stroke_width: float,
) -> VectorDocument:
    if not contours:
        return VectorDocument((), 1e-9, 1e-9, group_count=0)

    vector_contours = []
    all_points: list[Vec2] = []
    for points in contours:
        all_points.extend(points)
        segments = tuple(
            _line_cubic(points[i], points[(i + 1) % len(points)])
            for i in range(len(points))
        )
        vector_contours.append(VectorContour(segments, closed=True))

    fill_alpha = round(color.a * fill_opacity)
    fill = Color(color.r, color.g, color.b, fill_alpha)
    stroke = None if stroke_width <= 0 else StrokeStyle(color, stroke_width)
    path = VectorPath(tuple(vector_contours), fill=fill, stroke=stroke)

    left = min(p.x for p in all_points)
    right = max(p.x for p in all_points)
    bottom = min(p.y for p in all_points)
    top = max(p.y for p in all_points)
    return VectorDocument(
        (path,),
        max(1e-9, right - left),
        max(1e-9, top - bottom),
        group_count=1,
    )


class BooleanShape(VectorObject2D):
    """True vector boolean combination of finite closed 2D objects.

    Operands are flattened to line contours with a bounded world-space error,
    clipped by the shared Zig backend, and returned as a normal VectorObject2D.
    No raster mask is retained in the result.
    """

    def __init__(
        self,
        first,
        second,
        operation: str,
        *,
        color: Color = Color(255, 255, 255),
        fill_opacity: float = 0.5,
        stroke_width: float = DEFAULT_STROKE_WIDTH,
        tolerance: float = 1.0 / 512.0,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        if operation not in _OPERATION_IDS:
            raise ValueError(
                "operation must be one of: 'intersection', 'union', 'difference', 'exclusion'"
            )
        if not isinstance(color, Color):
            raise TypeError("color must be a Color")
        if not 0.0 <= float(fill_opacity) <= 1.0:
            raise ValueError("fill_opacity must be in [0, 1]")
        if float(stroke_width) < 0.0:
            raise ValueError("stroke_width must be >= 0")
        if not float(tolerance) > 0.0:
            raise ValueError("tolerance must be positive")

        a_contours = _collect_contours(
            first,
            parent_transform=Transform2D(),
            tolerance=float(tolerance),
        )
        b_contours = _collect_contours(
            second,
            parent_transform=Transform2D(),
            tolerance=float(tolerance),
        )
        epsilon = max(1e-10, float(tolerance) * 1e-5)
        contours = _native_boolean(a_contours, b_contours, operation, epsilon)
        document = _document_from_contours(
            contours,
            color=color,
            fill_opacity=float(fill_opacity),
            stroke_width=float(stroke_width),
        )

        self.operation = operation
        self.first = first
        self.second = second
        self.color = color
        self.fill_opacity = float(fill_opacity)
        self.stroke_width = float(stroke_width)
        self.tolerance = float(tolerance)
        self.backend = "vector"

        super().__init__(
            document=document,
            opacity=opacity,
            z_index=z_index,
        )


class Intersection(BooleanShape):
    def __init__(self, first, second, **kwargs) -> None:
        super().__init__(first, second, "intersection", **kwargs)


class Union(BooleanShape):
    def __init__(self, first, second, **kwargs) -> None:
        super().__init__(first, second, "union", **kwargs)


class Difference(BooleanShape):
    def __init__(self, first, second, **kwargs) -> None:
        super().__init__(first, second, "difference", **kwargs)


class Exclusion(BooleanShape):
    def __init__(self, first, second, **kwargs) -> None:
        super().__init__(first, second, "exclusion", **kwargs)


__all__ = [
    "BooleanShape",
    "Intersection",
    "Union",
    "Difference",
    "Exclusion",
]
