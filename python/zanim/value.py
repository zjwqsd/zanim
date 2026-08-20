from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .timeline import ValueClip


@dataclass(slots=True)
class ScalarValue:
    """Random-access scalar animation source managed by Scene/Timeline."""

    value: float
    _initial: float = field(init=False, repr=False)
    _clips: list["ValueClip"] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.value = float(self.value)
        self._initial = self.value

    def value_at(self, time: float) -> float:
        if not self._clips:
            return self._initial
        if time < self._clips[0].span.start:
            return self._clips[0].before
        result = self._initial
        for clip in self._clips:
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                result = clip.after
                continue
            return clip.sample(time)
        return result
