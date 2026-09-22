from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .object import SceneObject2D
from .space import SE2, Transform2D, Vec2


@dataclass(slots=True, init=False)
class Group(SceneObject2D):
    """Lightweight authoring container.

    Groups own no renderer payload. A group's transform is rigorously the
    local-to-parent frame transform. Nested groups therefore compose exactly as
    a scene graph / open-chain forward-kinematics tree. Scene registration keeps
    the hierarchy to compose transforms/opacity/z-index into leaf snapshots.
    """

    _children: list[SceneObject2D]
    transform: Transform2D
    opacity: float
    z_index: int

    def __init__(
        self,
        children: Sequence[SceneObject2D] | None = None,
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
                "Group accepts either transform= or position/rotation/scale/shear sugar, not both"
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

        self._children = [] if children is None else list(children)
        self.transform = resolved_transform
        self.opacity = float(opacity)
        self.z_index = int(z_index)
        self._validate_scene_state()
        if any(not isinstance(child, SceneObject2D) for child in self._children):
            raise TypeError("Group children must be SceneObject2D instances")

    @property
    def children(self) -> tuple[SceneObject2D, ...]:
        """Direct children in stable order; hierarchy is immutable after Scene.add()."""
        return tuple(self._children)

    def add(self, *children: SceneObject2D) -> "Group":
        self._require_layout_mutable()
        for child in children:
            if not isinstance(child, SceneObject2D):
                raise TypeError("Group children must be SceneObject2D instances")
            if child is self:
                raise ValueError("Group cannot contain itself")
            self._children.append(child)
        return self

    def __iter__(self):
        return iter(self._children)

    def __len__(self) -> int:
        return len(self._children)

    def __getitem__(self, index):
        return self._children[index]
