from __future__ import annotations

from dataclasses import dataclass

from .batch import BatchObject2D, CircleSet, LineSet, RectSet
from .dynamic import number_metrics
from .geometry import (
    ArcGeometry,
    CircleGeometry,
    Color,
    CubicBezierGeometry,
    EllipseGeometry,
    LineGeometry,
    Object2D,
    PolygonGeometry,
    PolylineGeometry,
    RectangleGeometry,
    RegularPolygonGeometry,
    SquareGeometry,
)
from .svg import load_svg
from .typst import compile_typst_svg
from .vector import VectorDocument, VectorObject2D, VectorPath, vector_path_bounds

SceneObject = Object2D | BatchObject2D | VectorObject2D


@dataclass(frozen=True, slots=True)
class SlotBox:
    item_index: int
    cell_index: int
    center_x: float
    center_y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class CompiledFormulaLayout:
    document: VectorDocument
    boxes: tuple[SlotBox, ...]
    width: float
    height: float

    def boxes_for(self, item_index: int) -> tuple[SlotBox, ...]:
        return tuple(
            sorted(
                (box for box in self.boxes if box.item_index == item_index),
                key=lambda box: box.cell_index,
            )
        )


def _hex(color: Color) -> str:
    return f"#{color.r:02x}{color.g:02x}{color.b:02x}{color.a:02x}"


def _marker_color(index: int) -> Color:
    # Compile-time-only tags chosen to be unlikely to collide with formula
    # colors. They are removed from the imported VectorDocument.
    return Color(
        17 + (index * 73) % 220,
        19 + (index * 97) % 218,
        23 + (index * 131) % 214,
    )


def _box_source(width: float, height: float, color: Color, *, baseline: str = "auto") -> str:
    return (
        f"#box(width: {width * 72:.8f}pt, height: {height * 72:.8f}pt, "
        f'baseline: {baseline}, fill: rgb("{_hex(color)}"))'
    )


def _number_box(slot, color: Color) -> str:
    width, height = number_metrics(
        slot.number_format,
        font_size=slot.font_size,
        color=slot.color,
    )
    width += 2 * slot.padding_x
    height += 2 * slot.padding_y
    return _box_source(width, height, color)


def compile_formula_layout(
    items, *, gap: float, font_size: float, color: Color
) -> CompiledFormulaLayout:
    """Let Typst lay out the whole formula, then recover fixed slot boxes.

    FormulaTemplate does not implement mathematical spacing itself. Colored
    marker boxes survive into SVG, where their exact bounds are measured and
    then removed from the static vector skeleton.
    """
    from .formula import FormulaLiteral, MatrixSlot, NumberSlot, ObjectSlot, ScriptSlots

    fragments: list[str] = []
    marker_specs: list[tuple[int, int, Color]] = []
    marker_index = 0

    def marker(item_index: int, cell_index: int) -> Color:
        nonlocal marker_index
        tag = _marker_color(marker_index)
        marker_index += 1
        marker_specs.append((item_index, cell_index, tag))
        return tag

    for item_index, item in enumerate(items):
        if isinstance(item, FormulaLiteral):
            fragments.append(item.source)
            continue

        if isinstance(item, NumberSlot):
            fragments.append(_number_box(item, marker(item_index, 0)))
            continue

        if isinstance(item, ScriptSlots):
            sub = _number_box(item.sub, marker(item_index, 0))
            sup = _number_box(item.sup, marker(item_index, 1))
            fragments.append(f"{item.base}_({sub})^({sup})")
            continue

        if isinstance(item, ObjectSlot):
            tag = marker(item_index, 0)
            box = _box_source(item.box_width, item.box_height, tag, baseline="50%")
            if item.math_class != "normal":
                box = f'#math.class("{item.math_class}", {box[1:]})'
            fragments.append(box)
            continue

        if isinstance(item, MatrixSlot):
            width, height = number_metrics(
                item.number_format,
                font_size=item.font_size,
                color=item.color,
            )
            cells = [
                _box_source(width, height, marker(item_index, cell_index))[1:]
                for cell_index in range(item.rows * item.cols)
            ]
            rows = [
                "(" + ", ".join(cells[row * item.cols : (row + 1) * item.cols]) + ")"
                for row in range(item.rows)
            ]
            fragments.append(
                f'#math.mat({", ".join(rows)}, delim: "{item.delim}", '
                f"row-gap: {item.row_gap}, column-gap: {item.column_gap})"
            )
            continue

        raise TypeError(f"unsupported FormulaItem: {type(item).__name__}")

    spacer = "" if gap == 0 else f" #h({gap * 72:.8f}pt) "
    equation = spacer.join(fragments)
    source = (
        "#set page(width: auto, height: auto, margin: 0pt, fill: none)\n"
        f'#set text(size: {font_size}pt, fill: rgb("{_hex(color)}"))\n'
        f"$ {equation} $\n"
    )
    imported = load_svg(compile_typst_svg(source))

    marker_colors = {tag for _, _, tag in marker_specs}
    marker_paths: dict[Color, list[VectorPath]] = {tag: [] for tag in marker_colors}
    static_paths: list[VectorPath] = []
    for path in imported.paths:
        if path.fill in marker_paths:
            marker_paths[path.fill].append(path)  # type: ignore[index]
        else:
            static_paths.append(path)

    boxes: list[SlotBox] = []
    for item_index, cell_index, tag in marker_specs:
        paths = marker_paths[tag]
        if not paths:
            raise RuntimeError("Typst formula slot marker was not found in SVG output")
        left = min(vector_path_bounds(path)[0] for path in paths)
        bottom = min(vector_path_bounds(path)[1] for path in paths)
        right = max(vector_path_bounds(path)[2] for path in paths)
        top = max(vector_path_bounds(path)[3] for path in paths)
        boxes.append(
            SlotBox(
                item_index,
                cell_index,
                (left + right) / 2,
                (bottom + top) / 2,
                right - left,
                top - bottom,
            )
        )

    document = VectorDocument(
        tuple(static_paths),
        imported.width,
        imported.height,
        imported.group_count if static_paths else 0,
    )
    return CompiledFormulaLayout(document, tuple(boxes), imported.width, imported.height)


def object_size(obj: SceneObject) -> tuple[float, float]:
    """Natural local bounds used to contain an object in ObjectSlot."""
    if isinstance(obj, VectorObject2D):
        return obj.document.width, obj.document.height

    if isinstance(obj, BatchObject2D):
        batch = obj.batch
        if isinstance(batch, LineSet):
            points = [point for pair in zip(batch.starts, batch.ends) for point in pair]
            xs = [point.x for point in points]
            ys = [point.y for point in points]
            return max(xs) - min(xs), max(ys) - min(ys)
        if isinstance(batch, CircleSet):
            left = min(center.x - radius for center, radius in zip(batch.centers, batch.radii))
            right = max(center.x + radius for center, radius in zip(batch.centers, batch.radii))
            bottom = min(center.y - radius for center, radius in zip(batch.centers, batch.radii))
            top = max(center.y + radius for center, radius in zip(batch.centers, batch.radii))
            return right - left, top - bottom
        if isinstance(batch, RectSet):
            left = min(center.x - size.x / 2 for center, size in zip(batch.centers, batch.sizes))
            right = max(center.x + size.x / 2 for center, size in zip(batch.centers, batch.sizes))
            bottom = min(center.y - size.y / 2 for center, size in zip(batch.centers, batch.sizes))
            top = max(center.y + size.y / 2 for center, size in zip(batch.centers, batch.sizes))
            return right - left, top - bottom
        raise TypeError(f"unsupported batch object for ObjectSlot: {type(batch).__name__}")

    geometry = obj.geometry
    if isinstance(geometry, RectangleGeometry):
        return geometry.width, geometry.height
    if isinstance(geometry, SquareGeometry):
        return geometry.side, geometry.side
    if isinstance(geometry, CircleGeometry):
        return 2 * geometry.radius, 2 * geometry.radius
    if isinstance(geometry, EllipseGeometry):
        return 2 * geometry.radius_x, 2 * geometry.radius_y
    if isinstance(geometry, ArcGeometry):
        return 2 * geometry.radius, 2 * geometry.radius
    if isinstance(geometry, RegularPolygonGeometry):
        return 2 * geometry.radius, 2 * geometry.radius
    if isinstance(geometry, LineGeometry):
        return abs(geometry.end.x - geometry.start.x), abs(geometry.end.y - geometry.start.y)
    if isinstance(geometry, (PolylineGeometry, PolygonGeometry)):
        xs = [point.x for point in geometry.points]
        ys = [point.y for point in geometry.points]
        return max(xs) - min(xs), max(ys) - min(ys)
    if isinstance(geometry, CubicBezierGeometry):
        points = (geometry.p0, geometry.p1, geometry.p2, geometry.p3)
        xs = [point.x for point in points]
        ys = [point.y for point in points]
        return max(xs) - min(xs), max(ys) - min(ys)
    raise TypeError(f"unsupported object for ObjectSlot: {type(geometry).__name__}")
