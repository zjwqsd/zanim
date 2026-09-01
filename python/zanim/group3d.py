from __future__ import annotations

from dataclasses import dataclass, field

from .mesh3d import MeshObject3D
from .space3d import SE3, Transform3D, Vec3


@dataclass(slots=True, init=False)
class Group3D:
    """Hierarchical 3D transform/opacity node with no renderer payload.

    Group3D mirrors the role of :class:`Group` in 2D: child meshes keep their
    own local geometry/pose while the group supplies a shared local-to-parent
    transform. Nested groups therefore form an explicit 3D scene graph useful
    for articulated assemblies, robots, and compound objects.
    """

    _children: list[MeshObject3D | "Group3D"]
    transform: Transform3D
    opacity: float
    _zanim_scene_registered: bool = field(default=False, init=False, repr=False)

    def __init__(
        self,
        children: list[MeshObject3D | "Group3D"] | None = None,
        transform: Transform3D | SE3 | None = None,
        opacity: float = 1.0,
        *,
        position: Vec3 | tuple[float, float, float] | None = None,
    ) -> None:
        if transform is not None and position is not None:
            raise ValueError("Group3D accepts either transform= or position=, not both")
        if transform is None:
            if position is None:
                resolved = Transform3D()
            else:
                p = position if isinstance(position, Vec3) else Vec3(*map(float, position))
                resolved = Transform3D.translation(p.x, p.y, p.z)
        elif isinstance(transform, SE3):
            resolved = transform.as_affine()
        elif isinstance(transform, Transform3D):
            resolved = transform
        else:
            raise TypeError("Group3D transform must be Transform3D or SE3")
        value = float(opacity)
        if not 0.0 <= value <= 1.0:
            raise ValueError("Group3D opacity must be in [0, 1]")
        values = [] if children is None else list(children)
        if any(not isinstance(child, (MeshObject3D, Group3D)) for child in values):
            raise TypeError("Group3D children must be MeshObject3D or Group3D")
        if any(child is self for child in values):
            raise ValueError("Group3D cannot contain itself")
        self._children = values
        self.transform = resolved
        self.opacity = value
        self._zanim_scene_registered = False

    def __setattr__(self, name: str, value) -> None:
        if not name.startswith("_") and getattr(self, "_zanim_scene_registered", False):
            raise RuntimeError(
                f"cannot assign {name!r} after Scene.add(); use a Scene timeline operation"
            )
        object.__setattr__(self, name, value)

    def _mark_scene_registered(self) -> None:
        object.__setattr__(self, "_zanim_scene_registered", True)

    def _set_scene_state(self, name: str, value) -> None:
        object.__setattr__(self, name, value)

    @property
    def children(self) -> tuple[MeshObject3D | "Group3D", ...]:
        return tuple(self._children)

    def add(self, *children: MeshObject3D | "Group3D") -> "Group3D":
        if self._zanim_scene_registered:
            raise RuntimeError("cannot modify Group3D hierarchy after Scene.add()")
        for child in children:
            if not isinstance(child, (MeshObject3D, Group3D)):
                raise TypeError("Group3D children must be MeshObject3D or Group3D")
            if child is self:
                raise ValueError("Group3D cannot contain itself")
            self._children.append(child)
        return self

    def __iter__(self):
        return iter(self._children)

    def __len__(self) -> int:
        return len(self._children)

    def __getitem__(self, index):
        return self._children[index]
