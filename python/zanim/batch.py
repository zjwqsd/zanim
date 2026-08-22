from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .geometry import Color
from .object import SceneObject2D
from .space import SE2, Linear2D, Transform2D, Vec2


def _same_length(name: str, n: int, values: tuple[object, ...]) -> None:
    if len(values) != n:
        raise ValueError(f"{name} must contain {n} values, got {len(values)}")


@dataclass(frozen=True, slots=True, weakref_slot=True)
class LineSet:
    """Many independent line segments with per-line stroke data."""

    starts: tuple[Vec2, ...]
    ends: tuple[Vec2, ...]
    colors: tuple[Color, ...]
    widths: tuple[float, ...]

    def __post_init__(self) -> None:
        n = len(self.starts)
        if n == 0:
            raise ValueError("LineSet cannot be empty")
        _same_length("ends", n, self.ends)
        _same_length("colors", n, self.colors)
        _same_length("widths", n, self.widths)
        if any(width <= 0 for width in self.widths):
            raise ValueError("LineSet widths must be positive")

    def __len__(self) -> int:
        return len(self.starts)


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CircleSet:
    """Many circles with per-circle fill and optional stroke data."""

    centers: tuple[Vec2, ...]
    radii: tuple[float, ...]
    fills: tuple[Color, ...]
    stroke_colors: tuple[Color, ...] | None = None
    stroke_widths: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        n = len(self.centers)
        if n == 0:
            raise ValueError("CircleSet cannot be empty")
        _same_length("radii", n, self.radii)
        _same_length("fills", n, self.fills)
        if any(radius <= 0 for radius in self.radii):
            raise ValueError("CircleSet radii must be positive")
        if (self.stroke_colors is None) != (self.stroke_widths is None):
            raise ValueError("CircleSet stroke colors and widths must be provided together")
        if self.stroke_colors is not None:
            _same_length("stroke_colors", n, self.stroke_colors)
            assert self.stroke_widths is not None
            _same_length("stroke_widths", n, self.stroke_widths)
            if any(width <= 0 for width in self.stroke_widths):
                raise ValueError("CircleSet stroke widths must be positive")

    def __len__(self) -> int:
        return len(self.centers)


@dataclass(frozen=True, slots=True, weakref_slot=True)
class RectSet:
    """Many axis-aligned local rectangles with per-rectangle visual data."""

    centers: tuple[Vec2, ...]
    sizes: tuple[Vec2, ...]
    fills: tuple[Color, ...]
    stroke_colors: tuple[Color, ...] | None = None
    stroke_widths: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        n = len(self.centers)
        if n == 0:
            raise ValueError("RectSet cannot be empty")
        _same_length("sizes", n, self.sizes)
        _same_length("fills", n, self.fills)
        if any(size.x <= 0 or size.y <= 0 for size in self.sizes):
            raise ValueError("RectSet sizes must be positive")
        if (self.stroke_colors is None) != (self.stroke_widths is None):
            raise ValueError("RectSet stroke colors and widths must be provided together")
        if self.stroke_colors is not None:
            _same_length("stroke_colors", n, self.stroke_colors)
            assert self.stroke_widths is not None
            _same_length("stroke_widths", n, self.stroke_widths)
            if any(width <= 0 for width in self.stroke_widths):
                raise ValueError("RectSet stroke widths must be positive")

    def __len__(self) -> int:
        return len(self.centers)


BatchGeometry = LineSet | CircleSet | RectSet


@dataclass(slots=True)
class BatchObject2D(SceneObject2D):
    """A transformable collection rendered as one batch.

    The batch owns per-element visual data. The accumulated transform has the
    same local/world composition semantics as Object2D.
    """

    batch: BatchGeometry
    transform: Transform2D | SE2 = Transform2D()
    opacity: float = 1.0
    z_index: int = 0

    def __post_init__(self) -> None:
        self._validate_scene_state()

    def apply_linear_local(self, linear: Linear2D) -> "BatchObject2D":
        self.transform = self.transform @ linear.as_affine()
        return self

    def apply_linear_world(self, linear: Linear2D) -> "BatchObject2D":
        self.transform = linear.as_affine() @ self.transform
        return self

    def apply_se2_local(self, rigid: SE2) -> "BatchObject2D":
        self.transform = self.transform @ rigid.as_affine()
        return self

    def apply_se2_world(self, rigid: SE2) -> "BatchObject2D":
        self.transform = rigid.as_affine() @ self.transform
        return self


class DynamicBatchObject2D(BatchObject2D):
    """Persistent batch whose complete geometry is a pure function of absolute time.

    This is the batch analogue of ``DynamicGeometryObject2D``: the provider is
    stateless and may be evaluated in any order. Timeline ``BatchClip`` writes
    are intentionally disallowed because a dynamic provider already owns the
    complete batch channel.
    """

    __slots__ = ("provider",)

    def __init__(
        self,
        provider: Callable[[float], BatchGeometry],
        *,
        transform: Transform2D | SE2 = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        if not callable(provider):
            raise TypeError("dynamic batch provider must be callable")
        self.provider = provider
        initial = provider(0.0)
        if not isinstance(initial, (LineSet, CircleSet, RectSet)):
            raise TypeError("dynamic batch provider must return LineSet, CircleSet, or RectSet")
        super().__init__(initial, transform=transform, opacity=opacity, z_index=z_index)

    @property
    def is_dynamic(self) -> bool:
        return True

    def batch_at(self, time: float) -> BatchGeometry:
        value = self.provider(float(time))
        if not isinstance(value, (LineSet, CircleSet, RectSet)):
            raise TypeError("dynamic batch provider returned unsupported batch geometry")
        return value

    def _batch_at(self, time: float, initial: BatchGeometry) -> BatchGeometry:
        _ = initial
        return self.batch_at(time)
