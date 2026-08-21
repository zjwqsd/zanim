from __future__ import annotations

from dataclasses import dataclass
from math import pi

from .object import SceneObject2D
from .space import Linear2D, SE2, Transform2D, Vec2


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
    color: Color = Color(230, 232, 238)
    width: float = 0.035

    def __post_init__(self) -> None:
        if self.width <= 0:
            raise ValueError("stroke width must be positive")


@dataclass(frozen=True, slots=True)
class Style:
    fill: Color | None = None
    stroke: StrokeStyle | None = StrokeStyle()

    @staticmethod
    def solid(color: Color) -> "Style":
        """Fill only.  No implicit outline is added."""
        return Style(fill=color, stroke=None)

    @staticmethod
    def outline(color: Color, width: float = 0.035) -> "Style":
        """Stroke only.  Both color and width are explicit."""
        return Style(fill=None, stroke=StrokeStyle(color, width))

    @staticmethod
    def paint(fill: Color, stroke: Color, stroke_width: float = 0.035) -> "Style":
        """Explicit fill plus explicit outline."""
        return Style(fill=fill, stroke=StrokeStyle(stroke, stroke_width))


@dataclass(frozen=True, slots=True)
class Line:
    start: Vec2
    end: Vec2


@dataclass(frozen=True, slots=True)
class Polyline:
    points: tuple[Vec2, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("polyline requires at least 2 points")


@dataclass(frozen=True, slots=True)
class Polygon:
    points: tuple[Vec2, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 3:
            raise ValueError("polygon requires at least 3 points")


@dataclass(frozen=True, slots=True)
class Rectangle:
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("rectangle dimensions must be positive")


@dataclass(frozen=True, slots=True)
class Square:
    side: float

    def __post_init__(self) -> None:
        if self.side <= 0:
            raise ValueError("square side must be positive")


@dataclass(frozen=True, slots=True)
class Circle:
    radius: float

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("circle radius must be positive")


@dataclass(frozen=True, slots=True)
class Ellipse:
    radius_x: float
    radius_y: float

    def __post_init__(self) -> None:
        if self.radius_x <= 0 or self.radius_y <= 0:
            raise ValueError("ellipse radii must be positive")


@dataclass(frozen=True, slots=True)
class Arc:
    radius: float
    start_angle: float
    sweep_angle: float

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("arc radius must be positive")


@dataclass(frozen=True, slots=True)
class RegularPolygon:
    sides: int
    radius: float
    phase: float = pi / 2

    def __post_init__(self) -> None:
        if self.sides < 3:
            raise ValueError("regular polygon requires at least 3 sides")
        if self.radius <= 0:
            raise ValueError("regular polygon radius must be positive")


@dataclass(frozen=True, slots=True)
class CubicBezier:
    p0: Vec2
    p1: Vec2
    p2: Vec2
    p3: Vec2


Geometry = Line | Polyline | Polygon | Rectangle | Square | Circle | Ellipse | Arc | RegularPolygon | CubicBezier


@dataclass(slots=True, init=False)
class Object2D(SceneObject2D):
    """Geometry plus explicit initial visual/affine state.

    ``style=`` and ``transform=`` remain the complete low-level values. For
    ordinary authoring the constructor also accepts direct style sugar
    (``fill/stroke/stroke_width``) and affine sugar
    (``position/rotation/scale/shear``). Complete values and their sugar forms
    are mutually exclusive, so no supplied state is silently overwritten.
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
        style: Style | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        trim: float = 1.0,
        *,
        fill: Color | None = None,
        stroke: Color | None = None,
        stroke_width: float | None = None,
        position: Vec2 | tuple[float, float] | None = None,
        rotation: float | None = None,
        scale: float | tuple[float, float] | None = None,
        shear: Vec2 | tuple[float, float] | None = None,
    ) -> None:
        from .space import affine2d

        style_sugar = fill is not None or stroke is not None or stroke_width is not None
        if style is not None and style_sugar:
            raise ValueError("Object2D accepts either style= or fill/stroke style sugar, not both")
        if style is None:
            if style_sugar:
                resolved_fill = fill
                resolved_stroke = stroke
                if resolved_fill is not None and not isinstance(resolved_fill, Color):
                    raise TypeError("fill must be Color or None")
                if resolved_stroke is not None and not isinstance(resolved_stroke, Color):
                    raise TypeError("stroke must be Color or None")
                if stroke_width is not None and resolved_stroke is None:
                    raise ValueError("stroke_width requires a stroke color")
                width = 0.035 if stroke_width is None else float(stroke_width)
                resolved_style = Style(
                    fill=resolved_fill,
                    stroke=None if resolved_stroke is None else StrokeStyle(resolved_stroke, width),
                )
            else:
                resolved_style = Style()
        elif isinstance(style, Style):
            resolved_style = style
        else:
            raise TypeError("style must be Style")

        transform_sugar = any(value is not None for value in (position, rotation, scale, shear))
        if transform is not None and transform_sugar:
            raise ValueError(
                "Object2D accepts either transform= or position/rotation/scale/shear sugar, not both"
            )
        if transform is None:
            resolved_transform = (
                affine2d(
                    to=(0.0, 0.0) if position is None else position,
                    rotation=0.0 if rotation is None else rotation,
                    scale=1.0 if scale is None else scale,
                    shear=(0.0, 0.0) if shear is None else shear,
                )
                if transform_sugar else Transform2D()
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

    def apply_linear_local(self, linear: Linear2D) -> "Object2D":
        self.transform = self.transform @ linear.as_affine()
        return self

    def apply_linear_world(self, linear: Linear2D) -> "Object2D":
        self.transform = linear.as_affine() @ self.transform
        return self

    def apply_se2_local(self, rigid: SE2) -> "Object2D":
        self.transform = self.transform @ rigid.as_affine()
        return self

    def apply_se2_world(self, rigid: SE2) -> "Object2D":
        self.transform = rigid.as_affine() @ self.transform
        return self

    def local_to_world(self, point: Vec2) -> Vec2:
        return self.transform.apply(point)

    def _geometry_at(self, time: float, initial: Geometry) -> Geometry:
        """Return geometry for rendering at absolute time.

        Static Object2D keeps the geometry frozen at Scene.add time. Dynamic
        subclasses override this hook without requiring Scene type checks.
        """
        _ = time
        return initial
