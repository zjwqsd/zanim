from __future__ import annotations

from dataclasses import dataclass
from math import pi

from .object import SceneObject2D
from .space import SE2, Transform2D, Vec2

DEFAULT_STROKE_WIDTH = 4.0 / 90.0
_UNSET = object()


@dataclass(frozen=True, slots=True)
class Color:
    r: int
    g: int
    b: int
    a: int = 255

    def __post_init__(self) -> None:
        if not all(0 <= v <= 255 for v in (self.r, self.g, self.b, self.a)):
            raise ValueError("color channels must be in [0, 255]")

    def with_alpha(self, alpha: int) -> "Color":
        """Return the same RGB color with one explicit 8-bit alpha value."""
        if not isinstance(alpha, int) or isinstance(alpha, bool):
            raise TypeError("alpha must be an integer in [0, 255]")
        return Color(self.r, self.g, self.b, alpha)


@dataclass(frozen=True, slots=True)
class StrokeStyle:
    color: Color = Color(255, 255, 255)
    width: float = DEFAULT_STROKE_WIDTH

    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError("stroke width must be positive")


@dataclass(frozen=True, slots=True)
class Style:
    fill: Color | None = None
    stroke: StrokeStyle | None = StrokeStyle()


@dataclass(frozen=True, slots=True)
class LineGeometry:
    start: Vec2
    end: Vec2


@dataclass(frozen=True, slots=True)
class PolylineGeometry:
    points: tuple[Vec2, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("polyline requires at least 2 points")


@dataclass(frozen=True, slots=True)
class PolygonGeometry:
    points: tuple[Vec2, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 3:
            raise ValueError("polygon requires at least 3 points")


@dataclass(frozen=True, slots=True)
class RectangleGeometry:
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("rectangle dimensions must be positive")


@dataclass(frozen=True, slots=True)
class SquareGeometry:
    side: float

    def __post_init__(self) -> None:
        if self.side <= 0:
            raise ValueError("square side must be positive")


@dataclass(frozen=True, slots=True)
class CircleGeometry:
    radius: float

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("circle radius must be positive")


@dataclass(frozen=True, slots=True)
class EllipseGeometry:
    radius_x: float
    radius_y: float

    def __post_init__(self) -> None:
        if self.radius_x <= 0 or self.radius_y <= 0:
            raise ValueError("ellipse radii must be positive")


@dataclass(frozen=True, slots=True)
class ArcGeometry:
    radius: float
    start_angle: float
    sweep_angle: float

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("arc radius must be positive")


@dataclass(frozen=True, slots=True)
class RegularPolygonGeometry:
    sides: int
    radius: float
    phase: float = pi / 2

    def __post_init__(self) -> None:
        if self.sides < 3:
            raise ValueError("regular polygon requires at least 3 sides")
        if self.radius <= 0:
            raise ValueError("regular polygon radius must be positive")


@dataclass(frozen=True, slots=True)
class CubicBezierGeometry:
    p0: Vec2
    p1: Vec2
    p2: Vec2
    p3: Vec2


Geometry = (
    LineGeometry
    | PolylineGeometry
    | PolygonGeometry
    | RectangleGeometry
    | SquareGeometry
    | CircleGeometry
    | EllipseGeometry
    | ArcGeometry
    | RegularPolygonGeometry
    | CubicBezierGeometry
)


@dataclass(slots=True, init=False)
class Object2D(SceneObject2D):
    """Geometry plus one explicit initial visual/affine state.

    Ordinary authoring uses fill/stroke/stroke_width and
    position/rotation/scale/shear. transform= remains the complete low-level
    affine escape hatch for code that already has a composed transform.
    """

    geometry: Geometry
    transform: Transform2D
    style: Style
    opacity: float
    z_index: int
    trim: float

    def __init__(
        self,
        geometry: Geometry,
        transform: Transform2D | SE2 | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        trim: float = 1.0,
        *,
        fill=_UNSET,
        stroke=_UNSET,
        stroke_width: float | None = None,
        position: Vec2 | tuple[float, float] | None = None,
        rotation: float | None = None,
        scale: float | tuple[float, float] | None = None,
        shear: Vec2 | tuple[float, float] | None = None,
    ) -> None:
        from .space import affine2d

        style_sugar = fill is not _UNSET or stroke is not _UNSET or stroke_width is not None
        if not style_sugar:
            resolved_style = Style()
        else:
            resolved_fill = None if fill is _UNSET else fill
            resolved_stroke = None if stroke is _UNSET else stroke
            if resolved_fill is not None and not isinstance(resolved_fill, Color):
                raise TypeError("fill must be Color or None")
            if resolved_stroke is not None and not isinstance(resolved_stroke, Color):
                raise TypeError("stroke must be Color or None")
            if resolved_stroke is None and stroke_width is not None:
                raise ValueError("stroke_width requires an explicit stroke color")
            width = DEFAULT_STROKE_WIDTH if stroke_width is None else float(stroke_width)
            resolved_style = Style(
                fill=resolved_fill,
                stroke=None if resolved_stroke is None else StrokeStyle(resolved_stroke, width),
            )

        transform_sugar = any(value is not None for value in (position, rotation, scale, shear))
        if transform is not None and transform_sugar:
            raise ValueError(
                "Object2D accepts either transform= or position/rotation/scale/shear sugar, not both"
            )
        if transform is None:
            resolved_transform = (
                affine2d(
                    position=(0.0, 0.0) if position is None else position,
                    rotation=0.0 if rotation is None else rotation,
                    scale=1.0 if scale is None else scale,
                    shear=(0.0, 0.0) if shear is None else shear,
                )
                if transform_sugar
                else Transform2D()
            )
        elif isinstance(transform, SE2):
            resolved_transform = transform.as_affine()
        elif isinstance(transform, Transform2D):
            resolved_transform = transform
        else:
            raise TypeError("transform must be Transform2D or SE2")

        self.geometry = geometry
        self.transform = resolved_transform
        self.style = resolved_style
        self.opacity = float(opacity)
        self.z_index = int(z_index)
        self.trim = float(trim)
        self._validate_scene_state()
        if not 0.0 <= self.trim <= 1.0:
            raise ValueError("trim must be in [0, 1]")

    def _geometry_at(self, time: float, initial: Geometry) -> Geometry:
        """Return geometry for rendering at absolute time.

        Static Object2D keeps the geometry frozen at Scene.add time. Dynamic
        subclasses override this hook without requiring Scene type checks.
        """
        _ = time
        return initial
