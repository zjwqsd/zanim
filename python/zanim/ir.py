"""Portable Zanim Scene IR v1.

The IR is intentionally animation-semantic rather than renderer-specific.  It
contains authored initial state, object lifetime/hierarchy, and deterministic
Timeline clips.  Native Python objects and Web objects are frontends that can
compile to this representation; renderers consume the same values afterwards.

Arbitrary Python/JavaScript callbacks are *not* part of the portable format.
TransformFunctionClip can optionally be baked into a sampled transform track,
and dynamic geometry/batch/vector providers can optionally be baked into sampled
absolute-time tracks.  Sampled tracks remain an explicit export fallback rather
than portable source code.
"""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from pathlib import Path
from typing import Any

from .batch import BatchObject2D, CircleSet, DynamicBatchObject2D, LineSet, RectSet
from .camera import Camera2D
from .errors import ZanimError
from .expression import ScalarExpr
from .fourier import FourierEpicycles, FourierTerm
from .fractal import FractalField2D, JuliaSet, MandelbrotSet
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
    StrokeStyle,
    Style,
)
from .group import Group
from .infinite import ComplexMappedGrid, InfiniteGrid, InfiniteLine, InfiniteObject2D
from .interpolation import ObjectInterpolation
from .plot import DynamicGeometryObject2D, FunctionPlot
from .scene import Scene
from .snapshot import BatchSnapshot, InfiniteSnapshot, NodeSnapshot, ObjectSnapshot, VectorSnapshot
from .space import SE2, Canvas, Transform2D, Vec2
from .timeline import (
    BatchClip,
    Easing,
    InterpolationClip,
    OpacityClip,
    PathTrimClip,
    RevealClip,
    SE2TransformClip,
    StyleClip,
    TimeSpan,
    TransformClip,
    TransformFunctionClip,
    ValueClip,
)
from .value import ScalarValue
from .vector import (
    DynamicVectorObject2D,
    VectorContour,
    VectorDocument,
    VectorObject2D,
    VectorPath,
)

FORMAT = "zanim.scene"
VERSION = 1


class SceneIRUnsupported(ZanimError):
    """Raised when authored behavior cannot be represented portably in IR v1."""


def _vec(v: Vec2) -> list[float]:
    return [float(v.x), float(v.y)]


def _transform(t: Transform2D) -> list[float]:
    return [float(t.xx), float(t.xy), float(t.yx), float(t.yy), float(t.tx), float(t.ty)]


def _transform_from(value) -> Transform2D:
    if not isinstance(value, list) or len(value) != 6:
        raise ValueError("IR transform must contain six numbers")
    return Transform2D(*(float(x) for x in value))


def _color(c: Color | None):
    return None if c is None else [c.r, c.g, c.b, c.a]


def _color_from(value) -> Color | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("IR color must contain RGBA")
    return Color(*(int(v) for v in value))


def _stroke(s: StrokeStyle | None):
    return None if s is None else {"color": _color(s.color), "width": float(s.width)}


def _stroke_from(value) -> StrokeStyle | None:
    if value is None:
        return None
    return StrokeStyle(_color_from(value["color"]), float(value["width"]))  # type: ignore[arg-type]


def _style(s: Style) -> dict[str, Any]:
    return {"fill": _color(s.fill), "stroke": _stroke(s.stroke)}


def _style_from(value) -> Style:
    return Style(fill=_color_from(value.get("fill")), stroke=_stroke_from(value.get("stroke")))


def _geometry(g) -> dict[str, Any]:
    if isinstance(g, LineGeometry):
        return {"kind": "line", "start": _vec(g.start), "end": _vec(g.end)}
    if isinstance(g, PolylineGeometry):
        return {"kind": "polyline", "points": [_vec(p) for p in g.points]}
    if isinstance(g, PolygonGeometry):
        return {"kind": "polygon", "points": [_vec(p) for p in g.points]}
    if isinstance(g, RectangleGeometry):
        return {"kind": "rectangle", "width": g.width, "height": g.height}
    if isinstance(g, SquareGeometry):
        return {"kind": "square", "side": g.side}
    if isinstance(g, CircleGeometry):
        return {"kind": "circle", "radius": g.radius}
    if isinstance(g, EllipseGeometry):
        return {"kind": "ellipse", "radius_x": g.radius_x, "radius_y": g.radius_y}
    if isinstance(g, ArcGeometry):
        return {
            "kind": "arc",
            "radius": g.radius,
            "start_angle": g.start_angle,
            "sweep_angle": g.sweep_angle,
        }
    if isinstance(g, RegularPolygonGeometry):
        return {"kind": "regular_polygon", "sides": g.sides, "radius": g.radius, "phase": g.phase}
    if isinstance(g, CubicBezierGeometry):
        return {
            "kind": "cubic_bezier",
            "points": [_vec(g.p0), _vec(g.p1), _vec(g.p2), _vec(g.p3)],
        }
    raise SceneIRUnsupported(f"unsupported geometry in Scene IR: {type(g).__name__}")


def _geometry_from(value):
    kind = value["kind"]

    def v(p):
        return Vec2(float(p[0]), float(p[1]))

    if kind == "line":
        return LineGeometry(v(value["start"]), v(value["end"]))
    if kind == "polyline":
        return PolylineGeometry(tuple(v(p) for p in value["points"]))
    if kind == "polygon":
        return PolygonGeometry(tuple(v(p) for p in value["points"]))
    if kind == "rectangle":
        return RectangleGeometry(float(value["width"]), float(value["height"]))
    if kind == "square":
        return SquareGeometry(float(value["side"]))
    if kind == "circle":
        return CircleGeometry(float(value["radius"]))
    if kind == "ellipse":
        return EllipseGeometry(float(value["radius_x"]), float(value["radius_y"]))
    if kind == "arc":
        return ArcGeometry(
            float(value["radius"]), float(value["start_angle"]), float(value["sweep_angle"])
        )
    if kind == "regular_polygon":
        return RegularPolygonGeometry(
            int(value["sides"]), float(value["radius"]), float(value["phase"])
        )
    if kind == "cubic_bezier":
        p = [v(x) for x in value["points"]]
        return CubicBezierGeometry(*p)
    raise ValueError(f"unknown IR geometry kind: {kind}")


def _batch(batch) -> dict[str, Any]:
    if isinstance(batch, LineSet):
        return {
            "kind": "lines",
            "starts": [_vec(p) for p in batch.starts],
            "ends": [_vec(p) for p in batch.ends],
            "colors": [_color(c) for c in batch.colors],
            "widths": list(batch.widths),
        }
    if isinstance(batch, CircleSet):
        return {
            "kind": "circles",
            "centers": [_vec(p) for p in batch.centers],
            "radii": list(batch.radii),
            "fills": [_color(c) for c in batch.fills],
            "stroke_colors": None
            if batch.stroke_colors is None
            else [_color(c) for c in batch.stroke_colors],
            "stroke_widths": None if batch.stroke_widths is None else list(batch.stroke_widths),
        }
    if isinstance(batch, RectSet):
        return {
            "kind": "rects",
            "centers": [_vec(p) for p in batch.centers],
            "sizes": [_vec(p) for p in batch.sizes],
            "fills": [_color(c) for c in batch.fills],
            "stroke_colors": None
            if batch.stroke_colors is None
            else [_color(c) for c in batch.stroke_colors],
            "stroke_widths": None if batch.stroke_widths is None else list(batch.stroke_widths),
        }
    raise SceneIRUnsupported(f"unsupported batch in Scene IR: {type(batch).__name__}")


def _batch_from(value):
    kind = value["kind"]

    def v(p):
        return Vec2(float(p[0]), float(p[1]))

    def cs(xs):
        return tuple(_color_from(x) for x in xs)

    if kind == "lines":
        return LineSet(
            tuple(v(p) for p in value["starts"]),
            tuple(v(p) for p in value["ends"]),
            cs(value["colors"]),
            tuple(float(x) for x in value["widths"]),  # type: ignore[arg-type]
        )
    if kind == "circles":
        strokes = value.get("stroke_colors")
        widths = value.get("stroke_widths")
        return CircleSet(
            tuple(v(p) for p in value["centers"]),
            tuple(float(x) for x in value["radii"]),
            cs(value["fills"]),
            None if strokes is None else cs(strokes),
            None if widths is None else tuple(float(x) for x in widths),  # type: ignore[arg-type]
        )
    if kind == "rects":
        strokes = value.get("stroke_colors")
        widths = value.get("stroke_widths")
        return RectSet(
            tuple(v(p) for p in value["centers"]),
            tuple(v(p) for p in value["sizes"]),
            cs(value["fills"]),
            None if strokes is None else cs(strokes),
            None if widths is None else tuple(float(x) for x in widths),  # type: ignore[arg-type]
        )
    raise ValueError(f"unknown IR batch kind: {kind}")


def _vector_document(doc: VectorDocument) -> dict[str, Any]:
    return {
        "width": doc.width,
        "height": doc.height,
        "group_count": doc.group_count,
        "paths": [
            {
                "group": path.group,
                "fill": _color(path.fill),
                "stroke": _stroke(path.stroke),
                "contours": [
                    {
                        "closed": contour.closed,
                        "segments": [
                            [_vec(seg.p0), _vec(seg.p1), _vec(seg.p2), _vec(seg.p3)]
                            for seg in contour.segments
                        ],
                    }
                    for contour in path.contours
                ],
            }
            for path in doc.paths
        ],
    }


def _vector_document_from(value) -> VectorDocument:
    paths = []
    for path in value["paths"]:
        contours = []
        for contour in path["contours"]:
            segments = []
            for raw in contour["segments"]:
                p = [Vec2(float(q[0]), float(q[1])) for q in raw]
                segments.append(CubicBezierGeometry(*p))
            contours.append(VectorContour(tuple(segments), bool(contour["closed"])))
        paths.append(
            VectorPath(
                tuple(contours),
                fill=_color_from(path.get("fill")),
                stroke=_stroke_from(path.get("stroke")),
                group=int(path.get("group", 0)),
            )
        )
    return VectorDocument(
        tuple(paths), float(value["width"]), float(value["height"]), int(value["group_count"])
    )


def _object_snapshot(snapshot: ObjectSnapshot) -> dict[str, Any]:
    return {
        "geometry": _geometry(snapshot.geometry),
        "transform": _transform(snapshot.transform),
        "style": _style(snapshot.style),
        "opacity": snapshot.opacity,
        "z_index": snapshot.z_index,
        "trim": snapshot.trim,
    }


def _object_snapshot_from(value) -> ObjectSnapshot:
    return ObjectSnapshot(
        _geometry_from(value["geometry"]),
        _transform_from(value["transform"]),
        _style_from(value["style"]),
        float(value["opacity"]),
        int(value["z_index"]),
        float(value.get("trim", 1.0)),
    )


def _easing(easing: Easing) -> str:
    return easing.value


def _span(clip) -> dict[str, Any]:
    return {
        "start": clip.span.start,
        "duration": clip.span.duration,
        "easing": _easing(clip.easing),
    }


def _frame_sample_times(start: float, end: float, rate: int) -> list[float]:
    """Return clip/object endpoints plus every global ``frame / rate`` sample inside.

    Using the global video grid, rather than subdividing a span evenly, is what
    makes baked runtime providers exact at every frame rendered by Native Zanim.
    """
    start = float(start)
    end = max(start, float(end))
    times = [start]
    if end <= start + 1e-15:
        return times
    first_frame = math.ceil(start * rate - 1e-12)
    last_frame = math.floor(end * rate + 1e-12)
    for frame in range(first_frame, last_frame + 1):
        time = frame / rate
        if start + 1e-12 < time < end - 1e-12:
            times.append(time)
    if end - times[-1] > 1e-12:
        times.append(end)
    else:
        times[-1] = end
    return times


def _sampled_state(times: list[float], samples: list[Any], rate: int) -> dict[str, Any]:
    start = times[0]
    return {
        "sample_rate": rate,
        "sample_start": start,
        "sample_offsets": [time - start for time in times],
        "samples": samples,
    }


def _sample_lookup(times: tuple[float, ...], samples: tuple[Any, ...], time: float):
    index = bisect_right(times, float(time) + 1e-12) - 1
    return samples[max(0, min(len(samples) - 1, index))]


def _registered_id(scene: Scene, obj) -> int:
    item = scene._by_identity.get(id(obj))
    if item is None:
        raise SceneIRUnsupported(f"IR value reference is not registered: {type(obj).__name__}")
    return item.object_id


def scene_to_ir(
    scene: Scene,
    *,
    sample_transform_functions: bool = False,
    sample_dynamic_providers: bool = False,
    sample_fps: int | None = None,
    include_debug: bool = False,
) -> dict[str, Any]:
    """Compile one Python Scene into portable Scene IR v1.

    ``sample_transform_functions=True`` bakes TransformFunctionClip on the exact
    video frame grid. ``sample_dynamic_providers=True`` does the same for
    DynamicGeometryObject2D, DynamicBatchObject2D and DynamicVectorObject2D.
    Both are explicit export fallbacks, not portable source code.
    """
    if not isinstance(scene, Scene):
        raise TypeError("scene_to_ir requires Scene")
    sample_rate = int(sample_fps or scene.fps)
    if sample_rate <= 0:
        raise ValueError("sample_fps must be positive")

    objects: list[dict[str, Any]] = []
    values: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    resource_ids: dict[int, int] = {}

    def vector_resource(doc: VectorDocument) -> int:
        identity = id(doc)
        existing = resource_ids.get(identity)
        if existing is not None:
            return existing
        rid = len(resources) + 1
        resource_ids[identity] = rid
        resources.append({"id": rid, "kind": "vector_document", "data": _vector_document(doc)})
        return rid

    semantic_fourier_ids = {
        reg.object_id for reg in scene._registry if isinstance(reg.object_ref, FourierEpicycles)
    }
    semantic_child_ids = {
        reg.object_id
        for reg in scene._registry
        if any(parent_id in semantic_fourier_ids for parent_id in reg.parent_ids)
    }

    for reg in scene._registry:
        if reg.object_id in semantic_child_ids:
            continue
        obj, initial = reg.object_ref, reg.initial
        parent = reg.parent_ids[-1] if reg.parent_ids else None
        common = {
            "id": reg.object_id,
            "parent": parent,
            "birth": reg.added_at,
            "death": reg.removed_at,
        }
        if isinstance(obj, Camera2D):
            if obj.is_dynamic:
                raise SceneIRUnsupported("dynamic Camera2D provider is not portable in Scene IR v1")
            assert isinstance(initial, NodeSnapshot)
            objects.append(
                {
                    **common,
                    "kind": "camera2d",
                    "state": {
                        "transform": _transform(initial.transform),
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, FourierEpicycles):
            assert isinstance(initial, NodeSnapshot)
            objects.append(
                {
                    **common,
                    "kind": "fourier_epicycles",
                    "state": {
                        "terms": [
                            [term.frequency, term.coefficient.real, term.coefficient.imag]
                            for term in obj.terms
                        ],
                        "start_time": obj.start_time,
                        "draw_duration": obj.draw_duration,
                        "circle_samples": obj.circle_samples,
                        "trace_samples": obj.trace_samples,
                        "visual_indices": list(obj.visual_indices),
                        "circle_style": _style(obj.circle_style),
                        "arrow_style": _style(obj.arrow_style),
                        "trace_style": _style(obj.trace_style),
                        "tip_style": _style(obj.tip_style),
                        "tip_radius": obj.tip_radius,
                        "tip_sides": obj.tip_sides,
                        "transform": _transform(initial.transform),
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, Group):
            assert isinstance(initial, NodeSnapshot)
            objects.append(
                {
                    **common,
                    "kind": "group",
                    "state": {
                        "transform": _transform(initial.transform),
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, DynamicBatchObject2D):
            if not sample_dynamic_providers:
                raise SceneIRUnsupported(
                    "DynamicBatchObject2D contains runtime code; pass "
                    "sample_dynamic_providers=True to bake it"
                )
            assert isinstance(initial, BatchSnapshot)
            end = min(
                float(reg.removed_at) if reg.removed_at is not None else scene.duration,
                scene.duration,
            )
            times = _frame_sample_times(reg.added_at, max(reg.added_at, end), sample_rate)
            objects.append(
                {
                    **common,
                    "kind": "sampled_batch2d",
                    "state": {
                        **_sampled_state(
                            times, [_batch(obj.batch_at(time)) for time in times], sample_rate
                        ),
                        "transform": _transform(initial.transform),
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, DynamicVectorObject2D):
            if not sample_dynamic_providers:
                raise SceneIRUnsupported(
                    "DynamicVectorObject2D contains runtime code; pass "
                    "sample_dynamic_providers=True to bake it"
                )
            assert isinstance(initial, VectorSnapshot)
            end = min(
                float(reg.removed_at) if reg.removed_at is not None else scene.duration,
                scene.duration,
            )
            times = _frame_sample_times(reg.added_at, max(reg.added_at, end), sample_rate)
            docs = [obj.document_at(time) for time in times]
            objects.append(
                {
                    **common,
                    "kind": "sampled_vector2d",
                    "state": {
                        **_sampled_state(
                            times, [vector_resource(doc) for doc in docs], sample_rate
                        ),
                        "transform": _transform(initial.transform),
                        "reveal": initial.reveal,
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, FunctionPlot):
            assert isinstance(initial, ObjectSnapshot)
            axes = obj.axes
            objects.append(
                {
                    **common,
                    "kind": "function_plot",
                    "state": {
                        "expression": obj.expression.to_data(),
                        "axes": {
                            "x_range": list(axes.x_range),
                            "y_range": list(axes.y_range),
                            "width": axes.width,
                            "height": axes.height,
                            "center": _vec(axes.center),
                        },
                        "x_range": list(obj.x_range),
                        "samples": obj.samples,
                        "transform": _transform(initial.transform),
                        "style": _style(initial.style),
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                        "trim": initial.trim,
                    },
                }
            )
        elif isinstance(obj, DynamicGeometryObject2D):
            if not sample_dynamic_providers:
                raise SceneIRUnsupported(
                    "DynamicGeometryObject2D contains runtime code; pass "
                    "sample_dynamic_providers=True to bake it"
                )
            assert isinstance(initial, ObjectSnapshot)
            end = min(
                float(reg.removed_at) if reg.removed_at is not None else scene.duration,
                scene.duration,
            )
            times = _frame_sample_times(reg.added_at, max(reg.added_at, end), sample_rate)
            objects.append(
                {
                    **common,
                    "kind": "sampled_object2d",
                    "state": {
                        **_sampled_state(
                            times, [_geometry(obj.geometry_at(time)) for time in times], sample_rate
                        ),
                        "transform": _transform(initial.transform),
                        "style": _style(initial.style),
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                        "trim": initial.trim,
                    },
                }
            )
        elif isinstance(obj, Object2D):
            if callable(getattr(obj, "provider", None)):
                raise SceneIRUnsupported(
                    f"{type(obj).__name__} provider is not portable in Scene IR v1"
                )
            assert isinstance(initial, ObjectSnapshot)
            objects.append({**common, "kind": "object2d", "state": _object_snapshot(initial)})
        elif isinstance(obj, BatchObject2D):
            assert isinstance(initial, BatchSnapshot)
            objects.append(
                {
                    **common,
                    "kind": "batch2d",
                    "state": {
                        "batch": _batch(initial.batch),
                        "transform": _transform(initial.transform),
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, VectorObject2D):
            assert isinstance(initial, VectorSnapshot)
            objects.append(
                {
                    **common,
                    "kind": "vector2d",
                    "state": {
                        "resource": vector_resource(initial.document),
                        "transform": _transform(initial.transform),
                        "reveal": initial.reveal,
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, InfiniteLine):
            assert isinstance(initial, InfiniteSnapshot)
            objects.append(
                {
                    **common,
                    "kind": "infinite_line",
                    "state": {
                        "point": [initial.p0, initial.p1],
                        "direction": [initial.p2, initial.p3],
                        "transform": _transform(initial.transform),
                        "color": _color(initial.color),
                        "stroke_width": initial.stroke_width,
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, InfiniteGrid):
            assert isinstance(initial, InfiniteSnapshot)
            objects.append(
                {
                    **common,
                    "kind": "infinite_grid",
                    "state": {
                        "origin": [initial.p0, initial.p1],
                        "step": [initial.p2, initial.p3],
                        "transform": _transform(initial.transform),
                        "color": _color(initial.color),
                        "stroke_width": initial.stroke_width,
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, FractalField2D):
            assert isinstance(initial, InfiniteSnapshot)
            objects.append(
                {
                    **common,
                    "kind": "fractal",
                    "state": {
                        "fractal_kind": obj.fractal_kind,
                        "max_iter": obj.max_iter,
                        "escape_radius": obj.escape_radius,
                        "julia_c": [obj.julia_c.real, obj.julia_c.imag],
                        "inside_color": _color(obj.color),
                        "palette_color": _color(obj.palette_color),
                        "color_shift": obj.color_shift,
                        "color_scale": obj.color_scale,
                        "transform": _transform(initial.transform),
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, ComplexMappedGrid):
            assert isinstance(initial, InfiniteSnapshot)
            progress: Any
            if isinstance(obj.progress, ScalarValue):
                progress = {"value_ref": _registered_id(scene, obj.progress)}
            else:
                progress = float(obj.progress)
            objects.append(
                {
                    **common,
                    "kind": "complex_grid",
                    "state": {
                        "map_kind": obj.map_kind,
                        "origin": _vec(obj.origin),
                        "step": _vec(obj.step),
                        "progress": progress,
                        "map_params": list(obj.map_params),
                        "x_color": _color(obj.color),
                        "y_color": _color(obj.secondary_color),
                        "stroke_width": obj.stroke_width,
                        "transform": _transform(initial.transform),
                        "opacity": initial.opacity,
                        "z_index": initial.z_index,
                    },
                }
            )
        elif isinstance(obj, ScalarValue):
            values.append({**common, "kind": "scalar", "initial": float(initial)})
        elif isinstance(obj, InfiniteObject2D):
            raise SceneIRUnsupported(f"unsupported infinite object: {type(obj).__name__}")
        else:
            raise SceneIRUnsupported(f"Scene IR v1 does not support {type(obj).__name__}")

    clips: list[dict[str, Any]] = []
    for clip in scene._timeline.clips:
        if isinstance(clip, TransformClip):
            clips.append(
                {
                    "kind": "transform",
                    "target": clip.object_id,
                    **_span(clip),
                    "before": _transform(clip.before),
                    "after": _transform(clip.after),
                }
            )
        elif isinstance(clip, SE2TransformClip):
            clips.append(
                {
                    "kind": "se2_transform",
                    "target": clip.object_id,
                    **_span(clip),
                    "before": {
                        "theta": clip.before.theta,
                        "translation": _vec(clip.before.translation),
                    },
                    "after": {
                        "theta": clip.after.theta,
                        "translation": _vec(clip.after.translation),
                    },
                }
            )
        elif isinstance(clip, TransformFunctionClip):
            if not sample_transform_functions:
                raise SceneIRUnsupported(
                    "TransformFunctionClip contains runtime code; pass sample_transform_functions=True to bake it"
                )
            sample_times = _frame_sample_times(clip.span.start, clip.span.end, sample_rate)
            samples = [_transform(clip.sample(time)) for time in sample_times]
            clips.append(
                {
                    "kind": "sampled_transform",
                    "target": clip.object_id,
                    "start": clip.span.start,
                    "duration": clip.span.duration,
                    "sample_rate": sample_rate,
                    "sample_offsets": [time - clip.span.start for time in sample_times],
                    "samples": samples,
                }
            )
        elif isinstance(clip, OpacityClip):
            clips.append(
                {
                    "kind": "opacity",
                    "target": clip.object_id,
                    **_span(clip),
                    "before": clip.before,
                    "after": clip.after,
                }
            )
        elif isinstance(clip, StyleClip):
            clips.append(
                {
                    "kind": "style",
                    "target": clip.object_id,
                    **_span(clip),
                    "before": _style(clip.before),
                    "after": _style(clip.after),
                }
            )
        elif isinstance(clip, PathTrimClip):
            clips.append(
                {
                    "kind": "trim",
                    "target": clip.object_id,
                    **_span(clip),
                    "before": clip.before,
                    "after": clip.after,
                }
            )
        elif isinstance(clip, RevealClip):
            clips.append(
                {
                    "kind": "reveal",
                    "target": clip.object_id,
                    **_span(clip),
                    "before": clip.before,
                    "after": clip.after,
                }
            )
        elif isinstance(clip, BatchClip):
            clips.append(
                {
                    "kind": "batch",
                    "target": clip.object_id,
                    **_span(clip),
                    "before": _batch(clip.before),
                    "after": _batch(clip.after),
                }
            )
        elif isinstance(clip, ValueClip):
            clips.append(
                {
                    "kind": "value",
                    "target": clip.value_id,
                    **_span(clip),
                    "before": clip.before,
                    "after": clip.after,
                }
            )
        elif isinstance(clip, InterpolationClip):
            clips.append(
                {
                    "kind": "interpolation",
                    **_span(clip),
                    "source": _object_snapshot(clip.interpolation.source),
                    "target": _object_snapshot(clip.interpolation.target),
                }
            )
        else:
            raise SceneIRUnsupported(f"Scene IR v1 does not support clip {type(clip).__name__}")

    result = {
        "format": FORMAT,
        "version": VERSION,
        "canvas": {
            "width": scene.canvas.width,
            "height": scene.canvas.height,
            "unit_size": scene.canvas.unit_size,
        },
        "fps": scene.fps,
        "duration": scene.duration,
        "objects": objects,
        "values": values,
        "resources": resources,
        "clips": clips,
        "meta": {
            "portable": True,
            "sampled_transform_functions": sum(c["kind"] == "sampled_transform" for c in clips),
            "sampled_dynamic_objects": sum(
                obj["kind"] in {"sampled_object2d", "sampled_batch2d", "sampled_vector2d"}
                for obj in objects
            ),
        },
    }

    if include_debug:
        from .source import get_preview_source

        source = get_preview_source(scene)
        if source is not None:
            result["debug"] = {
                "source": {"path": source.path, "text": source.text},
                "objects": {
                    str(reg.object_id): {
                        "type": type(reg.object_ref).__name__,
                        "names": list(source.object_names.get(reg.object_id, ())),
                    }
                    for reg in scene._registry
                },
            }
            if len(clips) != len(scene._timeline.clips):
                raise AssertionError(
                    "Scene IR debug mapping requires one IR clip per Timeline clip"
                )
            for raw, authored in zip(clips, scene._timeline.clips):
                span = source.clip_source(authored)
                if span is not None:
                    raw["debug"] = {"source": span.as_dict()}

    return result


def write_scene_ir(scene: Scene, path: str | Path, **options) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(scene_to_ir(scene, **options), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def read_scene_ir(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validate_header(ir) -> None:
    if ir.get("format") != FORMAT or int(ir.get("version", -1)) != VERSION:
        raise ValueError(f"unsupported Zanim Scene IR: {ir.get('format')!r} v{ir.get('version')!r}")


def scene_from_ir(ir: dict[str, Any]) -> Scene:
    """Reconstruct a portable IR scene for the existing Native renderer."""
    _validate_header(ir)
    canvas_raw = ir["canvas"]
    records = {int(x["id"]): x for x in ir.get("objects", [])}
    values_raw = {int(x["id"]): x for x in ir.get("values", [])}
    resources = {int(x["id"]): x for x in ir.get("resources", [])}
    camera_record = next((r for r in records.values() if r["kind"] == "camera2d"), None)
    camera = (
        Camera2D(transform=_transform_from(camera_record["state"]["transform"]))
        if camera_record
        else Camera2D()
    )
    scene = Scene(
        canvas=Canvas(
            int(canvas_raw["width"]), int(canvas_raw["height"]), float(canvas_raw["unit_size"])
        ),
        fps=int(ir["fps"]),
        camera=camera,
    )

    raw_by_ir: dict[int, Any] = {0: scene.camera}
    # First construct non-camera objects without hierarchy.
    for oid, record in sorted(records.items()):
        if record["kind"] == "camera2d":
            raw_by_ir[oid] = scene.camera
            continue
        s = record["state"]
        kind = record["kind"]
        common = {
            "transform": _transform_from(s["transform"]),
            "opacity": float(s.get("opacity", 1)),
            "z_index": int(s.get("z_index", 0)),
        }
        if kind == "fourier_epicycles":
            terms = tuple(
                FourierTerm(int(raw[0]), complex(float(raw[1]), float(raw[2])))
                for raw in s["terms"]
            )
            obj = FourierEpicycles(
                terms,
                start_time=float(s["start_time"]),
                draw_duration=float(s["draw_duration"]),
                circle_samples=int(s["circle_samples"]),
                trace_samples=int(s["trace_samples"]),
                visual_indices=tuple(int(i) for i in s["visual_indices"]),
                circle_style=_style_from(s["circle_style"]),
                arrow_style=_style_from(s["arrow_style"]),
                trace_style=_style_from(s["trace_style"]),
                tip_style=_style_from(s["tip_style"]),
                tip_radius=float(s["tip_radius"]),
                tip_sides=int(s["tip_sides"]),
                **common,
            )
        elif kind == "group":
            obj = Group([], **common)
        elif kind == "object2d":
            obj = Object2D(
                _geometry_from(s["geometry"]),
                style=_style_from(s["style"]),
                trim=float(s.get("trim", 1)),
                **common,
            )
        elif kind == "function_plot":
            axes_raw = s["axes"]
            from .plot import Axes

            axes = Axes(
                tuple(float(x) for x in axes_raw["x_range"]),
                tuple(float(x) for x in axes_raw["y_range"]),
                float(axes_raw["width"]),
                float(axes_raw["height"]),
                Vec2(*map(float, axes_raw["center"])),
            )
            style = _style_from(s["style"])
            if style.stroke is None:
                raise ValueError("IR function_plot requires a stroke")
            obj = FunctionPlot(
                ScalarExpr.from_data(s["expression"]),
                axes=axes,
                x_range=tuple(float(x) for x in s["x_range"]),
                samples=int(s["samples"]),
                color=style.stroke.color,
                stroke_width=style.stroke.width,
                **common,
            )
            obj.trim = float(s.get("trim", 1))
        elif kind == "sampled_object2d":
            start = float(s["sample_start"])
            times = tuple(start + float(x) for x in s["sample_offsets"])
            samples = tuple(_geometry_from(x) for x in s["samples"])
            obj = DynamicGeometryObject2D(
                lambda time, times=times, samples=samples: _sample_lookup(times, samples, time),
                style=_style_from(s["style"]),
                **common,
            )
            obj.trim = float(s.get("trim", 1))
        elif kind == "batch2d":
            obj = BatchObject2D(_batch_from(s["batch"]), **common)
        elif kind == "sampled_batch2d":
            start = float(s["sample_start"])
            times = tuple(start + float(x) for x in s["sample_offsets"])
            samples = tuple(_batch_from(x) for x in s["samples"])
            obj = DynamicBatchObject2D(
                lambda time, times=times, samples=samples: _sample_lookup(times, samples, time),
                **common,
            )
        elif kind == "vector2d":
            resource = resources.get(int(s["resource"]))
            if resource is None or resource.get("kind") != "vector_document":
                raise ValueError("IR vector2d references a missing vector_document resource")
            obj = VectorObject2D(
                _vector_document_from(resource["data"]), reveal=float(s.get("reveal", 1)), **common
            )
        elif kind == "sampled_vector2d":
            start = float(s["sample_start"])
            times = tuple(start + float(x) for x in s["sample_offsets"])
            docs = []
            for resource_id in s["samples"]:
                resource = resources.get(int(resource_id))
                if resource is None or resource.get("kind") != "vector_document":
                    raise ValueError(
                        "IR sampled_vector2d references a missing vector_document resource"
                    )
                docs.append(_vector_document_from(resource["data"]))
            samples = tuple(docs)
            obj = DynamicVectorObject2D(
                lambda time, times=times, samples=samples: _sample_lookup(times, samples, time),
                reveal=float(s.get("reveal", 1)),
                **common,
            )
        elif kind == "infinite_line":
            obj = InfiniteLine(
                s["point"],
                s["direction"],
                color=_color_from(s["color"]),
                stroke_width=float(s["stroke_width"]),
                **common,
            )
        elif kind == "infinite_grid":
            obj = InfiniteGrid(
                tuple(s["step"]),
                origin=s["origin"],
                color=_color_from(s["color"]),
                stroke_width=float(s["stroke_width"]),
                **common,
            )
        elif kind == "fractal":
            kwargs = dict(
                transform=common["transform"],
                max_iter=int(s["max_iter"]),
                escape_radius=float(s["escape_radius"]),
                inside_color=_color_from(s["inside_color"]),
                palette_color=_color_from(s["palette_color"]),
                color_shift=float(s["color_shift"]),
                color_scale=float(s["color_scale"]),
                opacity=common["opacity"],
                z_index=common["z_index"],
            )
            obj = (
                MandelbrotSet(**kwargs)
                if int(s["fractal_kind"]) == 1
                else JuliaSet(complex(*s["julia_c"]), **kwargs)
            )
        elif kind == "complex_grid":
            mapping = {1: "square", 2: "exp", 3: "reciprocal", 4: "mobius"}[int(s["map_kind"])]
            progress = s["progress"]
            if isinstance(progress, dict):
                # resolved after ScalarValue construction
                progress = 0.0
            kwargs: dict[str, Any] = dict(
                step=tuple(s["step"]),
                origin=s["origin"],
                progress=progress,
                x_color=_color_from(s["x_color"]),
                y_color=_color_from(s["y_color"]),
                stroke_width=float(s["stroke_width"]),
                **common,
            )
            params = list(s.get("map_params", []))
            if mapping == "exp" and params:
                kwargs["exp_warp"] = complex(params[0], params[1])
            elif mapping == "mobius" and len(params) == 8:
                kwargs["mobius"] = tuple(complex(params[i], params[i + 1]) for i in range(0, 8, 2))
            obj = ComplexMappedGrid(mapping, **kwargs)
        else:
            raise SceneIRUnsupported(f"cannot load IR object kind into Python: {kind}")
        raw_by_ir[oid] = obj

    for vid, record in sorted(values_raw.items()):
        raw_by_ir[vid] = ScalarValue(float(record["initial"]))

    # Resolve ScalarValue bindings now that all values exist.
    for oid, record in records.items():
        if record["kind"] == "complex_grid" and isinstance(record["state"]["progress"], dict):
            ref = int(record["state"]["progress"]["value_ref"])
            raw_by_ir[oid].progress = raw_by_ir[ref]

    # Assemble Group children before Scene.add().
    for oid, record in records.items():
        parent = record.get("parent")
        if parent is not None and record["kind"] != "camera2d":
            p = raw_by_ir[int(parent)]
            if not isinstance(p, Group):
                raise ValueError("IR parent must refer to a Group")
            p._children.append(raw_by_ir[oid])

    roots = []
    for oid, record in records.items():
        if record["kind"] != "camera2d" and record.get("parent") is None:
            roots.append((float(record.get("birth", 0)), oid, raw_by_ir[oid]))
    for vid, record in values_raw.items():
        roots.append((float(record.get("birth", 0)), vid, raw_by_ir[vid]))
    for birth, _oid, obj in sorted(roots):
        scene._timeline.cursor = birth
        scene.add(obj)

    # Map portable IDs to the reconstructed Scene registry IDs.
    native_id: dict[int, int] = {0: 0}
    for oid, obj in raw_by_ir.items():
        if oid == 0:
            continue
        native_id[oid] = scene._require_registered(obj).object_id
    for oid, record in {**records, **values_raw}.items():
        if oid == 0:
            continue
        removed = record.get("death")
        if removed is not None:
            scene._by_id[native_id[oid]].removed_at = float(removed)

    def easing(name: str) -> Easing:
        return Easing(name)

    # Exact spans are already resolved in IR; append dataclasses directly.
    scene._timeline.cursor = 0.0
    ordered_clips = sorted(
        enumerate(ir.get("clips", [])), key=lambda item: (float(item[1]["start"]), item[0])
    )
    for _order, raw in ordered_clips:
        span = TimeSpan(float(raw["start"]), float(raw["duration"]))
        kind = raw["kind"]
        e = easing(raw.get("easing", "smoothstep"))
        if kind == "transform":
            clip = TransformClip(
                native_id[int(raw["target"])],
                span,
                _transform_from(raw["before"]),
                _transform_from(raw["after"]),
                e,
            )
            scene._timeline._append(clip)
        elif kind == "se2_transform":
            before = raw["before"]
            after = raw["after"]
            clip = SE2TransformClip(
                native_id[int(raw["target"])],
                span,
                SE2(float(before["theta"]), Vec2(*map(float, before["translation"]))),
                SE2(float(after["theta"]), Vec2(*map(float, after["translation"]))),
                e,
            )
            scene._timeline._append(clip)
        elif kind == "sampled_transform":
            samples = tuple(_transform_from(x) for x in raw["samples"])
            offsets = tuple(float(x) for x in raw.get("sample_offsets", ()))
            if not offsets:
                offsets = tuple(
                    span.duration * i / max(1, len(samples) - 1) for i in range(len(samples))
                )
            if len(offsets) != len(samples):
                raise ValueError("sampled_transform offsets/samples length mismatch")

            def provider(alpha: float, samples=samples, offsets=offsets, duration=span.duration):
                if len(samples) == 1:
                    return samples[0]
                local = max(0.0, min(1.0, alpha)) * duration
                i = bisect_right(offsets, local + 1e-12) - 1
                i = max(0, min(len(samples) - 1, i))
                if abs(local - offsets[i]) <= 1e-10 or i == len(samples) - 1:
                    return samples[i]
                j = i + 1
                width = offsets[j] - offsets[i]
                u = 0.0 if width <= 1e-15 else (local - offsets[i]) / width
                from .timeline import lerp_transform

                return lerp_transform(samples[i], samples[j], max(0.0, min(1.0, u)))

            clip = TransformFunctionClip(
                native_id[int(raw["target"])],
                span,
                provider,
                samples[0],
                samples[-1],
                Easing.LINEAR,
            )
            scene._timeline._append(clip)
        elif kind == "opacity":
            scene._timeline._append(
                OpacityClip(
                    native_id[int(raw["target"])],
                    span,
                    float(raw["before"]),
                    float(raw["after"]),
                    e,
                )
            )
        elif kind == "style":
            scene._timeline._append(
                StyleClip(
                    native_id[int(raw["target"])],
                    span,
                    _style_from(raw["before"]),
                    _style_from(raw["after"]),
                    e,
                )
            )
        elif kind == "trim":
            scene._timeline._append(
                PathTrimClip(
                    native_id[int(raw["target"])],
                    span,
                    float(raw["before"]),
                    float(raw["after"]),
                    e,
                )
            )
        elif kind == "reveal":
            scene._timeline._append(
                RevealClip(
                    native_id[int(raw["target"])],
                    span,
                    float(raw["before"]),
                    float(raw["after"]),
                    e,
                )
            )
        elif kind == "batch":
            scene._timeline._append(
                BatchClip(
                    native_id[int(raw["target"])],
                    span,
                    _batch_from(raw["before"]),
                    _batch_from(raw["after"]),
                    e,
                )
            )
        elif kind == "value":
            target = native_id[int(raw["target"])]
            clip = ValueClip(target, span, float(raw["before"]), float(raw["after"]), e)
            scene._timeline._append(clip, key_name="value_id")
            value_obj = raw_by_ir[int(raw["target"])]
            value_obj._clips.append(clip)
        elif kind == "interpolation":
            interp = ObjectInterpolation(
                _object_snapshot_from(raw["source"]), _object_snapshot_from(raw["target"])
            )
            scene._timeline._append(InterpolationClip(interp, span, e), key_name=None)
        else:
            raise SceneIRUnsupported(f"cannot load IR clip kind into Python: {kind}")

    scene._timeline.cursor = float(ir.get("duration", 0.0))
    return scene


def load_scene_ir(path: str | Path) -> Scene:
    return scene_from_ir(read_scene_ir(path))
