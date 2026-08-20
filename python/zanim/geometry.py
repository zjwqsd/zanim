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


@dataclass(slots=True)
class Object2D(SceneObject2D):
    """Geometry plus an accumulated local-to-world affine transform.

    Local operations right-multiply the current transform; world operations
    left-multiply it. SE(2) operations are rigid affine wrappers on top of the
    same composition mechanism.
    """

    geometry: Geometry
    transform: Transform2D = Transform2D()
    style: Style = Style()
    opacity: float = 1.0
    z_index: int = 0
    trim: float = 1.0

    def __post_init__(self) -> None:
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
