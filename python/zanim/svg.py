from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from math import radians, tan
from pathlib import Path

from ._svg_path import parse_path_data
from .geometry import Color, CubicBezierGeometry, StrokeStyle
from .space import Transform2D
from .vector import VectorContour, VectorDocument, VectorPath

_TRANSFORM_RE = re.compile(r"([A-Za-z]+)\s*\(([^)]*)\)")
_NUMBER_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _parse_transform(value: str | None) -> Transform2D:
    out = Transform2D()
    if not value:
        return out
    for name, args_text in _TRANSFORM_RE.findall(value):
        args = [float(x) for x in _NUMBER_RE.findall(args_text)]
        if name == "matrix" and len(args) == 6:
            a, b, c, d, e, f = args
            local = Transform2D(a, c, b, d, e, f)
        elif name == "translate" and 1 <= len(args) <= 2:
            local = Transform2D.translation(args[0], args[1] if len(args) > 1 else 0.0)
        elif name == "scale" and 1 <= len(args) <= 2:
            local = Transform2D.scaling(args[0], args[1] if len(args) > 1 else args[0])
        elif name == "rotate" and len(args) in (1, 3):
            rotation = Transform2D.rotation(radians(args[0]))
            if len(args) == 3:
                cx, cy = args[1], args[2]
                local = (
                    Transform2D.translation(cx, cy) @ rotation @ Transform2D.translation(-cx, -cy)
                )
            else:
                local = rotation
        elif name == "skewX" and len(args) == 1:
            local = Transform2D(xy=tan(radians(args[0])))
        elif name == "skewY" and len(args) == 1:
            local = Transform2D(yx=tan(radians(args[0])))
        else:
            raise ValueError(f"unsupported SVG transform {name}({args_text})")
        out = out @ local
    return out


def _apply_transform(
    contours: tuple[VectorContour, ...], transform: Transform2D
) -> tuple[VectorContour, ...]:
    return tuple(
        VectorContour(
            tuple(
                CubicBezierGeometry(
                    transform.apply(segment.p0),
                    transform.apply(segment.p1),
                    transform.apply(segment.p2),
                    transform.apply(segment.p3),
                )
                for segment in contour.segments
            ),
            contour.closed,
        )
        for contour in contours
    )


def _parse_color(value: str | None, default: Color | None) -> Color | None:
    if value is None:
        return default
    value = value.strip().lower()
    if value == "none":
        return None
    if value.startswith("#"):
        hex_value = value[1:]
        if len(hex_value) == 3:
            hex_value = "".join(ch * 2 for ch in hex_value)
        if len(hex_value) == 6:
            return Color(*(int(hex_value[i : i + 2], 16) for i in (0, 2, 4)))
        if len(hex_value) == 8:
            return Color(*(int(hex_value[i : i + 2], 16) for i in (0, 2, 4, 6)))
    if value.startswith("rgb("):
        values = [float(x) for x in _NUMBER_RE.findall(value)]
        if len(values) >= 3:
            return Color(*(max(0, min(255, round(channel))) for channel in values[:3]))
    named = {
        "black": Color(0, 0, 0),
        "white": Color(255, 255, 255),
        "red": Color(255, 0, 0),
        "blue": Color(0, 0, 255),
    }
    if value in named:
        return named[value]
    raise ValueError(f"unsupported SVG color: {value}")


def _style_map(element: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    style = element.get("style")
    if style:
        for part in style.split(";"):
            if ":" in part:
                key, value = part.split(":", 1)
                result[key.strip()] = value.strip()
    for key in ("fill", "fill-opacity", "stroke", "stroke-opacity", "stroke-width", "opacity"):
        if element.get(key) is not None:
            result[key] = element.get(key) or ""
    return result


def _with_alpha(color: Color | None, alpha: float) -> Color | None:
    if color is None:
        return None
    return Color(color.r, color.g, color.b, max(0, min(255, round(color.a * alpha))))


def _length(value: str | None) -> float | None:
    if value is None:
        return None
    match = _NUMBER_RE.search(value)
    return float(match.group()) if match else None


def load_svg(source: str | Path, *, unit_scale: float = 1 / 72.0) -> VectorDocument:
    """Import the useful SVG subset into a centered cubic VectorDocument.

    SVG transforms are flattened during import. The SVG y-down coordinate
    system is converted exactly once into Zanim's y-up local coordinates.
    """
    if isinstance(source, Path) or (isinstance(source, str) and "<svg" not in source):
        root = ET.parse(source).getroot()
    else:
        root = ET.fromstring(str(source))

    view_box = root.get("viewBox")
    if view_box:
        x0, y0, width, height = [float(x) for x in _NUMBER_RE.findall(view_box)[:4]]
    else:
        width = _length(root.get("width"))
        height = _length(root.get("height"))
        if width is None or height is None:
            raise ValueError("SVG requires viewBox or width/height")
        x0 = y0 = 0.0

    id_map = {element.get("id"): element for element in root.iter() if element.get("id")}
    paths: list[VectorPath] = []
    next_group = 0

    def render_element(
        element: ET.Element,
        parent_transform: Transform2D,
        inherited_fill: Color | None,
        inherited_stroke: StrokeStyle | None,
        inherited_opacity: float,
        group_override: int | None = None,
        from_use: bool = False,
    ) -> None:
        nonlocal next_group
        tag = element.tag.split("}")[-1]
        if tag == "defs" and not from_use:
            return

        transform = parent_transform @ _parse_transform(element.get("transform"))
        styles = _style_map(element)
        opacity = inherited_opacity * float(styles.get("opacity", "1") or 1)
        fill = _parse_color(styles.get("fill"), inherited_fill)
        if fill is not None:
            fill = _with_alpha(fill, opacity * float(styles.get("fill-opacity", "1") or 1))

        stroke_color = _parse_color(
            styles.get("stroke"),
            inherited_stroke.color if inherited_stroke else None,
        )
        stroke = None
        if stroke_color is not None:
            width_value = float(
                styles.get("stroke-width", inherited_stroke.width if inherited_stroke else 1.0)
            )
            resolved = _with_alpha(
                stroke_color,
                opacity * float(styles.get("stroke-opacity", "1") or 1),
            )
            assert resolved is not None
            stroke = StrokeStyle(resolved, width_value * unit_scale)

        if tag == "use":
            href = element.get("href") or element.get("{http://www.w3.org/1999/xlink}href")
            if not href or not href.startswith("#") or href[1:] not in id_map:
                return
            x = _length(element.get("x")) or 0.0
            y = _length(element.get("y")) or 0.0
            group = next_group if group_override is None else group_override
            if group_override is None:
                next_group += 1
            render_element(
                id_map[href[1:]],
                transform @ Transform2D.translation(x, y),
                fill,
                stroke,
                opacity,
                group,
                True,
            )
            return

        if tag == "path" and element.get("d"):
            contours = parse_path_data(element.get("d") or "")
            if contours:
                group = next_group if group_override is None else group_override
                if group_override is None:
                    next_group += 1
                paths.append(
                    VectorPath(
                        _apply_transform(contours, transform),
                        fill=fill,
                        stroke=stroke,
                        group=group,
                    )
                )
            return

        if tag in ("svg", "g", "symbol") or from_use:
            for child in element:
                render_element(
                    child,
                    transform,
                    fill,
                    stroke,
                    opacity,
                    group_override,
                    from_use,
                )

    render_element(root, Transform2D(), Color(0, 0, 0), None, 1.0)

    final = Transform2D.scaling(unit_scale, -unit_scale) @ Transform2D.translation(
        -(x0 + width / 2), -(y0 + height / 2)
    )
    paths = [
        VectorPath(
            _apply_transform(path.contours, final),
            path.fill,
            path.stroke,
            path.group,
        )
        for path in paths
    ]
    return VectorDocument(
        tuple(paths),
        width * unit_scale,
        height * unit_scale,
        next_group if paths else 0,
    )


__all__ = ["load_svg", "parse_path_data"]
