from __future__ import annotations

from dataclasses import dataclass

from .geometry import Color, CubicBezier, StrokeStyle
from .object import SceneObject2D
from .space import Linear2D, SE2, Transform2D


@dataclass(frozen=True, slots=True)
class VectorContour:
    """One SVG-like contour normalized to cubic Bezier segments."""

    segments: tuple[CubicBezier, ...]
    closed: bool = True

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("vector contour requires at least one segment")


@dataclass(frozen=True, slots=True)
class VectorPath:
    """One paint operation containing one or more contours.

    Keeping all contours of a glyph/path together preserves non-zero fill holes
    (for example the counters in O, B, 8) when the Zig renderer fills it.
    """

    contours: tuple[VectorContour, ...]
    fill: Color | None = Color(240, 242, 248)
    stroke: StrokeStyle | None = None
    group: int = 0

    def __post_init__(self) -> None:
        if not self.contours:
            raise ValueError("vector path requires at least one contour")
        if self.group < 0:
            raise ValueError("vector path group must be >= 0")


@dataclass(frozen=True, slots=True)
class VectorDocument:
    """Immutable vector resource, typically imported from SVG/Typst."""

    paths: tuple[VectorPath, ...]
    width: float
    height: float
    group_count: int = 1

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("vector document dimensions must be positive")
        if self.group_count < 0:
            raise ValueError("group_count must be >= 0")
        if self.paths and self.group_count == 0:
            raise ValueError("non-empty vector document requires at least one group")
        if self.paths and max(path.group for path in self.paths) >= self.group_count:
            raise ValueError("vector path group is outside document group_count")


@dataclass(slots=True)
class VectorObject2D(SceneObject2D):
    """Persistent scene object backed by an immutable VectorDocument."""

    document: VectorDocument
    transform: Transform2D = Transform2D()
    reveal: float = 1.0
    opacity: float = 1.0
    z_index: int = 0

    def __post_init__(self) -> None:
        self._validate_scene_state()
        if not 0.0 <= self.reveal <= 1.0:
            raise ValueError("reveal must be in [0, 1]")

    def _document_at(self, time: float, initial: VectorDocument) -> VectorDocument:
        """Return the render document at absolute time. Static data stays frozen."""
        _ = time
        return initial

    def apply_linear_local(self, linear: Linear2D) -> "VectorObject2D":
        self.transform = self.transform @ linear.as_affine()
        return self

    def apply_linear_world(self, linear: Linear2D) -> "VectorObject2D":
        self.transform = linear.as_affine() @ self.transform
        return self

    def apply_se2_local(self, rigid: SE2) -> "VectorObject2D":
        self.transform = self.transform @ rigid.as_affine()
        return self

    def apply_se2_world(self, rigid: SE2) -> "VectorObject2D":
        self.transform = rigid.as_affine() @ self.transform
        return self



def _cubic_axis_bounds(p0: float, p1: float, p2: float, p3: float) -> tuple[float, float]:
    """Exact scalar bounds of one cubic Bezier component on t in [0, 1]."""
    values = [p0, p3]
    # derivative / 3 = a*t^2 + b*t + c
    a = -p0 + 3.0 * p1 - 3.0 * p2 + p3
    b = 2.0 * (p0 - 2.0 * p1 + p2)
    c = p1 - p0
    if abs(a) < 1e-14:
        if abs(b) > 1e-14:
            t = -c / b
            if 0.0 < t < 1.0:
                u = 1.0 - t
                values.append(u**3*p0 + 3*u*u*t*p1 + 3*u*t*t*p2 + t**3*p3)
    else:
        disc = b*b - 4.0*a*c
        if disc >= 0.0:
            root = disc ** 0.5
            for t in ((-b-root)/(2*a), (-b+root)/(2*a)):
                if 0.0 < t < 1.0:
                    u = 1.0 - t
                    values.append(u**3*p0 + 3*u*u*t*p1 + 3*u*t*t*p2 + t**3*p3)
    return min(values), max(values)


def vector_path_bounds(path: VectorPath) -> tuple[float, float, float, float]:
    left = bottom = float('inf')
    right = top = float('-inf')
    for contour in path.contours:
        for seg in contour.segments:
            x0, x1 = _cubic_axis_bounds(seg.p0.x, seg.p1.x, seg.p2.x, seg.p3.x)
            y0, y1 = _cubic_axis_bounds(seg.p0.y, seg.p1.y, seg.p2.y, seg.p3.y)
            left, right = min(left, x0), max(right, x1)
            bottom, top = min(bottom, y0), max(top, y1)
    return left, bottom, right, top


def vector_document_bounds(document: VectorDocument) -> tuple[float, float, float, float]:
    if not document.paths:
        return (0.0, 0.0, 0.0, 0.0)
    bounds = [vector_path_bounds(path) for path in document.paths]
    return (
        min(b[0] for b in bounds), min(b[1] for b in bounds),
        max(b[2] for b in bounds), max(b[3] for b in bounds),
    )
