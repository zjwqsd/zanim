from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil

from .object import SceneObject2D
from .space import Transform2D, Vec2


@dataclass(slots=True)
class Group2D(SceneObject2D):
    """Lightweight authoring container.

    Groups own no renderer payload. Scene registration keeps the hierarchy only
    long enough to compose transforms/opacity/z-index into leaf snapshots.
    """

    children: list[SceneObject2D] = field(default_factory=list)
    transform: Transform2D = Transform2D()
    opacity: float = 1.0
    z_index: int = 0

    def __post_init__(self) -> None:
        self._validate_scene_state()
        if any(not isinstance(child, SceneObject2D) for child in self.children):
            raise TypeError("Group2D children must be SceneObject2D instances")

    def add(self, *children: SceneObject2D) -> "Group2D":
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
