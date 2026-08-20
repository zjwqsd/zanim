from __future__ import annotations

from math import atan2, ceil, cos, pi, radians, sin, sqrt, tan
import re

from .geometry import CubicBezier
from .space import Vec2
from .vector import VectorContour

_TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _lerp(a: Vec2, b: Vec2, t: float) -> Vec2:
    return Vec2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)


def _line(a: Vec2, b: Vec2) -> CubicBezier:
    return CubicBezier(a, _lerp(a, b, 1 / 3), _lerp(a, b, 2 / 3), b)


def _quadratic(a: Vec2, q: Vec2, b: Vec2) -> CubicBezier:
    return CubicBezier(
        a,
        Vec2(a.x + (q.x - a.x) * 2 / 3, a.y + (q.y - a.y) * 2 / 3),
        Vec2(b.x + (q.x - b.x) * 2 / 3, b.y + (q.y - b.y) * 2 / 3),
        b,
    )


def _map_ellipse(cx: float, cy: float, rx: float, ry: float, phi: float, p: Vec2) -> Vec2:
    c, s = cos(phi), sin(phi)
    return Vec2(cx + rx * p.x * c - ry * p.y * s, cy + rx * p.x * s + ry * p.y * c)


def _vector_angle(ux: float, uy: float, vx: float, vy: float) -> float:
    return atan2(ux * vy - uy * vx, ux * vx + uy * vy)


def _arc_to_cubics(
    start: Vec2,
    rx: float,
    ry: float,
    rotation_deg: float,
    large_arc: bool,
    sweep: bool,
    end: Vec2,
) -> list[CubicBezier]:
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0 or (
        abs(start.x - end.x) < 1e-12 and abs(start.y - end.y) < 1e-12
    ):
        return [] if start == end else [_line(start, end)]

    phi = radians(rotation_deg % 360.0)
    cp, sp = cos(phi), sin(phi)
    dx = (start.x - end.x) * 0.5
    dy = (start.y - end.y) * 0.5
    x1p = cp * dx + sp * dy
    y1p = -sp * dx + cp * dy

    scale_needed = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if scale_needed > 1.0:
        scale = sqrt(scale_needed)
        rx *= scale
        ry *= scale

    numerator = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    factor = 0.0 if denominator == 0 else sqrt(max(0.0, numerator / denominator))
    if large_arc == sweep:
        factor = -factor
    cxp = factor * (rx * y1p / ry)
    cyp = factor * (-ry * x1p / rx)
    cx = cp * cxp - sp * cyp + (start.x + end.x) * 0.5
    cy = sp * cxp + cp * cyp + (start.y + end.y) * 0.5

    ux = (x1p - cxp) / rx
    uy = (y1p - cyp) / ry
    vx = (-x1p - cxp) / rx
    vy = (-y1p - cyp) / ry
    theta = atan2(uy, ux)
    delta = _vector_angle(ux, uy, vx, vy)
    if not sweep and delta > 0:
        delta -= 2 * pi
    elif sweep and delta < 0:
        delta += 2 * pi

    count = max(1, int(ceil(abs(delta) / (pi / 2))))
    step = delta / count
    out: list[CubicBezier] = []
    previous = start
    for index in range(count):
        a0 = theta + index * step
        a1 = a0 + step
        k = 4.0 / 3.0 * tan(step / 4.0)
        u0 = Vec2(cos(a0), sin(a0))
        u3 = Vec2(cos(a1), sin(a1))
        u1 = Vec2(u0.x - k * u0.y, u0.y + k * u0.x)
        u2 = Vec2(u3.x + k * u3.y, u3.y - k * u3.x)
        p1 = _map_ellipse(cx, cy, rx, ry, phi, u1)
        p2 = _map_ellipse(cx, cy, rx, ry, phi, u2)
        p3 = end if index == count - 1 else _map_ellipse(cx, cy, rx, ry, phi, u3)
        out.append(CubicBezier(previous, p1, p2, p3))
        previous = p3
    return out


def parse_path_data(data: str) -> tuple[VectorContour, ...]:
    """Parse SVG path data and normalize every segment to cubic Beziers."""
    tokens = _TOKEN_RE.findall(data.replace(",", " "))
    i = 0
    command: str | None = None
    current = Vec2()
    contour_start = Vec2()
    segments: list[CubicBezier] = []
    contours: list[VectorContour] = []
    previous_cubic_control: Vec2 | None = None
    previous_quadratic_control: Vec2 | None = None

    def number() -> float:
        nonlocal i
        if i >= len(tokens) or tokens[i].isalpha():
            raise ValueError(f"invalid SVG path near token {i}: {data!r}")
        value = float(tokens[i])
        i += 1
        return value

    def point(relative: bool) -> Vec2:
        x, y = number(), number()
        return Vec2(current.x + x, current.y + y) if relative else Vec2(x, y)

    def finish(closed: bool) -> None:
        nonlocal segments
        if segments:
            contours.append(VectorContour(tuple(segments), closed=closed))
            segments = []

    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        if command is None:
            raise ValueError("SVG path does not start with a command")
        relative = command.islower()
        op = command.upper()

        if op == "Z":
            if abs(current.x - contour_start.x) > 1e-12 or abs(current.y - contour_start.y) > 1e-12:
                segments.append(_line(current, contour_start))
            current = contour_start
            finish(True)
            previous_cubic_control = previous_quadratic_control = None
            command = None
            continue

        if op == "M":
            p = point(relative)
            if segments:
                finish(False)
            current = contour_start = p
            previous_cubic_control = previous_quadratic_control = None
            command = "l" if relative else "L"
            continue

        if op == "L":
            p = point(relative)
            segments.append(_line(current, p))
            current = p
            previous_cubic_control = previous_quadratic_control = None
        elif op == "H":
            x = number() + (current.x if relative else 0.0)
            p = Vec2(x, current.y)
            segments.append(_line(current, p))
            current = p
            previous_cubic_control = previous_quadratic_control = None
        elif op == "V":
            y = number() + (current.y if relative else 0.0)
            p = Vec2(current.x, y)
            segments.append(_line(current, p))
            current = p
            previous_cubic_control = previous_quadratic_control = None
        elif op == "C":
            c1, c2, p = point(relative), point(relative), point(relative)
            segments.append(CubicBezier(current, c1, c2, p))
            current = p
            previous_cubic_control, previous_quadratic_control = c2, None
        elif op == "S":
            c1 = (
                current
                if previous_cubic_control is None
                else Vec2(
                    2 * current.x - previous_cubic_control.x,
                    2 * current.y - previous_cubic_control.y,
                )
            )
            c2, p = point(relative), point(relative)
            segments.append(CubicBezier(current, c1, c2, p))
            current = p
            previous_cubic_control, previous_quadratic_control = c2, None
        elif op == "Q":
            q, p = point(relative), point(relative)
            segments.append(_quadratic(current, q, p))
            current = p
            previous_quadratic_control, previous_cubic_control = q, None
        elif op == "T":
            q = (
                current
                if previous_quadratic_control is None
                else Vec2(
                    2 * current.x - previous_quadratic_control.x,
                    2 * current.y - previous_quadratic_control.y,
                )
            )
            p = point(relative)
            segments.append(_quadratic(current, q, p))
            current = p
            previous_quadratic_control, previous_cubic_control = q, None
        elif op == "A":
            rx, ry, rotation = number(), number(), number()
            large_arc, sweep = bool(int(number())), bool(int(number()))
            p = point(relative)
            segments.extend(_arc_to_cubics(current, rx, ry, rotation, large_arc, sweep, p))
            current = p
            previous_cubic_control = previous_quadratic_control = None
        else:
            raise ValueError(f"unsupported SVG path command: {command}")

    if segments:
        finish(False)
    return tuple(contours)
