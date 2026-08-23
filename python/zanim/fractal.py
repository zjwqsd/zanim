from __future__ import annotations

from dataclasses import dataclass

from .geometry import Color
from .infinite import InfiniteObject2D
from .space import SE2, Transform2D


@dataclass(slots=True, init=False)
class FractalField2D(InfiniteObject2D):
    """Base class for native unbounded escape-time fields.

    The mathematical field has no finite texture or source rectangle. The Zig
    renderer evaluates the current viewport directly for every frame.
    """

    fractal_kind: int
    max_iter: int
    escape_radius: float
    julia_c: complex
    color_shift: float
    color_scale: float
    palette_color: Color

    def _init_fractal(
        self,
        *,
        fractal_kind: int,
        julia_c: complex = 0j,
        transform: Transform2D | SE2 = Transform2D(),
        max_iter: int = 220,
        escape_radius: float = 2.0,
        inside_color: Color = Color(5, 7, 14),
        palette_color: Color = Color(130, 190, 255),
        color_shift: float = 0.0,
        color_scale: float = 1.0,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        max_iter = int(max_iter)
        if max_iter < 1 or max_iter > 100_000:
            raise ValueError("max_iter must be in [1, 100000]")
        escape_radius = float(escape_radius)
        if escape_radius < 2.0:
            raise ValueError("escape_radius must be at least 2")
        if not isinstance(inside_color, Color) or not isinstance(palette_color, Color):
            raise TypeError("inside_color and palette_color must be Color")
        if float(color_scale) <= 0.0:
            raise ValueError("color_scale must be positive")

        self.fractal_kind = int(fractal_kind)
        self.max_iter = max_iter
        self.escape_radius = escape_radius
        self.julia_c = complex(julia_c)
        self.color_shift = float(color_shift)
        self.color_scale = float(color_scale)
        self.palette_color = palette_color

        # Reuse the native unbounded-object transport. `stroke_width` has no
        # fractal meaning; the wire slot is deliberately ignored by Zig kind=3.
        self._init_common(
            transform=transform,
            color=inside_color,
            stroke_width=1.0,
            opacity=opacity,
            z_index=z_index,
        )


@dataclass(slots=True, init=False)
class MandelbrotSet(FractalField2D):
    """The unbounded Mandelbrot escape-time field ``z <- z² + c``."""

    def __init__(
        self,
        *,
        transform: Transform2D | SE2 = Transform2D(),
        max_iter: int = 220,
        escape_radius: float = 2.0,
        inside_color: Color = Color(5, 7, 14),
        palette_color: Color = Color(130, 190, 255),
        color_shift: float = 0.0,
        color_scale: float = 1.0,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        self._init_fractal(
            fractal_kind=1,
            transform=transform,
            max_iter=max_iter,
            escape_radius=escape_radius,
            inside_color=inside_color,
            palette_color=palette_color,
            color_shift=color_shift,
            color_scale=color_scale,
            opacity=opacity,
            z_index=z_index,
        )


@dataclass(slots=True, init=False)
class JuliaSet(FractalField2D):
    """The unbounded filled Julia escape-time field for one complex ``c``."""

    def __init__(
        self,
        c: complex,
        *,
        transform: Transform2D | SE2 = Transform2D(),
        max_iter: int = 220,
        escape_radius: float = 2.0,
        inside_color: Color = Color(5, 7, 14),
        palette_color: Color = Color(255, 160, 105),
        color_shift: float = 0.0,
        color_scale: float = 1.0,
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        self._init_fractal(
            fractal_kind=2,
            julia_c=complex(c),
            transform=transform,
            max_iter=max_iter,
            escape_radius=escape_radius,
            inside_color=inside_color,
            palette_color=palette_color,
            color_shift=color_shift,
            color_scale=color_scale,
            opacity=opacity,
            z_index=z_index,
        )
