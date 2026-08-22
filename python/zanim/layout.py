from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Protocol

from .space import Point2, Transform2D, Vec2, as_vec2


@dataclass(frozen=True, slots=True)
class Anchor:
    """A normalized point inside visual bounds or a Frame.

    ``(-1, -1)`` is bottom-left, ``(0, 0)`` is center and ``(1, 1)`` is
    top-right. Intermediate values are allowed, so an anchor is a real layout
    value rather than a magic enum hidden inside positioning methods.
    """

    x: float = 0.0
    y: float = 0.0

    def __post_init__(self) -> None:
        if not -1.0 <= float(self.x) <= 1.0 or not -1.0 <= float(self.y) <= 1.0:
            raise ValueError("anchor coordinates must be in [-1, 1]")


def _anchor(value: Anchor | Vec2) -> Anchor:
    if isinstance(value, Anchor):
        return value
    if isinstance(value, Vec2):
        if not -1.0 <= value.x <= 1.0 or not -1.0 <= value.y <= 1.0:
            raise ValueError("Vec2 used as an anchor must have coordinates in [-1, 1]")
        return Anchor(value.x, value.y)
    raise TypeError("anchor must be Anchor or Vec2")


CENTER = Anchor(0, 0)
TOP = Anchor(0, 1)
BOTTOM = Anchor(0, -1)
LEFT_CENTER = Anchor(-1, 0)
RIGHT_CENTER = Anchor(1, 0)
TOP_LEFT = Anchor(-1, 1)
TOP_RIGHT = Anchor(1, 1)
BOTTOM_LEFT = Anchor(-1, -1)
BOTTOM_RIGHT = Anchor(1, -1)


@dataclass(frozen=True, slots=True)
class Frame:
    """An explicit world-space rectangular layout region."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        if self.x_min > self.x_max or self.y_min > self.y_max:
            raise ValueError("invalid frame")

    @staticmethod
    def from_canvas(canvas) -> "Frame":
        half_w = canvas.width / (2.0 * canvas.unit_size)
        half_h = canvas.height / (2.0 * canvas.unit_size)
        return Frame(-half_w, -half_h, half_w, half_h)

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    def anchor(self, anchor: Anchor | Vec2) -> Vec2:
        a = _anchor(anchor)
        return Vec2(
            (self.x_min + self.x_max) * 0.5 + a.x * self.width * 0.5,
            (self.y_min + self.y_max) * 0.5 + a.y * self.height * 0.5,
        )

    @property
    def center(self) -> Vec2:
        return self.anchor(CENTER)

    @property
    def top(self) -> Vec2:
        return self.anchor(TOP)

    @property
    def bottom(self) -> Vec2:
        return self.anchor(BOTTOM)

    @property
    def left(self) -> Vec2:
        return self.anchor(LEFT_CENTER)

    @property
    def right(self) -> Vec2:
        return self.anchor(RIGHT_CENTER)

    @property
    def top_left(self) -> Vec2:
        return self.anchor(TOP_LEFT)

    @property
    def top_right(self) -> Vec2:
        return self.anchor(TOP_RIGHT)

    @property
    def bottom_left(self) -> Vec2:
        return self.anchor(BOTTOM_LEFT)

    @property
    def bottom_right(self) -> Vec2:
        return self.anchor(BOTTOM_RIGHT)

    def inset(self, x: float, y: float | None = None) -> "Frame":
        x = float(x)
        y = x if y is None else float(y)
        if x < 0 or y < 0:
            raise ValueError("frame inset must be >= 0")
        if 2 * x > self.width or 2 * y > self.height:
            raise ValueError("frame inset is too large")
        return Frame(self.x_min + x, self.y_min + y, self.x_max - x, self.y_max - y)

    def top_region(self, *, height: float) -> "Frame":
        height = float(height)
        if not 0 <= height <= self.height:
            raise ValueError("region height must fit inside frame")
        return Frame(self.x_min, self.y_max - height, self.x_max, self.y_max)

    def bottom_region(self, *, height: float) -> "Frame":
        height = float(height)
        if not 0 <= height <= self.height:
            raise ValueError("region height must fit inside frame")
        return Frame(self.x_min, self.y_min, self.x_max, self.y_min + height)

    def left_region(self, *, width: float) -> "Frame":
        width = float(width)
        if not 0 <= width <= self.width:
            raise ValueError("region width must fit inside frame")
        return Frame(self.x_min, self.y_min, self.x_min + width, self.y_max)

    def right_region(self, *, width: float) -> "Frame":
        width = float(width)
        if not 0 <= width <= self.width:
            raise ValueError("region width must fit inside frame")
        return Frame(self.x_max - width, self.y_min, self.x_max, self.y_max)

    def below(self, other: "Frame", *, gap: float = 0.0) -> "Frame":
        gap = float(gap)
        if gap < 0:
            raise ValueError("gap must be >= 0")
        y_max = min(self.y_max, other.y_min - gap)
        if y_max < self.y_min:
            raise ValueError("no frame remains below the reference region")
        return Frame(self.x_min, self.y_min, self.x_max, y_max)

    def above(self, other: "Frame", *, gap: float = 0.0) -> "Frame":
        gap = float(gap)
        if gap < 0:
            raise ValueError("gap must be >= 0")
        y_min = max(self.y_min, other.y_max + gap)
        if y_min > self.y_max:
            raise ValueError("no frame remains above the reference region")
        return Frame(self.x_min, y_min, self.x_max, self.y_max)

    def left_of(self, other: "Frame", *, gap: float = 0.0) -> "Frame":
        gap = float(gap)
        if gap < 0:
            raise ValueError("gap must be >= 0")
        x_max = min(self.x_max, other.x_min - gap)
        if x_max < self.x_min:
            raise ValueError("no frame remains left of the reference region")
        return Frame(self.x_min, self.y_min, x_max, self.y_max)

    def right_of(self, other: "Frame", *, gap: float = 0.0) -> "Frame":
        gap = float(gap)
        if gap < 0:
            raise ValueError("gap must be >= 0")
        x_min = max(self.x_min, other.x_max + gap)
        if x_min > self.x_max:
            raise ValueError("no frame remains right of the reference region")
        return Frame(x_min, self.y_min, self.x_max, self.y_max)


def _objects(values: tuple) -> tuple:
    from .object import SceneObject2D

    if not values:
        raise ValueError("layout requires at least one object")
    if any(not isinstance(obj, SceneObject2D) for obj in values):
        raise TypeError("layout objects must be SceneObject2D instances")
    return values


def _target_transform(obj, center: Vec2) -> Transform2D:
    delta = center - obj.bounds().center
    return Transform2D.translation(delta.x, delta.y) @ obj.transform


def _translated_bounds(obj, center: Vec2):
    from .bounds import Bounds2D

    bounds = obj.bounds()
    half_w, half_h = bounds.width * 0.5, bounds.height * 0.5
    return Bounds2D(center.x - half_w, center.y - half_h, center.x + half_w, center.y + half_h)


def _place_block(
    objects: tuple,
    centers: tuple[Vec2, ...],
    *,
    anchor: Anchor | Vec2,
    at: Point2,
) -> tuple[Vec2, ...]:
    from .bounds import Bounds2D

    at = as_vec2(at, name="at")
    bounds = Bounds2D.union(
        *(_translated_bounds(obj, center) for obj, center in zip(objects, centers))
    )
    a = _anchor(anchor)
    block_anchor = Vec2(
        bounds.center.x + a.x * bounds.width * 0.5,
        bounds.center.y + a.y * bounds.height * 0.5,
    )
    delta = at - block_anchor
    return tuple(center + delta for center in centers)


class Layout2D(Protocol):
    def targets(self, *objects) -> tuple[Transform2D, ...]: ...
    def place(self, *objects) -> tuple: ...


class _LayoutBase:
    def _centers(self, objects: tuple) -> tuple[Vec2, ...]:
        raise NotImplementedError

    def targets(self, *objects) -> tuple[Transform2D, ...]:
        items = _objects(tuple(objects))
        centers = self._centers(items)
        return tuple(_target_transform(obj, center) for obj, center in zip(items, centers))

    def place(self, *objects) -> tuple:
        items = _objects(tuple(objects))
        for obj in items:
            obj._require_layout_mutable()
        for obj, target in zip(items, self.targets(*items)):
            obj.transform = target
        return items


@dataclass(frozen=True, slots=True)
class Row(_LayoutBase):
    """A one-time or animated left-to-right layout specification."""

    gap: float = 0.25
    anchor: Anchor | Vec2 = CENTER
    at: Point2 = Vec2()
    align: Anchor | Vec2 = CENTER

    def _centers(self, objects: tuple) -> tuple[Vec2, ...]:
        gap = float(self.gap)
        if gap < 0:
            raise ValueError("row gap must be >= 0")
        cross = _anchor(self.align).y
        widths = tuple(obj.bounds().width for obj in objects)
        total = sum(widths) + gap * (len(objects) - 1)
        cursor = -total * 0.5
        centers = []
        for obj, width in zip(objects, widths):
            centers.append(Vec2(cursor + width * 0.5, -cross * obj.bounds().height * 0.5))
            cursor += width + gap
        return _place_block(objects, tuple(centers), anchor=self.anchor, at=self.at)


@dataclass(frozen=True, slots=True)
class Column(_LayoutBase):
    """A one-time or animated top-to-bottom layout specification."""

    gap: float = 0.25
    anchor: Anchor | Vec2 = CENTER
    at: Point2 = Vec2()
    align: Anchor | Vec2 = CENTER

    def _centers(self, objects: tuple) -> tuple[Vec2, ...]:
        gap = float(self.gap)
        if gap < 0:
            raise ValueError("column gap must be >= 0")
        cross = _anchor(self.align).x
        heights = tuple(obj.bounds().height for obj in objects)
        total = sum(heights) + gap * (len(objects) - 1)
        cursor = total * 0.5
        centers = []
        for obj, height in zip(objects, heights):
            centers.append(Vec2(-cross * obj.bounds().width * 0.5, cursor - height * 0.5))
            cursor -= height + gap
        return _place_block(objects, tuple(centers), anchor=self.anchor, at=self.at)


@dataclass(frozen=True, slots=True)
class Grid(_LayoutBase):
    """A one-time or animated equal-cell grid layout specification."""

    rows: int | None = None
    cols: int | None = None
    gap: float | Vec2 = 0.25
    anchor: Anchor | Vec2 = CENTER
    at: Point2 = Vec2()

    def _centers(self, objects: tuple) -> tuple[Vec2, ...]:
        count = len(objects)
        rows, cols = self.rows, self.cols
        if rows is None and cols is None:
            cols = int(ceil(count**0.5))
        if cols is None:
            if rows is None or rows <= 0:
                raise ValueError("rows must be positive")
            cols = int(ceil(count / rows))
        if rows is None:
            if cols <= 0:
                raise ValueError("cols must be positive")
            rows = int(ceil(count / cols))
        if rows <= 0 or cols <= 0 or rows * cols < count:
            raise ValueError("grid dimensions cannot contain all objects")

        if isinstance(self.gap, Vec2):
            gap_x, gap_y = self.gap.x, self.gap.y
        else:
            gap_x = gap_y = float(self.gap)
        if gap_x < 0 or gap_y < 0:
            raise ValueError("grid gap must be >= 0")

        cell_w = max(obj.bounds().width for obj in objects)
        cell_h = max(obj.bounds().height for obj in objects)
        total_w = cols * cell_w + (cols - 1) * gap_x
        total_h = rows * cell_h + (rows - 1) * gap_y
        centers = []
        for index, _obj in enumerate(objects):
            row, col = divmod(index, cols)
            centers.append(
                Vec2(
                    -total_w * 0.5 + cell_w * 0.5 + col * (cell_w + gap_x),
                    total_h * 0.5 - cell_h * 0.5 - row * (cell_h + gap_y),
                )
            )
        return _place_block(objects, tuple(centers), anchor=self.anchor, at=self.at)
