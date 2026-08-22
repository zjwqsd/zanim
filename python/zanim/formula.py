from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Callable, Mapping, Sequence

from .batch import BatchObject2D
from .dynamic import DynamicNumber, NumberFormat
from .geometry import Color, Object2D
from .space import Transform2D
from .vector import VectorObject2D

SceneObject = Object2D | BatchObject2D | VectorObject2D
ValueProvider = Callable[[float], Real]
MatrixProvider = Callable[[float], Sequence[Sequence[Real]]]


def _provider(value):
    from .value import ScalarValue

    if isinstance(value, ScalarValue):
        return value.value_at
    if callable(value):
        return value
    return lambda _time, value=value: value


class FormulaItem:
    """Marker base for compile-time formula template items."""


@dataclass(frozen=True, slots=True)
class FormulaLiteral(FormulaItem):
    source: str
    font_size: float = 44.0
    color: Color = Color(240, 242, 248)


@dataclass(frozen=True, slots=True)
class NumberSlot(FormulaItem):
    name: str
    number_format: NumberFormat
    font_size: float = 44.0
    color: Color = Color(240, 242, 248)
    padding_x: float = 0.04
    padding_y: float = 0.02
    align: str = "right"


@dataclass(frozen=True, slots=True)
class ScriptSlots(FormulaItem):
    """Typst math base with fixed dynamic subscript/superscript slots."""

    base: str
    sub: NumberSlot
    sup: NumberSlot

    def __post_init__(self) -> None:
        if not self.base.strip():
            raise ValueError("ScriptSlots base must not be empty")
        if self.sub.name == self.sup.name:
            raise ValueError("ScriptSlots sub/sup slot names must be distinct")


@dataclass(frozen=True, slots=True)
class ObjectSlot(FormulaItem):
    """Fixed Typst-laid-out viewport for an arbitrary Zanim object."""

    name: str
    box_width: float
    box_height: float
    padding: float = 0.05
    math_class: str = "normal"

    def __post_init__(self) -> None:
        if self.box_width <= 0 or self.box_height <= 0:
            raise ValueError("ObjectSlot dimensions must be positive")
        if self.padding < 0 or self.padding * 2 >= min(self.box_width, self.box_height):
            raise ValueError("invalid ObjectSlot padding")
        if self.math_class not in {
            "normal",
            "punctuation",
            "opening",
            "closing",
            "fence",
            "large",
            "relation",
            "unary",
            "binary",
            "vary",
        }:
            raise ValueError("invalid Typst math class for ObjectSlot")


@dataclass(frozen=True, slots=True)
class MatrixSlot(FormulaItem):
    name: str
    rows: int
    cols: int
    number_format: NumberFormat
    font_size: float = 44.0
    color: Color = Color(240, 242, 248)
    align: str = "center"
    delim: str = "["
    row_gap: str = "0.2em"
    column_gap: str = "0.5em"

    def __post_init__(self) -> None:
        if self.rows <= 0 or self.cols <= 0:
            raise ValueError("matrix dimensions must be positive")

    def _validate_matrix(self, value) -> None:
        if not isinstance(value, Sequence) or len(value) != self.rows:
            raise ValueError(f"matrix slot {self.name!r} requires {self.rows} rows")
        for row in value:
            if not isinstance(row, Sequence) or len(row) != self.cols:
                raise ValueError(f"matrix slot {self.name!r} requires {self.cols} columns")


@dataclass(frozen=True, slots=True)
class FormulaInstance:
    objects: tuple[SceneObject, ...]
    slots: Mapping[str, tuple[SceneObject, ...]]
    width: float
    height: float


class FormulaTemplate:
    """Compile-once Typst formula skeleton with fixed dynamic slots."""

    def __init__(
        self,
        *items: FormulaItem,
        gap: float = 0.0,
        font_size: float | None = None,
        color: Color = Color(240, 242, 248),
    ) -> None:
        if not items:
            raise ValueError("FormulaTemplate requires at least one item")
        if gap < 0:
            raise ValueError("formula gap must be >= 0")

        self.items = tuple(items)
        self.gap = float(gap)
        self.font_size = float(
            font_size
            if font_size is not None
            else max((getattr(item, "font_size", 44.0) for item in items), default=44.0)
        )
        self.color = color
        self._validate_slot_names()

        from ._formula_layout import compile_formula_layout

        self.layout = compile_formula_layout(
            self.items,
            gap=self.gap,
            font_size=self.font_size,
            color=self.color,
        )
        # Compatibility/readability aliases: these are immutable products of
        # the compiled layout, not authoring state.
        self.document = self.layout.document
        self.width = self.layout.width
        self.height = self.layout.height

    def _validate_slot_names(self) -> None:
        names: list[str] = []
        for item in self.items:
            if isinstance(item, ScriptSlots):
                names.extend((item.sub.name, item.sup.name))
            else:
                name = getattr(item, "name", None)
                if name is not None:
                    names.append(name)
        if len(names) != len(set(names)):
            raise ValueError("duplicate formula slot name")

    def mount(
        self,
        scene,
        bindings: Mapping[str, object],
        *,
        transform: Transform2D = Transform2D(),
    ) -> FormulaInstance:
        from ._formula_layout import object_size

        all_objects: list[SceneObject] = []
        slots: dict[str, tuple[SceneObject, ...]] = {}

        skeleton = VectorObject2D(self.layout.document, transform=transform)
        scene.add(skeleton)
        all_objects.append(skeleton)

        for item_index, item in enumerate(self.items):
            if isinstance(item, FormulaLiteral):
                continue
            boxes = self.layout.boxes_for(item_index)
            mounted: list[SceneObject] = []

            if isinstance(item, NumberSlot):
                mounted.append(self._mount_number(scene, item, boxes[0], bindings, transform))
                slots[item.name] = tuple(mounted)

            elif isinstance(item, MatrixSlot):
                if item.name not in bindings:
                    raise KeyError(f"missing FormulaTemplate binding: {item.name}")
                provider = _provider(bindings[item.name])
                item._validate_matrix(provider(0.0))
                for box in boxes:
                    row, col = divmod(box.cell_index, item.cols)

                    def cell_provider(t: float, row=row, col=col, provider=provider, item=item):
                        matrix = provider(t)
                        item._validate_matrix(matrix)
                        return matrix[row][col]

                    mounted.append(
                        DynamicNumber(
                            cell_provider,
                            number_format=item.number_format,
                            font_size=item.font_size,
                            color=item.color,
                            align=item.align,
                            transform=transform
                            @ Transform2D.translation(box.center_x, box.center_y),
                        )
                    )
                scene.add(*mounted)
                slots[item.name] = tuple(mounted)

            elif isinstance(item, ScriptSlots):
                for box, slot in zip(boxes, (item.sub, item.sup)):
                    obj = self._mount_number(scene, slot, box, bindings, transform)
                    mounted.append(obj)
                    slots[slot.name] = (obj,)

            elif isinstance(item, ObjectSlot):
                if item.name not in bindings:
                    raise KeyError(f"missing FormulaTemplate binding: {item.name}")
                obj = bindings[item.name]
                if not isinstance(obj, (Object2D, BatchObject2D, VectorObject2D)):
                    raise TypeError("ObjectSlot accepts Object2D, BatchObject2D, or VectorObject2D")
                if obj.transform != Transform2D():
                    raise ValueError(
                        "ObjectSlot currently requires bound object transform to be identity"
                    )
                width, height = object_size(obj)
                if width <= 1e-12 or height <= 1e-12:
                    raise ValueError("ObjectSlot cannot fit a zero-size object")
                box = boxes[0]
                inner_width = box.width - 2 * item.padding
                inner_height = box.height - 2 * item.padding
                scale = min(inner_width / width, inner_height / height)
                obj.transform = (
                    transform
                    @ Transform2D.translation(box.center_x, box.center_y)
                    @ Transform2D.scaling(scale)
                )
                scene.add(obj)
                mounted.append(obj)
                slots[item.name] = tuple(mounted)

            else:
                raise TypeError(f"unsupported FormulaItem: {type(item).__name__}")

            all_objects.extend(mounted)

        return FormulaInstance(tuple(all_objects), slots, self.width, self.height)

    @staticmethod
    def _mount_number(
        scene, slot: NumberSlot, box, bindings, transform: Transform2D
    ) -> DynamicNumber:
        if slot.name not in bindings:
            raise KeyError(f"missing FormulaTemplate binding: {slot.name}")
        provider = _provider(bindings[slot.name])
        obj = DynamicNumber(
            lambda t, provider=provider: provider(t),
            number_format=slot.number_format,
            font_size=slot.font_size,
            color=slot.color,
            align=slot.align,
            transform=transform @ Transform2D.translation(box.center_x, box.center_y),
        )
        scene.add(obj)
        return obj
