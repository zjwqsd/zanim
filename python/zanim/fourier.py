from __future__ import annotations

from cmath import exp
from dataclasses import dataclass
from functools import lru_cache
from math import cos, pi, sin, sqrt
from typing import Iterable

from .geometry import Color, PolygonGeometry, PolylineGeometry, Style
from .group import Group
from .plot import DynamicGeometryObject2D
from .space import Transform2D, Vec2


@dataclass(frozen=True, slots=True)
class FourierTerm:
    """One complex Fourier coefficient with an integer frequency."""

    frequency: int
    coefficient: complex

    @property
    def radius(self) -> float:
        return abs(self.coefficient)


def epicycle_chain(terms: Iterable[FourierTerm], phase: float) -> tuple[complex, ...]:
    """Return chain joints from origin through every rotating Fourier vector."""
    t = float(phase) % 1.0
    joints = [0j]
    current = 0j
    for term in terms:
        current += term.coefficient * exp(2j * pi * term.frequency * t)
        joints.append(current)
    return tuple(joints)


def _point2(value: complex) -> Vec2:
    return Vec2(float(value.real), float(value.imag))


def _circle_polyline(center: complex, radius: float, samples: int) -> PolylineGeometry:
    return PolylineGeometry(
        tuple(
            Vec2(
                center.real + radius * cos(2 * pi * i / samples),
                center.imag + radius * sin(2 * pi * i / samples),
            )
            for i in range(samples + 1)
        )
    )


def _arrow_polygon(start: complex, end: complex) -> PolygonGeometry:
    dx, dy = end.real - start.real, end.imag - start.imag
    length = sqrt(dx * dx + dy * dy)
    if length <= 1e-8:
        p = _point2(start)
        eps = 1e-5
        return PolygonGeometry((p, Vec2(p.x + eps, p.y), Vec2(p.x, p.y + eps)))
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    shaft_half = min(0.018, length * 0.08)
    tip_length = min(0.15, length * 0.32)
    tip_half = min(0.065, max(shaft_half * 2.4, length * 0.10))
    bx, by = end.real - ux * tip_length, end.imag - uy * tip_length
    return PolygonGeometry(
        (
            Vec2(start.real + nx * shaft_half, start.imag + ny * shaft_half),
            Vec2(bx + nx * shaft_half, by + ny * shaft_half),
            Vec2(bx + nx * tip_half, by + ny * tip_half),
            Vec2(end.real, end.imag),
            Vec2(bx - nx * tip_half, by - ny * tip_half),
            Vec2(bx - nx * shaft_half, by - ny * shaft_half),
            Vec2(start.real - nx * shaft_half, start.imag - ny * shaft_half),
        )
    )


def _tip_polygon(point: complex, radius: float, sides: int) -> PolygonGeometry:
    return PolygonGeometry(
        tuple(
            Vec2(
                point.real + radius * cos(2 * pi * i / sides),
                point.imag + radius * sin(2 * pi * i / sides),
            )
            for i in range(sides)
        )
    )


class FourierEpicycles(Group):
    """Portable Fourier epicycle visualization driven by absolute scene time.

    Native rendering deliberately decomposes this semantic object into ordinary
    DynamicGeometryObject2D children, so it reuses the existing renderer. Scene
    IR and Web can preserve the compact coefficient representation instead of
    baking every generated circle/arrow/trace at every video frame.
    """

    __slots__ = (
        "terms",
        "start_time",
        "draw_duration",
        "circle_samples",
        "trace_samples",
        "visual_indices",
        "circle_style",
        "arrow_style",
        "trace_style",
        "tip_style",
        "tip_radius",
        "tip_sides",
    )

    def __init__(
        self,
        terms: Iterable[FourierTerm],
        *,
        start_time: float = 0.0,
        draw_duration: float = 1.0,
        circle_samples: int = 28,
        trace_samples: int = 1000,
        visual_indices: Iterable[int] | None = None,
        circle_style: Style = Style.outline(Color(132, 157, 198, 82), 0.012),
        arrow_style: Style = Style.solid(Color(205, 220, 245, 190)),
        trace_style: Style = Style.outline(Color(255, 108, 139), 0.045),
        tip_style: Style = Style.solid(Color(255, 204, 214)),
        tip_radius: float = 0.055,
        tip_sides: int = 14,
        transform: Transform2D = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        terms = tuple(terms)
        if not terms:
            raise ValueError("FourierEpicycles requires at least one term")
        if draw_duration <= 0:
            raise ValueError("draw_duration must be positive")
        if circle_samples < 3 or trace_samples < 2 or tip_sides < 3:
            raise ValueError("FourierEpicycles sample counts are too small")
        self.terms = terms
        self.start_time = float(start_time)
        self.draw_duration = float(draw_duration)
        self.circle_samples = int(circle_samples)
        self.trace_samples = int(trace_samples)
        self.visual_indices = tuple(
            visual_indices
            if visual_indices is not None
            else (i for i, term in enumerate(terms) if term.frequency != 0 and term.radius > 2e-4)
        )
        self.circle_style = circle_style
        self.arrow_style = arrow_style
        self.trace_style = trace_style
        self.tip_style = tip_style
        self.tip_radius = float(tip_radius)
        self.tip_sides = int(tip_sides)

        def phase_at(time: float) -> float:
            return max(0.0, min(1.0, (float(time) - self.start_time) / self.draw_duration))

        @lru_cache(maxsize=2048)
        def chain_at(time: float) -> tuple[complex, ...]:
            return epicycle_chain(self.terms, phase_at(time))

        children = []
        for index in self.visual_indices:
            radius = self.terms[index].radius
            children.append(
                DynamicGeometryObject2D(
                    lambda t, index=index, radius=radius: _circle_polyline(
                        chain_at(float(t))[index], radius, self.circle_samples
                    ),
                    style=self.circle_style,
                    z_index=0,
                )
            )
            children.append(
                DynamicGeometryObject2D(
                    lambda t, index=index: _arrow_polygon(
                        chain_at(float(t))[index], chain_at(float(t))[index + 1]
                    ),
                    style=self.arrow_style,
                    z_index=1,
                )
            )

        full_trace = tuple(
            epicycle_chain(self.terms, i / (self.trace_samples - 1))[-1]
            for i in range(self.trace_samples)
        )

        def trace_geometry(time: float) -> PolylineGeometry:
            phase = phase_at(time)
            end = max(1, min(self.trace_samples - 1, round(phase * (self.trace_samples - 1))))
            points = tuple(_point2(value) for value in full_trace[: end + 1])
            if len(points) < 2:
                points = (points[0], points[0])
            return PolylineGeometry(points)

        children.append(DynamicGeometryObject2D(trace_geometry, style=self.trace_style, z_index=4))
        children.append(
            DynamicGeometryObject2D(
                lambda t: _tip_polygon(chain_at(float(t))[-1], self.tip_radius, self.tip_sides),
                style=self.tip_style,
                z_index=5,
            )
        )
        super().__init__(children, transform=transform, opacity=opacity, z_index=z_index)

    def phase_at(self, time: float) -> float:
        return max(0.0, min(1.0, (float(time) - self.start_time) / self.draw_duration))
