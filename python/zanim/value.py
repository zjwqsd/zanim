from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .scene import Scene


@dataclass(slots=True)
class ScalarValue:
    """Scalar source whose timeline state is owned by Scene after registration."""

    value: float
    _initial: float = field(init=False, repr=False)
    _scene: "Scene | None" = field(default=None, init=False, repr=False, compare=False)
    _zanim_scene_registered: bool = field(default=False, init=False, repr=False)

    def __setattr__(self, name: str, value) -> None:
        if not name.startswith("_") and getattr(self, "_zanim_scene_registered", False):
            raise RuntimeError(
                f"cannot assign {name!r} after Scene.add(); animate the bound value handle"
            )
        object.__setattr__(self, name, value)

    def __post_init__(self) -> None:
        self.value = float(self.value)
        self._initial = self.value

    def _mark_scene_registered(self) -> None:
        object.__setattr__(self, "_zanim_scene_registered", True)

    def _bind_scene(self, scene: "Scene") -> None:
        if self._scene is not None and self._scene is not scene:
            raise ValueError("ScalarValue is already bound to a different Scene")
        object.__setattr__(self, "_scene", scene)

    def value_at(self, time: float) -> float:
        if self._scene is None:
            return self._initial
        return self._scene.value_at(self, time)
