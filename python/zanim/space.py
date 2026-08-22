from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, cos, isfinite, pi, sin


class TransformFrame(str, Enum):
    """Frame in which a relative transform is expressed.

    For an authored local-to-parent transform ``T``:
    - ``PARENT`` applies ``delta @ T``.
    - ``LOCAL`` applies ``T @ delta``.
    - ``WORLD`` expresses ``delta`` in world coordinates; Scene converts it
      through the parent world transform before updating ``T``.
    """

    LOCAL = "local"
    PARENT = "parent"
    WORLD = "world"


LOCAL = TransformFrame.LOCAL
PARENT = TransformFrame.PARENT
WORLD = TransformFrame.WORLD


@dataclass(frozen=True, slots=True)
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Vec2") -> "Vec2":
        if not isinstance(other, Vec2):
            return NotImplemented
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        if not isinstance(other, Vec2):
            return NotImplemented
        return Vec2(self.x - other.x, self.y - other.y)

    def __neg__(self) -> "Vec2":
        return Vec2(-self.x, -self.y)

    def __mul__(self, scalar: float) -> "Vec2":
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        return Vec2(self.x * float(scalar), self.y * float(scalar))

    def __rmul__(self, scalar: float) -> "Vec2":
        return self * scalar

    def __truediv__(self, scalar: float) -> "Vec2":
        scalar = float(scalar)
        if scalar == 0.0:
            raise ZeroDivisionError("cannot divide Vec2 by zero")
        return Vec2(self.x / scalar, self.y / scalar)

    @property
    def length(self) -> float:
        return (self.x * self.x + self.y * self.y) ** 0.5

    def normalized(self) -> "Vec2":
        length = self.length
        if length <= 1e-12:
            raise ValueError("cannot normalize a zero Vec2")
        return self / length


@dataclass(frozen=True, slots=True)
class Linear2D:
    """Pure 2x2 linear map in x-right / y-up mathematical coordinates."""

    xx: float = 1.0
    xy: float = 0.0
    yx: float = 0.0
    yy: float = 1.0

    def __matmul__(self, other: "Linear2D") -> "Linear2D":
        a, b = self, other
        return Linear2D(
            xx=a.xx * b.xx + a.xy * b.yx,
            xy=a.xx * b.xy + a.xy * b.yy,
            yx=a.yx * b.xx + a.yy * b.yx,
            yy=a.yx * b.xy + a.yy * b.yy,
        )

    @staticmethod
    def rotation(radians: float) -> "Linear2D":
        c, s = cos(radians), sin(radians)
        return Linear2D(xx=c, xy=-s, yx=s, yy=c)

    @staticmethod
    def scaling(x: float, y: float | None = None) -> "Linear2D":
        return Linear2D(xx=x, yy=x if y is None else y)

    @staticmethod
    def shear(x: float = 0.0, y: float = 0.0) -> "Linear2D":
        return Linear2D(xx=1.0, xy=x, yx=y, yy=1.0)

    @property
    def determinant(self) -> float:
        return self.xx * self.yy - self.xy * self.yx

    def apply(self, v: Vec2) -> Vec2:
        return Vec2(
            self.xx * v.x + self.xy * v.y,
            self.yx * v.x + self.yy * v.y,
        )

    def as_affine(self) -> "Transform2D":
        return Transform2D(xx=self.xx, xy=self.xy, yx=self.yx, yy=self.yy)


@dataclass(frozen=True, slots=True)
class Transform2D:
    """Affine matrix in x-right / y-up mathematical coordinates."""

    xx: float = 1.0
    xy: float = 0.0
    yx: float = 0.0
    yy: float = 1.0
    tx: float = 0.0
    ty: float = 0.0

    def __matmul__(self, other: "Transform2D") -> "Transform2D":
        a, b = self, other
        return Transform2D(
            xx=a.xx * b.xx + a.xy * b.yx,
            xy=a.xx * b.xy + a.xy * b.yy,
            yx=a.yx * b.xx + a.yy * b.yx,
            yy=a.yx * b.xy + a.yy * b.yy,
            tx=a.xx * b.tx + a.xy * b.ty + a.tx,
            ty=a.yx * b.tx + a.yy * b.ty + a.ty,
        )

    @staticmethod
    def translation(x: float, y: float) -> "Transform2D":
        return Transform2D(tx=x, ty=y)

    @staticmethod
    def scaling(x: float, y: float | None = None) -> "Transform2D":
        return Transform2D(xx=x, yy=x if y is None else y)

    @staticmethod
    def rotation(radians: float) -> "Transform2D":
        c, s = cos(radians), sin(radians)
        return Transform2D(xx=c, xy=-s, yx=s, yy=c)

    @staticmethod
    def shear(x: float = 0.0, y: float = 0.0) -> "Transform2D":
        """Return the affine shear ``[[1, x], [y, 1]]``."""
        return Transform2D(xx=1.0, xy=float(x), yx=float(y), yy=1.0)

    def translate(self, x: float, y: float) -> "Transform2D":
        """Append a translation in local coordinates (self @ translation)."""
        return self @ Transform2D.translation(x, y)

    def rotate(self, radians: float) -> "Transform2D":
        """Append a rotation in local coordinates (self @ rotation)."""
        return self @ Transform2D.rotation(radians)

    def scale(self, x: float, y: float | None = None) -> "Transform2D":
        """Append a scale in local coordinates (self @ scaling)."""
        return self @ Transform2D.scaling(x, y)

    def apply(self, p: Vec2) -> Vec2:
        return Vec2(
            self.xx * p.x + self.xy * p.y + self.tx,
            self.yx * p.x + self.yy * p.y + self.ty,
        )

    @property
    def determinant(self) -> float:
        return self.xx * self.yy - self.xy * self.yx

    def inverse(self) -> "Transform2D":
        """Return the inverse affine transform.

        Raises for singular transforms instead of silently approximating one.
        """
        det = self.determinant
        if abs(det) <= 1e-12:
            raise ValueError("Transform2D is singular and cannot be inverted")
        inv_xx, inv_xy = self.yy / det, -self.xy / det
        inv_yx, inv_yy = -self.yx / det, self.xx / det
        return Transform2D(
            xx=inv_xx,
            xy=inv_xy,
            yx=inv_yx,
            yy=inv_yy,
            tx=-(inv_xx * self.tx + inv_xy * self.ty),
            ty=-(inv_yx * self.tx + inv_yy * self.ty),
        )


@dataclass(frozen=True, slots=True)
class SE2:
    """Rigid 2D pose ``p_parent = R(theta) p_local + translation``."""

    theta: float = 0.0
    translation: Vec2 = Vec2()

    def __post_init__(self) -> None:
        if not isfinite(float(self.theta)):
            raise ValueError("SE2 theta must be finite")
        if not isfinite(self.translation.x) or not isfinite(self.translation.y):
            raise ValueError("SE2 translation must be finite")

    def __matmul__(self, other: "SE2") -> "SE2":
        """Group product; apply ``other`` first, then ``self``."""
        if not isinstance(other, SE2):
            return NotImplemented
        rotated = self.apply_vector(other.translation)
        return SE2(
            theta=self.theta + other.theta,
            translation=Vec2(
                rotated.x + self.translation.x,
                rotated.y + self.translation.y,
            ),
        )

    def inverse(self) -> "SE2":
        c, s = cos(self.theta), sin(self.theta)
        x, y = self.translation.x, self.translation.y
        return SE2(
            theta=-self.theta,
            translation=Vec2(-(c * x + s * y), -(-s * x + c * y)),
        )

    def apply_vector(self, v: Vec2) -> Vec2:
        c, s = cos(self.theta), sin(self.theta)
        return Vec2(c * v.x - s * v.y, s * v.x + c * v.y)

    def apply(self, p: Vec2) -> Vec2:
        v = self.apply_vector(p)
        return Vec2(v.x + self.translation.x, v.y + self.translation.y)

    def as_affine(self) -> Transform2D:
        c, s = cos(self.theta), sin(self.theta)
        return Transform2D(
            xx=c,
            xy=-s,
            yx=s,
            yy=c,
            tx=self.translation.x,
            ty=self.translation.y,
        )

    @staticmethod
    def from_affine(transform: Transform2D, *, tolerance: float = 1e-7) -> "SE2":
        """Convert a rigid affine transform to SE(2), rejecting scale/shear/reflection."""
        if not isinstance(transform, Transform2D):
            raise TypeError("SE2.from_affine() requires Transform2D")
        x_axis = Vec2(transform.xx, transform.yx)
        y_axis = Vec2(transform.xy, transform.yy)
        if abs(x_axis.length - 1.0) > tolerance or abs(y_axis.length - 1.0) > tolerance:
            raise ValueError("Transform2D is not rigid: basis vectors must have unit length")
        if abs(x_axis.x * y_axis.x + x_axis.y * y_axis.y) > tolerance:
            raise ValueError("Transform2D is not rigid: basis vectors must be orthogonal")
        if abs(transform.determinant - 1.0) > tolerance:
            raise ValueError("Transform2D is not in SE(2): determinant must be +1")
        return SE2(
            theta=atan2(transform.yx, transform.xx),
            translation=Vec2(transform.tx, transform.ty),
        )

    def interpolate(self, other: "SE2", alpha: float) -> "SE2":
        """Rigid interpolation with linear translation and shortest-angle rotation."""
        if not isinstance(other, SE2):
            raise TypeError("SE2.interpolate() requires SE2")
        t = max(0.0, min(1.0, float(alpha)))
        dtheta = (other.theta - self.theta + pi) % (2 * pi) - pi
        return SE2(
            theta=self.theta + dtheta * t,
            translation=self.translation + (other.translation - self.translation) * t,
        )


Point2 = Vec2 | tuple[float, float]


def as_vec2(value: Point2, *, name: str = "point") -> Vec2:
    if isinstance(value, Vec2):
        return value
    if isinstance(value, tuple) and len(value) == 2:
        x, y = value
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            return Vec2(float(x), float(y))
    raise TypeError(f"{name} must be Vec2 or a numeric (x, y) tuple")


def pose2d(*, position: Point2 = (0.0, 0.0), rotation: float = 0.0) -> SE2:
    """Construct a complete local-to-parent rigid pose."""
    return SE2(theta=float(rotation), translation=as_vec2(position, name="position"))


def affine2d(
    *,
    position: Point2 = (0.0, 0.0),
    rotation: float = 0.0,
    scale: float | tuple[float, float] = 1.0,
    shear: Point2 = (0.0, 0.0),
) -> Transform2D:
    """Construct ``Translation @ Rotation @ Shear @ Scale`` explicitly."""
    p = as_vec2(position, name="position")
    sh = as_vec2(shear, name="shear")
    if isinstance(scale, (int, float)):
        sx = sy = float(scale)
    elif (
        isinstance(scale, tuple)
        and len(scale) == 2
        and all(isinstance(v, (int, float)) for v in scale)
    ):
        sx, sy = float(scale[0]), float(scale[1])
    else:
        raise TypeError("scale must be a number or numeric (x, y) tuple")
    return (
        Transform2D.translation(p.x, p.y)
        @ Transform2D.rotation(float(rotation))
        @ Transform2D.shear(sh.x, sh.y)
        @ Transform2D.scaling(sx, sy)
    )


@dataclass(slots=True)
class Canvas:
    width: int = 1920
    height: int = 1080
    unit_size: float = 100.0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("canvas dimensions must be positive")
        if self.unit_size <= 0:
            raise ValueError("unit_size must be positive")

    @property
    def basis(self) -> Transform2D:
        # Mathematical y-up -> device y-down happens only here.
        return Transform2D(
            xx=self.unit_size,
            yy=-self.unit_size,
            tx=self.width * 0.5,
            ty=self.height * 0.5,
        )

    def world_to_device(self, point: Vec2, view: Transform2D = Transform2D()) -> Vec2:
        return (self.basis @ view).apply(point)
