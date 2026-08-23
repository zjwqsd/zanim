from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import Color
from .object import SceneObject2D
from .space import SE2, Point2, Transform2D, Vec2, as_vec2
from .value import ScalarValue


@dataclass(slots=True, init=False)
class InfiniteObject2D(SceneObject2D):
    """Base class for mathematically unbounded native 2D objects."""

    transform: Transform2D
    opacity: float
    z_index: int
    color: Color
    stroke_width: float

    def _init_common(
        self,
        *,
        transform: Transform2D | SE2 = Transform2D(),
        color: Color = Color(180, 188, 208),
        stroke_width: float = 0.025,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        if isinstance(transform, SE2):
            transform = transform.as_affine()
        if not isinstance(transform, Transform2D):
            raise TypeError("transform must be Transform2D or SE2")
        if not isinstance(color, Color):
            raise TypeError("color must be Color")
        if float(stroke_width) <= 0.0:
            raise ValueError("stroke_width must be positive")
        self.transform = transform
        self.color = color
        self.stroke_width = float(stroke_width)
        self.opacity = float(opacity)
        self.z_index = int(z_index)
        self._validate_scene_state()

    def bounds(self):
        raise TypeError(f"{type(self).__name__} is unbounded and has no finite bounds")


@dataclass(slots=True, init=False)
class InfiniteLine(InfiniteObject2D):
    """An exact infinite line ``point + t * direction``, ``t ∈ R``."""

    point: Vec2
    direction: Vec2

    def __init__(
        self,
        point: Point2 = (0.0, 0.0),
        direction: Point2 = (1.0, 0.0),
        *,
        transform: Transform2D | SE2 = Transform2D(),
        color: Color = Color(230, 232, 238),
        stroke_width: float = 0.035,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        self.point = as_vec2(point, name="point")
        self.direction = as_vec2(direction, name="direction")
        if self.direction.length <= 1e-12:
            raise ValueError("InfiniteLine direction must be non-zero")
        self._init_common(
            transform=transform, color=color, stroke_width=stroke_width,
            opacity=opacity, z_index=z_index,
        )


@dataclass(slots=True, init=False)
class InfiniteGrid(InfiniteObject2D):
    """An exact axis-aligned infinite lattice in local coordinates."""

    origin: Vec2
    step: Vec2

    def __init__(
        self,
        step: float | tuple[float, float] = 1.0,
        *,
        origin: Point2 = (0.0, 0.0),
        transform: Transform2D | SE2 = Transform2D(),
        color: Color = Color(92, 105, 132, 180),
        stroke_width: float = 0.018,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        sx, sy = _grid_step(step)
        self.origin = as_vec2(origin, name="origin")
        self.step = Vec2(sx, sy)
        self._init_common(
            transform=transform, color=color, stroke_width=stroke_width,
            opacity=opacity, z_index=z_index,
        )


def _grid_step(step: float | tuple[float, float]) -> tuple[float, float]:
    if isinstance(step, (int, float)):
        sx = sy = float(step)
    else:
        if len(step) != 2:
            raise ValueError("step must be a scalar or (x_step, y_step)")
        sx, sy = float(step[0]), float(step[1])
    if sx <= 0.0 or sy <= 0.0:
        raise ValueError("grid step values must be positive")
    return sx, sy


_MAP_KINDS = {"square": 1, "exp": 2, "reciprocal": 3, "mobius": 4}


@dataclass(slots=True, init=False)
class ComplexMappedGrid(InfiniteObject2D):
    """An infinite complex lattice transformed natively by an analytic map.

    The Zig renderer evaluates inverse maps per target pixel; no finite source
    rectangle or Python-side curve sampling exists. Supported maps are deliberately
    small and explicit while the native representation is being validated:
    ``square``, ``exp``, ``reciprocal`` and ``mobius``.

    ``progress`` may be a float or a ``ScalarValue``. Square and reciprocal use
    exact identity→map homotopies. Exp uses the periodic analytic family
    ``exp(z)-1+(1-progress)*lambda*exp(-z)`` so the complete infinite lattice
    remains discrete throughout. Mobius maps use a nonsingular Gauss-decomposition
    path from identity to the requested matrix whenever ``d != 0``.
    """

    origin: Vec2
    step: Vec2
    map_kind: int
    progress: float | ScalarValue
    secondary_color: Color
    map_params: tuple[float, ...]

    def __init__(
        self,
        mapping: str,
        step: float | tuple[float, float] = 0.5,
        *,
        origin: Point2 = (0.0, 0.0),
        progress: float | ScalarValue = 1.0,
        exp_warp: complex = 1.0 + 0.0j,
        mobius: tuple[complex, complex, complex, complex] | None = None,
        x_color: Color = Color(255, 166, 92, 210),
        y_color: Color = Color(92, 180, 255, 210),
        stroke_width: float = 0.022,
        transform: Transform2D | SE2 = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        if mapping not in _MAP_KINDS:
            raise ValueError(f"unsupported complex mapping: {mapping!r}")
        sx, sy = _grid_step(step)
        self.origin = as_vec2(origin, name="origin")
        self.step = Vec2(sx, sy)
        self.map_kind = _MAP_KINDS[mapping]
        self.progress = progress
        self.secondary_color = y_color
        if not isinstance(x_color, Color) or not isinstance(y_color, Color):
            raise TypeError("x_color and y_color must be Color")

        if isinstance(progress, ScalarValue):
            p = float(progress.value)
        else:
            p = float(progress)
        if not 0.0 <= p <= 1.0:
            raise ValueError("progress must be in [0, 1]")

        params: tuple[float, ...] = ()
        if mapping == "exp":
            # Every member of the native exp family remains 2πi-periodic.  If
            # y-step divides 2π, all logarithm branches have identical lattice
            # membership, so a finite set of quadratic roots is exact.
            periods = 2.0 * math.pi / sy
            if abs(periods - round(periods)) > 1e-9:
                raise ValueError(
                    "exact infinite exp grid requires y_step = 2*pi/N; "
                    "otherwise horizontal grid images are dense in angle"
                )
            warp = complex(exp_warp)
            params = (warp.real, warp.imag)

        if mapping == "mobius":
            if mobius is None:
                raise ValueError("mobius mapping requires (a, b, c, d)")
            if len(mobius) != 4:
                raise ValueError("mobius must contain exactly (a, b, c, d)")
            a, b, c, d = (complex(v) for v in mobius)
            if abs(a * d - b * c) <= 1e-12:
                raise ValueError("mobius matrix must be nonsingular")
            if (isinstance(progress, ScalarValue) or p < 1.0 - 1e-12) and abs(d) <= 1e-12:
                raise ValueError("animated mobius path currently requires d != 0")
            params = (a.real, a.imag, b.real, b.imag, c.real, c.imag, d.real, d.imag)
        self.map_params = params
        self._init_common(
            transform=transform, color=x_color, stroke_width=stroke_width,
            opacity=opacity, z_index=z_index,
        )

    def progress_at(self, time: float) -> float:
        value = self.progress.value_at(time) if isinstance(self.progress, ScalarValue) else self.progress
        return max(0.0, min(1.0, float(value)))
