from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil

from .object import SceneObject2D
from .space import SE2, Transform2D, Vec2


@dataclass(slots=True, init=False)
class Group2D(SceneObject2D):
    """Lightweight authoring container.

    Groups own no renderer payload. A group's transform is rigorously the
    local-to-parent frame transform. Nested groups therefore compose exactly as
    a scene graph / open-chain forward-kinematics tree. Scene registration keeps
    the hierarchy to compose transforms/opacity/z-index into leaf snapshots.
    """

    children: list[SceneObject2D]
    transform: Transform2D
    opacity: float
    z_index: int

    def __init__(
        self,
        children: list[SceneObject2D] | None = None,
        transform: Transform2D | SE2 | None = None,
        opacity: float = 1.0,
        z_index: int = 0,
        *,
        position: Vec2 | tuple[float, float] | None = None,
        rotation: float | None = None,
        scale: float | tuple[float, float] | None = None,
        shear: Vec2 | tuple[float, float] | None = None,
    ) -> None:
        from .space import affine2d

        transform_sugar = any(value is not None for value in (position, rotation, scale, shear))
        if transform is not None and transform_sugar:
            raise ValueError(
                "Group2D accepts either transform= or position/rotation/scale/shear sugar, not both"
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

        self.children = [] if children is None else children
        self.transform = resolved_transform
        self.opacity = float(opacity)
        self.z_index = int(z_index)
        self._validate_scene_state()
        if any(not isinstance(child, SceneObject2D) for child in self.children):
            raise TypeError("Group2D children must be SceneObject2D instances")

    def add(self, *children: SceneObject2D) -> "Group2D":
        self._require_layout_mutable()
        for child in children:
            if not isinstance(child, SceneObject2D):
                raise TypeError("Group2D children must be SceneObject2D instances")
            if child is self:
                raise ValueError("Group2D cannot contain itself")
            self.children.append(child)
        return self

    def __iter__(self):
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    def __getitem__(self, index):
        return self.children[index]

    def arrange(self, direction: Vec2 = Vec2(1, 0), *, buff: float = 0.25, center: bool = True) -> "Group2D":
        if not self.children:
            return self
        original_center = self.bounds().center
        for previous, child in zip(self.children, self.children[1:]):
            child.next_to(previous, direction, buff)
            # Keep rows/columns visually aligned on the orthogonal center axis.
            if abs(direction.x) >= abs(direction.y):
                child.shift(0.0, previous.bounds().center.y - child.bounds().center.y)
            else:
                child.shift(previous.bounds().center.x - child.bounds().center.x, 0.0)
        if center:
            new_center = self.bounds().center
            delta = Vec2(original_center.x - new_center.x, original_center.y - new_center.y)
            for child in self.children:
                child.shift(delta)
        return self

    def arrange_in_grid(
        self,
        *,
        rows: int | None = None,
        cols: int | None = None,
        buff_x: float = 0.25,
        buff_y: float = 0.25,
    ) -> "Group2D":
        count = len(self.children)
        if count == 0:
            return self
        if rows is None and cols is None:
            cols = int(ceil(count ** 0.5))
        if cols is None:
            if rows is None or rows <= 0:
                raise ValueError("rows must be positive")
            cols = int(ceil(count / rows))
        if rows is None:
            if cols <= 0:
                raise ValueError("cols must be positive")
            rows = int(ceil(count / cols))
        if rows <= 0 or cols <= 0 or rows * cols < count:
            raise ValueError("grid dimensions cannot contain all children")
        if buff_x < 0 or buff_y < 0:
            raise ValueError("grid buffers must be >= 0")

        center = self.bounds().center
        cell_w = max(child.bounds().width for child in self.children)
        cell_h = max(child.bounds().height for child in self.children)
        total_w = cols * cell_w + (cols - 1) * buff_x
        total_h = rows * cell_h + (rows - 1) * buff_y
        for index, child in enumerate(self.children):
            row, col = divmod(index, cols)
            target = Vec2(
                center.x - total_w * 0.5 + cell_w * 0.5 + col * (cell_w + buff_x),
                center.y + total_h * 0.5 - cell_h * 0.5 - row * (cell_h + buff_y),
            )
            child.move_to(target)
        return self
