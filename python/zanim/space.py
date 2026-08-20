from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin


@dataclass(frozen=True, slots=True)
class Vec2:
    x: float = 0.0
    y: float = 0.0


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


@dataclass(frozen=True, slots=True)
class SE2:
    """Rigid 2D pose: p' = R(theta) p + translation."""

    theta: float = 0.0
    translation: Vec2 = Vec2()

    def __matmul__(self, other: "SE2") -> "SE2":
        """Group product; apply ``other`` first, then ``self``."""
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
            xx=c, xy=-s, yx=s, yy=c,
            tx=self.translation.x, ty=self.translation.y,
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
