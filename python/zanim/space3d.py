from __future__ import annotations

from dataclasses import dataclass
from math import acos, cos, isfinite, sin, sqrt


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> "Vec3":
        if abs(scalar) <= 1e-15:
            raise ZeroDivisionError("cannot divide Vec3 by zero")
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    @property
    def length(self) -> float:
        return sqrt(self.dot(self))

    def normalized(self) -> "Vec3":
        length = self.length
        if length <= 1e-15:
            raise ValueError("cannot normalize a zero Vec3")
        return self / length


@dataclass(frozen=True, slots=True)
class SO3:
    """A proper 3×3 rotation matrix with group-preserving interpolation."""

    m00: float = 1.0
    m01: float = 0.0
    m02: float = 0.0
    m10: float = 0.0
    m11: float = 1.0
    m12: float = 0.0
    m20: float = 0.0
    m21: float = 0.0
    m22: float = 1.0

    def __post_init__(self) -> None:
        values = tuple(value for row in self.as_rows() for value in row)
        if not all(isfinite(v) for v in values):
            raise ValueError("SO3 entries must be finite")
        rows = tuple(Vec3(*row) for row in self.as_rows())
        tolerance = 1e-6
        if any(abs(row.length - 1.0) > tolerance for row in rows):
            raise ValueError("SO3 rows must be unit length")
        if any(abs(rows[i].dot(rows[j])) > tolerance for i in range(3) for j in range(i + 1, 3)):
            raise ValueError("SO3 rows must be orthogonal")
        if abs(self.determinant - 1.0) > tolerance:
            raise ValueError("SO3 determinant must be +1")

    @staticmethod
    def rotation_axis(axis: Vec3, radians: float) -> "SO3":
        a = axis.normalized()
        x, y, z = a.x, a.y, a.z
        c, s = cos(radians), sin(radians)
        q = 1.0 - c
        return SO3(
            c + x * x * q,
            x * y * q - z * s,
            x * z * q + y * s,
            y * x * q + z * s,
            c + y * y * q,
            y * z * q - x * s,
            z * x * q - y * s,
            z * y * q + x * s,
            c + z * z * q,
        )

    @staticmethod
    def rotation_x(radians: float) -> "SO3":
        return SO3.rotation_axis(Vec3(1, 0, 0), radians)

    @staticmethod
    def rotation_y(radians: float) -> "SO3":
        return SO3.rotation_axis(Vec3(0, 1, 0), radians)

    @staticmethod
    def rotation_z(radians: float) -> "SO3":
        return SO3.rotation_axis(Vec3(0, 0, 1), radians)

    @staticmethod
    def from_quaternion(w: float, x: float, y: float, z: float) -> "SO3":
        norm = sqrt(w * w + x * x + y * y + z * z)
        if norm <= 1e-15:
            raise ValueError("SO3 quaternion must be non-zero")
        w, x, y, z = w / norm, x / norm, y / norm, z / norm
        return SO3(
            1 - 2 * (y * y + z * z),
            2 * (x * y - z * w),
            2 * (x * z + y * w),
            2 * (x * y + z * w),
            1 - 2 * (x * x + z * z),
            2 * (y * z - x * w),
            2 * (x * z - y * w),
            2 * (y * z + x * w),
            1 - 2 * (x * x + y * y),
        )

    @property
    def determinant(self) -> float:
        return (
            self.m00 * (self.m11 * self.m22 - self.m12 * self.m21)
            - self.m01 * (self.m10 * self.m22 - self.m12 * self.m20)
            + self.m02 * (self.m10 * self.m21 - self.m11 * self.m20)
        )

    def __matmul__(self, other: "SO3") -> "SO3":
        a, b = self, other
        return SO3(
            a.m00 * b.m00 + a.m01 * b.m10 + a.m02 * b.m20,
            a.m00 * b.m01 + a.m01 * b.m11 + a.m02 * b.m21,
            a.m00 * b.m02 + a.m01 * b.m12 + a.m02 * b.m22,
            a.m10 * b.m00 + a.m11 * b.m10 + a.m12 * b.m20,
            a.m10 * b.m01 + a.m11 * b.m11 + a.m12 * b.m21,
            a.m10 * b.m02 + a.m11 * b.m12 + a.m12 * b.m22,
            a.m20 * b.m00 + a.m21 * b.m10 + a.m22 * b.m20,
            a.m20 * b.m01 + a.m21 * b.m11 + a.m22 * b.m21,
            a.m20 * b.m02 + a.m21 * b.m12 + a.m22 * b.m22,
        )

    def apply(self, vector: Vec3) -> Vec3:
        return Vec3(
            self.m00 * vector.x + self.m01 * vector.y + self.m02 * vector.z,
            self.m10 * vector.x + self.m11 * vector.y + self.m12 * vector.z,
            self.m20 * vector.x + self.m21 * vector.y + self.m22 * vector.z,
        )

    def as_rows(self) -> tuple[tuple[float, float, float], ...]:
        return (
            (self.m00, self.m01, self.m02),
            (self.m10, self.m11, self.m12),
            (self.m20, self.m21, self.m22),
        )

    def as_quaternion(self) -> tuple[float, float, float, float]:
        trace = self.m00 + self.m11 + self.m22
        if trace > 0.0:
            s = sqrt(trace + 1.0) * 2.0
            w = 0.25 * s
            x = (self.m21 - self.m12) / s
            y = (self.m02 - self.m20) / s
            z = (self.m10 - self.m01) / s
        elif self.m00 > self.m11 and self.m00 > self.m22:
            s = sqrt(1.0 + self.m00 - self.m11 - self.m22) * 2.0
            w = (self.m21 - self.m12) / s
            x = 0.25 * s
            y = (self.m01 + self.m10) / s
            z = (self.m02 + self.m20) / s
        elif self.m11 > self.m22:
            s = sqrt(1.0 + self.m11 - self.m00 - self.m22) * 2.0
            w = (self.m02 - self.m20) / s
            x = (self.m01 + self.m10) / s
            y = 0.25 * s
            z = (self.m12 + self.m21) / s
        else:
            s = sqrt(1.0 + self.m22 - self.m00 - self.m11) * 2.0
            w = (self.m10 - self.m01) / s
            x = (self.m02 + self.m20) / s
            y = (self.m12 + self.m21) / s
            z = 0.25 * s
        norm = sqrt(w * w + x * x + y * y + z * z)
        return w / norm, x / norm, y / norm, z / norm

    def slerp(self, other: "SO3", alpha: float) -> "SO3":
        t = max(0.0, min(1.0, float(alpha)))
        q0 = self.as_quaternion()
        q1 = other.as_quaternion()
        dot = sum(a * b for a, b in zip(q0, q1))
        if dot < 0.0:
            q1 = tuple(-v for v in q1)
            dot = -dot
        dot = max(-1.0, min(1.0, dot))
        if dot > 0.9995:
            q = tuple(a + t * (b - a) for a, b in zip(q0, q1))
        else:
            theta = acos(dot)
            sin_theta = sin(theta)
            a_weight = sin((1.0 - t) * theta) / sin_theta
            b_weight = sin(t * theta) / sin_theta
            q = tuple(a_weight * a + b_weight * b for a, b in zip(q0, q1))
        return SO3.from_quaternion(*q)

    def to_transform3d(self) -> "Transform3D":
        return Transform3D(
            self.m00,
            self.m01,
            self.m02,
            0.0,
            self.m10,
            self.m11,
            self.m12,
            0.0,
            self.m20,
            self.m21,
            self.m22,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        )


@dataclass(frozen=True, slots=True)
class Transform3D:
    """Row-major affine 4x4 transform acting on column vectors."""

    m00: float = 1.0
    m01: float = 0.0
    m02: float = 0.0
    m03: float = 0.0
    m10: float = 0.0
    m11: float = 1.0
    m12: float = 0.0
    m13: float = 0.0
    m20: float = 0.0
    m21: float = 0.0
    m22: float = 1.0
    m23: float = 0.0
    m30: float = 0.0
    m31: float = 0.0
    m32: float = 0.0
    m33: float = 1.0

    def __matmul__(self, other: "Transform3D") -> "Transform3D":
        a, b = self, other
        return Transform3D(
            a.m00 * b.m00 + a.m01 * b.m10 + a.m02 * b.m20 + a.m03 * b.m30,
            a.m00 * b.m01 + a.m01 * b.m11 + a.m02 * b.m21 + a.m03 * b.m31,
            a.m00 * b.m02 + a.m01 * b.m12 + a.m02 * b.m22 + a.m03 * b.m32,
            a.m00 * b.m03 + a.m01 * b.m13 + a.m02 * b.m23 + a.m03 * b.m33,
            a.m10 * b.m00 + a.m11 * b.m10 + a.m12 * b.m20 + a.m13 * b.m30,
            a.m10 * b.m01 + a.m11 * b.m11 + a.m12 * b.m21 + a.m13 * b.m31,
            a.m10 * b.m02 + a.m11 * b.m12 + a.m12 * b.m22 + a.m13 * b.m32,
            a.m10 * b.m03 + a.m11 * b.m13 + a.m12 * b.m23 + a.m13 * b.m33,
            a.m20 * b.m00 + a.m21 * b.m10 + a.m22 * b.m20 + a.m23 * b.m30,
            a.m20 * b.m01 + a.m21 * b.m11 + a.m22 * b.m21 + a.m23 * b.m31,
            a.m20 * b.m02 + a.m21 * b.m12 + a.m22 * b.m22 + a.m23 * b.m32,
            a.m20 * b.m03 + a.m21 * b.m13 + a.m22 * b.m23 + a.m23 * b.m33,
            a.m30 * b.m00 + a.m31 * b.m10 + a.m32 * b.m20 + a.m33 * b.m30,
            a.m30 * b.m01 + a.m31 * b.m11 + a.m32 * b.m21 + a.m33 * b.m31,
            a.m30 * b.m02 + a.m31 * b.m12 + a.m32 * b.m22 + a.m33 * b.m32,
            a.m30 * b.m03 + a.m31 * b.m13 + a.m32 * b.m23 + a.m33 * b.m33,
        )

    @staticmethod
    def translation(x: float, y: float, z: float) -> "Transform3D":
        return Transform3D(m03=float(x), m13=float(y), m23=float(z))

    @staticmethod
    def scaling(x: float, y: float | None = None, z: float | None = None) -> "Transform3D":
        y = x if y is None else y
        z = x if z is None else z
        return Transform3D(m00=float(x), m11=float(y), m22=float(z))

    @staticmethod
    def rotation_x(radians: float) -> "Transform3D":
        return SO3.rotation_x(radians).to_transform3d()

    @staticmethod
    def rotation_y(radians: float) -> "Transform3D":
        return SO3.rotation_y(radians).to_transform3d()

    @staticmethod
    def rotation_z(radians: float) -> "Transform3D":
        return SO3.rotation_z(radians).to_transform3d()

    @staticmethod
    def rotation_axis(axis: Vec3, radians: float) -> "Transform3D":
        return SO3.rotation_axis(axis, radians).to_transform3d()

    @staticmethod
    def from_so3(rotation: SO3, translation: Vec3 = Vec3()) -> "Transform3D":
        result = rotation.to_transform3d()
        return Transform3D(
            result.m00,
            result.m01,
            result.m02,
            translation.x,
            result.m10,
            result.m11,
            result.m12,
            translation.y,
            result.m20,
            result.m21,
            result.m22,
            translation.z,
            0.0,
            0.0,
            0.0,
            1.0,
        )

    def translate(self, x: float, y: float, z: float) -> "Transform3D":
        return self @ Transform3D.translation(x, y, z)

    def scale(self, x: float, y: float | None = None, z: float | None = None) -> "Transform3D":
        return self @ Transform3D.scaling(x, y, z)

    def rotate_x(self, radians: float) -> "Transform3D":
        return self @ Transform3D.rotation_x(radians)

    def rotate_y(self, radians: float) -> "Transform3D":
        return self @ Transform3D.rotation_y(radians)

    def rotate_z(self, radians: float) -> "Transform3D":
        return self @ Transform3D.rotation_z(radians)

    def apply(self, point: Vec3) -> Vec3:
        x = self.m00 * point.x + self.m01 * point.y + self.m02 * point.z + self.m03
        y = self.m10 * point.x + self.m11 * point.y + self.m12 * point.z + self.m13
        z = self.m20 * point.x + self.m21 * point.y + self.m22 * point.z + self.m23
        w = self.m30 * point.x + self.m31 * point.y + self.m32 * point.z + self.m33
        if abs(w) <= 1e-15:
            raise ValueError("Transform3D produced a point at infinity")
        return Vec3(x / w, y / w, z / w)

    def as_rows(self) -> tuple[tuple[float, float, float, float], ...]:
        return (
            (self.m00, self.m01, self.m02, self.m03),
            (self.m10, self.m11, self.m12, self.m13),
            (self.m20, self.m21, self.m22, self.m23),
            (self.m30, self.m31, self.m32, self.m33),
        )

    def as_tuple(self) -> tuple[float, ...]:
        return tuple(value for row in self.as_rows() for value in row)
