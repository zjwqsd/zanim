from __future__ import annotations

from dataclasses import dataclass

from .geometry import Object2D
from .snapshot import ObjectSnapshot


@dataclass(frozen=True, slots=True)
class ObjectInterpolation:
    """A value relationship between two distinct object snapshots.

    Sampling/rendering the relationship never mutates either endpoint.
    """

    source: ObjectSnapshot
    target: ObjectSnapshot

    @staticmethod
    def from_objects(source: Object2D, target: Object2D) -> "ObjectInterpolation":
        return ObjectInterpolation(
            source=ObjectSnapshot.from_object(source),
            target=ObjectSnapshot.from_object(target),
        )
