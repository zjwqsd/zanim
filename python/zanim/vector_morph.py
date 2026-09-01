from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .geometry import Color, CubicBezierGeometry, StrokeStyle
from .space import Vec2
from .vector import VectorContour, VectorDocument, VectorPath, vector_path_bounds


def _lerp(a: float, b: float, alpha: float) -> float:
    return a + (b - a) * alpha


def _lerp_color(a: Color, b: Color, alpha: float) -> Color:
    return Color(
        round(_lerp(a.r, b.r, alpha)),
        round(_lerp(a.g, b.g, alpha)),
        round(_lerp(a.b, b.b, alpha)),
        round(_lerp(a.a, b.a, alpha)),
    )


def _transparent_like(color: Color) -> Color:
    return Color(color.r, color.g, color.b, 0)


def _lerp_optional_color(a: Color | None, b: Color | None, alpha: float) -> Color | None:
    if a is None and b is None:
        return None
    if a is None:
        assert b is not None
        a = _transparent_like(b)
    if b is None:
        b = _transparent_like(a)
    return _lerp_color(a, b, alpha)


def _lerp_stroke(a: StrokeStyle | None, b: StrokeStyle | None, alpha: float) -> StrokeStyle | None:
    if a is None and b is None:
        return None
    if a is None:
        assert b is not None
        a = StrokeStyle(_transparent_like(b.color), b.width)
    if b is None:
        b = StrokeStyle(_transparent_like(a.color), a.width)
    return StrokeStyle(_lerp_color(a.color, b.color, alpha), _lerp(a.width, b.width, alpha))


def _with_opacity(color: Color | None, opacity: float) -> Color | None:
    if color is None:
        return None
    return Color(color.r, color.g, color.b, round(color.a * max(0.0, min(1.0, opacity))))


def _stroke_with_opacity(stroke: StrokeStyle | None, opacity: float) -> StrokeStyle | None:
    if stroke is None:
        return None
    color = _with_opacity(stroke.color, opacity)
    assert color is not None
    return StrokeStyle(color, stroke.width)


def _group_paths(document: VectorDocument) -> tuple[tuple[VectorPath, ...], ...]:
    groups: list[list[VectorPath]] = [[] for _ in range(document.group_count)]
    for path in document.paths:
        groups[path.group].append(path)
    return tuple(tuple(group) for group in groups)


def _paths_bounds(paths: tuple[VectorPath, ...]) -> tuple[float, float, float, float]:
    if not paths:
        return (0.0, 0.0, 0.0, 0.0)
    bounds = tuple(vector_path_bounds(path) for path in paths)
    return (
        min(value[0] for value in bounds),
        min(value[1] for value in bounds),
        max(value[2] for value in bounds),
        max(value[3] for value in bounds),
    )


def _center(paths: tuple[VectorPath, ...]) -> Vec2:
    left, bottom, right, top = _paths_bounds(paths)
    return Vec2((left + right) * 0.5, (bottom + top) * 0.5)


def _topology(paths: tuple[VectorPath, ...]):
    return tuple(tuple(tuple(len(contour.segments) for contour in path.contours) for path in paths))


def _visual_signature(paths: tuple[VectorPath, ...]):
    """Translation/scale-independent shape key used for Math glyph matching."""
    left, bottom, right, top = _paths_bounds(paths)
    width = max(right - left, 1e-12)
    height = max(top - bottom, 1e-12)
    scale = max(width, height)

    def point_key(point: Vec2) -> tuple[int, int]:
        return (
            round((point.x - left) / scale * 10000),
            round((point.y - bottom) / scale * 10000),
        )

    return (
        round(width / scale * 10000),
        round(height / scale * 10000),
        tuple(
            tuple(
                (
                    contour.closed,
                    tuple(
                        (
                            point_key(segment.p0),
                            point_key(segment.p1),
                            point_key(segment.p2),
                            point_key(segment.p3),
                        )
                        for segment in contour.segments
                    ),
                )
                for contour in path.contours
            )
            for path in paths
        ),
    )


def _relabel(paths: tuple[VectorPath, ...], group: int) -> tuple[VectorPath, ...]:
    return tuple(
        VectorPath(path.contours, fill=path.fill, stroke=path.stroke, group=group) for path in paths
    )


def _lerp_paths(
    source: tuple[VectorPath, ...], target: tuple[VectorPath, ...], alpha: float, group: int
) -> tuple[VectorPath, ...]:
    if _topology(source) != _topology(target):
        raise ValueError("vector groups must share topology for direct interpolation")
    result: list[VectorPath] = []
    for a_path, b_path in zip(source, target):
        contours: list[VectorContour] = []
        for a_contour, b_contour in zip(a_path.contours, b_path.contours):
            segments = tuple(
                CubicBezierGeometry(
                    Vec2(_lerp(a.p0.x, b.p0.x, alpha), _lerp(a.p0.y, b.p0.y, alpha)),
                    Vec2(_lerp(a.p1.x, b.p1.x, alpha), _lerp(a.p1.y, b.p1.y, alpha)),
                    Vec2(_lerp(a.p2.x, b.p2.x, alpha), _lerp(a.p2.y, b.p2.y, alpha)),
                    Vec2(_lerp(a.p3.x, b.p3.x, alpha), _lerp(a.p3.y, b.p3.y, alpha)),
                )
                for a, b in zip(a_contour.segments, b_contour.segments)
            )
            contours.append(VectorContour(segments, a_contour.closed and b_contour.closed))
        result.append(
            VectorPath(
                tuple(contours),
                fill=_lerp_optional_color(a_path.fill, b_path.fill, alpha),
                stroke=_lerp_stroke(a_path.stroke, b_path.stroke, alpha),
                group=group,
            )
        )
    return tuple(result)


def _scale_paths(
    paths: tuple[VectorPath, ...], scale: float, opacity: float, group: int
) -> tuple[VectorPath, ...]:
    origin = _center(paths)

    def point(value: Vec2) -> Vec2:
        return Vec2(
            origin.x + (value.x - origin.x) * scale,
            origin.y + (value.y - origin.y) * scale,
        )

    result: list[VectorPath] = []
    for path in paths:
        contours = tuple(
            VectorContour(
                tuple(
                    CubicBezierGeometry(
                        point(segment.p0),
                        point(segment.p1),
                        point(segment.p2),
                        point(segment.p3),
                    )
                    for segment in contour.segments
                ),
                contour.closed,
            )
            for contour in path.contours
        )
        result.append(
            VectorPath(
                contours,
                fill=_with_opacity(path.fill, opacity),
                stroke=_stroke_with_opacity(path.stroke, opacity),
                group=group,
            )
        )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class VectorMorphPlan:
    """Precomputed glyph correspondence for a VectorDocument transition."""

    source: VectorDocument
    target: VectorDocument
    matched: tuple[tuple[int, int], ...]
    source_only: tuple[int, ...]
    target_only: tuple[int, ...]

    def sample(self, alpha: float) -> VectorDocument:
        alpha = max(0.0, min(1.0, float(alpha)))
        if alpha <= 0.0:
            return self.source
        if alpha >= 1.0:
            return self.target

        source_groups = _group_paths(self.source)
        target_groups = _group_paths(self.target)
        paths: list[VectorPath] = []
        group = 0
        for source_index, target_index in self.matched:
            a = source_groups[source_index]
            b = target_groups[target_index]
            if _topology(a) == _topology(b):
                paths.extend(_lerp_paths(a, b, alpha, group))
            else:
                # Rare fallback (for example a font change with different outlines):
                # keep the glyph-local transition lively without forcing unrelated
                # contour topology into one path.
                paths.extend(_scale_paths(a, 1.0 - 0.35 * alpha, 1.0 - alpha, group))
                group += 1
                paths.extend(_scale_paths(b, 0.65 + 0.35 * alpha, alpha, group))
            group += 1

        for source_index in self.source_only:
            paths.extend(
                _scale_paths(
                    source_groups[source_index],
                    1.0 - 0.45 * alpha,
                    1.0 - alpha,
                    group,
                )
            )
            group += 1
        for target_index in self.target_only:
            paths.extend(
                _scale_paths(
                    target_groups[target_index],
                    0.55 + 0.45 * alpha,
                    alpha,
                    group,
                )
            )
            group += 1

        return VectorDocument(
            tuple(paths),
            _lerp(self.source.width, self.target.width, alpha),
            _lerp(self.source.height, self.target.height, alpha),
            group,
        )


def prepare_vector_morph(
    source: VectorDocument,
    target: VectorDocument,
    *,
    source_keys: tuple[object, ...] | None = None,
    target_keys: tuple[object, ...] | None = None,
) -> VectorMorphPlan:
    """Build stable glyph correspondence, preferring supplied semantic keys."""
    source_groups = _group_paths(source)
    target_groups = _group_paths(target)
    if source_keys is None or len(source_keys) != len(source_groups):
        source_keys = tuple(_visual_signature(group) for group in source_groups)
    if target_keys is None or len(target_keys) != len(target_groups):
        target_keys = tuple(_visual_signature(group) for group in target_groups)

    matcher = SequenceMatcher(a=source_keys, b=target_keys, autojunk=False)
    matched: list[tuple[int, int]] = []
    source_matched: set[int] = set()
    target_matched: set[int] = set()
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            a = block.a + offset
            b = block.b + offset
            matched.append((a, b))
            source_matched.add(a)
            target_matched.add(b)

    return VectorMorphPlan(
        source,
        target,
        tuple(matched),
        tuple(index for index in range(len(source_groups)) if index not in source_matched),
        tuple(index for index in range(len(target_groups)) if index not in target_matched),
    )


def typst_semantic_keys(obj) -> tuple[str, ...] | None:
    """Return one key per visible glyph when Typst source has that exact mapping."""
    from .typst import Text

    if not isinstance(obj, Text):
        return None
    keys = tuple(char for char in obj.content if not char.isspace())
    return keys if len(keys) == obj.document.group_count else None
