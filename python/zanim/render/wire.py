from __future__ import annotations

import ctypes
import threading
import weakref
from dataclasses import dataclass

from .abi import (
    WireBatch,
    WireCamera3D,
    WireDrawItem,
    WireInterpolation,
    WireMesh3D,
    WireObject,
    WireRaster,
    WireScene3DLayer,
    WireVectorObject,
    WireVectorPath,
)

DRAW_OBJECT = 0
DRAW_BATCH = 1
DRAW_VECTOR = 2
DRAW_INTERPOLATION = 3
DRAW_RASTER = 4
DRAW_SCENE3D = 5


def _pack_rgba(color) -> int:
    return (int(color.r) << 24) | (int(color.g) << 16) | (int(color.b) << 8) | int(color.a)


def _wire_object(snapshot):
    from ..geometry import (
        ArcGeometry,
        CircleGeometry,
        CubicBezierGeometry,
        EllipseGeometry,
        LineGeometry,
        PolygonGeometry,
        PolylineGeometry,
        RectangleGeometry,
        RegularPolygonGeometry,
        SquareGeometry,
    )

    geometry = snapshot.geometry
    params = [0.0] * 8
    points_array = None
    point_count = 0

    if isinstance(geometry, LineGeometry):
        kind = 0
        params[:4] = [geometry.start.x, geometry.start.y, geometry.end.x, geometry.end.y]
    elif isinstance(geometry, PolylineGeometry):
        kind = 1
        flat = [value for point in geometry.points for value in (point.x, point.y)]
        points_array = (ctypes.c_double * len(flat))(*flat)
        point_count = len(geometry.points)
    elif isinstance(geometry, PolygonGeometry):
        kind = 2
        flat = [value for point in geometry.points for value in (point.x, point.y)]
        points_array = (ctypes.c_double * len(flat))(*flat)
        point_count = len(geometry.points)
    elif isinstance(geometry, RectangleGeometry):
        kind = 3
        params[:2] = [geometry.width, geometry.height]
    elif isinstance(geometry, SquareGeometry):
        kind = 4
        params[0] = geometry.side
    elif isinstance(geometry, CircleGeometry):
        kind = 5
        params[0] = geometry.radius
    elif isinstance(geometry, EllipseGeometry):
        kind = 6
        params[:2] = [geometry.radius_x, geometry.radius_y]
    elif isinstance(geometry, ArcGeometry):
        kind = 7
        params[:3] = [geometry.radius, geometry.start_angle, geometry.sweep_angle]
    elif isinstance(geometry, RegularPolygonGeometry):
        kind = 8
        params[:3] = [float(geometry.sides), geometry.radius, geometry.phase]
    elif isinstance(geometry, CubicBezierGeometry):
        kind = 9
        params[:] = [
            geometry.p0.x,
            geometry.p0.y,
            geometry.p1.x,
            geometry.p1.y,
            geometry.p2.x,
            geometry.p2.y,
            geometry.p3.x,
            geometry.p3.y,
        ]
    else:
        raise TypeError(
            f"geometry is not supported by scene wire format: {type(geometry).__name__}"
        )

    transform = snapshot.transform
    style = snapshot.style
    points_ptr = (
        ctypes.cast(points_array, ctypes.POINTER(ctypes.c_double))
        if points_array is not None
        else ctypes.POINTER(ctypes.c_double)()
    )
    wire = WireObject(
        kind,
        *params,
        points_ptr,
        point_count,
        transform.xx,
        transform.xy,
        transform.yx,
        transform.yy,
        transform.tx,
        transform.ty,
        int(style.fill is not None),
        _pack_rgba(style.fill) if style.fill is not None else 0,
        int(style.stroke is not None),
        _pack_rgba(style.stroke.color) if style.stroke is not None else 0,
        style.stroke.width if style.stroke is not None else 0.0,
        float(snapshot.opacity),
    )
    return wire, points_array


class _WeakIdentityCache:
    """Cache ctypes encodings without extending source-object lifetime.

    ``id(obj)`` keeps lookup O(1) without hashing large immutable geometry.
    The weakref callback removes the entry when the source value dies, which is
    essential for per-frame DynamicVectorObject2D documents.
    """

    def __init__(self) -> None:
        self._values: dict[int, tuple[weakref.ReferenceType, object]] = {}

    def get(self, obj):
        entry = self._values.get(id(obj))
        if entry is None or entry[0]() is not obj:
            return None
        return entry[1]

    def set(self, obj, value) -> None:
        key = id(obj)
        values = self._values

        def discard(ref, *, key=key, values=values):
            current = values.get(key)
            if current is not None and current[0] is ref:
                values.pop(key, None)

        values[key] = (weakref.ref(obj, discard), value)

    def clear(self) -> None:
        self._values.clear()

    def __len__(self) -> int:
        return len(self._values)


_BATCH_STORAGE = _WeakIdentityCache()


def _batch_storage(batch_geometry):
    from ..batch import CircleSet, LineSet, RectSet

    cached = _BATCH_STORAGE.get(batch_geometry)
    if cached is not None:
        return cached

    if isinstance(batch_geometry, LineSet):
        kind = 0
        flat = [
            value
            for start, end in zip(batch_geometry.starts, batch_geometry.ends)
            for value in (start.x, start.y, end.x, end.y)
        ]
        fills = None
        strokes = [_pack_rgba(color) for color in batch_geometry.colors]
        widths = list(batch_geometry.widths)
    elif isinstance(batch_geometry, CircleSet):
        kind = 1
        flat = [
            value
            for center, radius in zip(batch_geometry.centers, batch_geometry.radii)
            for value in (center.x, center.y, radius)
        ]
        fills = [_pack_rgba(color) for color in batch_geometry.fills]
        strokes = (
            [_pack_rgba(color) for color in batch_geometry.stroke_colors]
            if batch_geometry.stroke_colors is not None
            else None
        )
        widths = (
            list(batch_geometry.stroke_widths) if batch_geometry.stroke_widths is not None else None
        )
    elif isinstance(batch_geometry, RectSet):
        kind = 2
        flat = [
            value
            for center, size in zip(batch_geometry.centers, batch_geometry.sizes)
            for value in (center.x, center.y, size.x, size.y)
        ]
        fills = [_pack_rgba(color) for color in batch_geometry.fills]
        strokes = (
            [_pack_rgba(color) for color in batch_geometry.stroke_colors]
            if batch_geometry.stroke_colors is not None
            else None
        )
        widths = (
            list(batch_geometry.stroke_widths) if batch_geometry.stroke_widths is not None else None
        )
    else:
        raise TypeError(f"unsupported batch geometry: {type(batch_geometry).__name__}")

    data_array = (ctypes.c_double * len(flat))(*flat)
    fill_array = (ctypes.c_uint32 * len(fills))(*fills) if fills is not None else None
    stroke_array = (ctypes.c_uint32 * len(strokes))(*strokes) if strokes is not None else None
    width_array = (ctypes.c_double * len(widths))(*widths) if widths is not None else None
    value = (data_array, fill_array, stroke_array, width_array, kind)
    _BATCH_STORAGE.set(batch_geometry, value)
    return value


def _wire_batch(snapshot, target=None, alpha: float = 0.0):
    data, fills, strokes, widths, kind = _batch_storage(snapshot.batch)
    target_data = target_fills = target_strokes = target_widths = None
    if target is not None:
        target_data, target_fills, target_strokes, target_widths, target_kind = _batch_storage(
            target.batch
        )
        if target_kind != kind or len(target.batch) != len(snapshot.batch):
            raise ValueError("batch transition endpoints are incompatible")

    null_u32 = ctypes.POINTER(ctypes.c_uint32)
    null_f64 = ctypes.POINTER(ctypes.c_double)
    transform = snapshot.transform
    return WireBatch(
        kind,
        len(snapshot.batch),
        ctypes.cast(data, ctypes.POINTER(ctypes.c_double)),
        ctypes.cast(fills, ctypes.POINTER(ctypes.c_uint32)) if fills is not None else null_u32(),
        ctypes.cast(strokes, ctypes.POINTER(ctypes.c_uint32))
        if strokes is not None
        else null_u32(),
        ctypes.cast(widths, ctypes.POINTER(ctypes.c_double)) if widths is not None else null_f64(),
        ctypes.cast(target_data, ctypes.POINTER(ctypes.c_double))
        if target_data is not None
        else null_f64(),
        ctypes.cast(target_fills, ctypes.POINTER(ctypes.c_uint32))
        if target_fills is not None
        else null_u32(),
        ctypes.cast(target_strokes, ctypes.POINTER(ctypes.c_uint32))
        if target_strokes is not None
        else null_u32(),
        ctypes.cast(target_widths, ctypes.POINTER(ctypes.c_double))
        if target_widths is not None
        else null_f64(),
        float(alpha),
        transform.xx,
        transform.xy,
        transform.yx,
        transform.yy,
        transform.tx,
        transform.ty,
        float(snapshot.opacity),
    )


_VECTOR_STORAGE = _WeakIdentityCache()


def _vector_storage(document):
    cached = _VECTOR_STORAGE.get(document)
    if cached is not None:
        return cached

    wires = []
    keepalive: list[object] = []
    for path in document.paths:
        flat: list[float] = []
        ends: list[int] = []
        closed: list[int] = []
        count = 0
        for contour in path.contours:
            for segment in contour.segments:
                flat.extend(
                    (
                        segment.p0.x,
                        segment.p0.y,
                        segment.p1.x,
                        segment.p1.y,
                        segment.p2.x,
                        segment.p2.y,
                        segment.p3.x,
                        segment.p3.y,
                    )
                )
                count += 1
            ends.append(count)
            closed.append(int(contour.closed))

        segment_array = (ctypes.c_double * len(flat))(*flat)
        end_array = (ctypes.c_uint32 * len(ends))(*ends)
        closed_array = (ctypes.c_uint8 * len(closed))(*closed)
        keepalive.extend((segment_array, end_array, closed_array))
        wires.append(
            WireVectorPath(
                count,
                ctypes.cast(segment_array, ctypes.POINTER(ctypes.c_double)),
                len(ends),
                ctypes.cast(end_array, ctypes.POINTER(ctypes.c_uint32)),
                ctypes.cast(closed_array, ctypes.POINTER(ctypes.c_uint8)),
                int(path.fill is not None),
                _pack_rgba(path.fill) if path.fill is not None else 0,
                int(path.stroke is not None),
                _pack_rgba(path.stroke.color) if path.stroke is not None else 0,
                path.stroke.width if path.stroke is not None else 0.0,
                path.group,
            )
        )

    path_array = (WireVectorPath * len(wires))(*wires) if wires else None
    if path_array is not None:
        keepalive.append(path_array)
    value = (path_array, tuple(keepalive))
    _VECTOR_STORAGE.set(document, value)
    return value


def _wire_vector(snapshot):
    path_array, keepalive = _vector_storage(snapshot.document)
    transform = snapshot.transform
    return WireVectorObject(
        len(snapshot.document.paths),
        ctypes.cast(path_array, ctypes.POINTER(WireVectorPath))
        if path_array is not None
        else ctypes.POINTER(WireVectorPath)(),
        snapshot.document.group_count,
        snapshot.reveal,
        transform.xx,
        transform.xy,
        transform.yx,
        transform.yy,
        transform.tx,
        transform.ty,
        float(snapshot.opacity),
    ), keepalive


def _wire_raster(snapshot):
    frame = snapshot.frame
    pixel_array = (ctypes.c_uint8 * len(frame.rgba)).from_buffer(frame.rgba)
    transform = snapshot.transform
    wire = WireRaster(
        ctypes.cast(pixel_array, ctypes.POINTER(ctypes.c_uint8)),
        frame.width,
        frame.height,
        snapshot.width,
        snapshot.height,
        transform.xx,
        transform.xy,
        transform.yx,
        transform.yy,
        transform.tx,
        transform.ty,
        float(snapshot.opacity),
    )
    return wire, pixel_array


class _Mesh3DStorage:
    """Thread-safe weak identity cache for immutable mesh arrays."""

    def __init__(self) -> None:
        self._values: dict[int, tuple[weakref.ReferenceType, tuple[object, object, object]]] = {}
        self._lock = threading.Lock()

    def get(self, mesh):
        with self._lock:
            entry = self._values.get(id(mesh))
            if entry is not None and entry[0]() is mesh:
                return entry[1]

            positions = (ctypes.c_float * (len(mesh.vertices) * 3))(
                *(value for vertex in mesh.vertices for value in (vertex.x, vertex.y, vertex.z))
            )
            normals = (ctypes.c_float * (len(mesh.normals) * 3))(
                *(value for normal in mesh.normals for value in (normal.x, normal.y, normal.z))
            )
            indices = (ctypes.c_uint32 * len(mesh.indices))(*mesh.indices)
            value = (positions, normals, indices)
            key = id(mesh)
            values = self._values
            lock = self._lock

            def discard(ref, *, key=key, values=values, lock=lock):
                with lock:
                    current = values.get(key)
                    if current is not None and current[0] is ref:
                        values.pop(key, None)

            self._values[key] = (weakref.ref(mesh, discard), value)
            return value


_MESH3D_STORAGE = _Mesh3DStorage()


def _wire_camera3d(camera) -> WireCamera3D:
    return WireCamera3D(
        camera.position.x,
        camera.position.y,
        camera.position.z,
        camera.target.x,
        camera.target.y,
        camera.target.z,
        camera.up.x,
        camera.up.y,
        camera.up.z,
        camera.fov_y_degrees,
        camera.near,
        camera.far,
        0.0 if camera.orthographic_height is None else camera.orthographic_height,
        0 if camera.orthographic_height is None else 1,
    )


def _wire_mesh3d(render_mesh):
    snapshot = render_mesh.snapshot
    mesh = snapshot.mesh
    positions, normals, indices = _MESH3D_STORAGE.get(mesh)
    model = snapshot.transform @ snapshot.geometry_transform
    matrix = (ctypes.c_float * 16)(*model.as_tuple())
    wire = WireMesh3D(
        len(mesh.vertices),
        ctypes.cast(positions, ctypes.POINTER(ctypes.c_float)),
        ctypes.cast(normals, ctypes.POINTER(ctypes.c_float)),
        len(mesh.indices),
        ctypes.cast(indices, ctypes.POINTER(ctypes.c_uint32)),
        matrix,
        _pack_rgba(snapshot.color),
        float(snapshot.opacity),
    )
    return wire, (positions, normals, indices, matrix)


def _wire_scene3d(snapshot):
    camera = snapshot.camera3d
    if camera is None:
        raise RuntimeError("3D snapshot is missing Camera3D state")
    meshes: list[WireMesh3D] = []
    keepalive: list[object] = []
    for render_mesh in snapshot.meshes3d:
        mesh_wire, owned = _wire_mesh3d(render_mesh)
        meshes.append(mesh_wire)
        keepalive.extend(owned)
    mesh_array = (WireMesh3D * len(meshes))(*meshes) if meshes else None
    if mesh_array is not None:
        keepalive.append(mesh_array)
    layer = WireScene3DLayer(
        _wire_camera3d(camera),
        ctypes.cast(mesh_array, ctypes.POINTER(WireMesh3D))
        if mesh_array is not None
        else ctypes.POINTER(WireMesh3D)(),
        len(meshes),
    )
    return layer, tuple(keepalive)


@dataclass(slots=True)
class EncodedScene:
    draw_items: list[WireDrawItem]
    draw_object_ids: list[int] | None
    objects: list[WireObject]
    batches: list[WireBatch]
    vectors: list[WireVectorObject]
    rasters: list[WireRaster]
    scene3d_layers: list[WireScene3DLayer]
    interpolations: list[WireInterpolation]
    draw_array: object | None
    object_array: object | None
    batch_array: object | None
    vector_array: object | None
    raster_array: object | None
    scene3d_array: object | None
    interpolation_array: object | None
    keepalive: list[object]


def encode_snapshot(snapshot, *, include_object_ids: bool = False) -> EncodedScene:
    objects: list[WireObject] = []
    batches: list[WireBatch] = []
    vectors: list[WireVectorObject] = []
    rasters: list[WireRaster] = []
    scene3d_layers: list[WireScene3DLayer] = []
    interpolations: list[WireInterpolation] = []
    ordered: list[tuple[int, int, int, int]] = []
    keepalive: list[object] = []

    for item in snapshot.objects:
        if item.snapshot.opacity <= 0.0:
            continue
        wire, owned = _wire_object(item.snapshot)
        index = len(objects)
        objects.append(wire)
        ordered.append((item.snapshot.z_index, item.object_id, DRAW_OBJECT, index))
        if owned is not None:
            keepalive.append(owned)

    for item in snapshot.batches:
        if item.snapshot.opacity <= 0.0:
            continue
        index = len(batches)
        batches.append(_wire_batch(item.snapshot, item.target, item.alpha))
        ordered.append((item.snapshot.z_index, item.object_id, DRAW_BATCH, index))

    for item in snapshot.vectors:
        if item.snapshot.opacity <= 0.0 or item.snapshot.reveal <= 0.0:
            continue
        wire, owned = _wire_vector(item.snapshot)
        index = len(vectors)
        vectors.append(wire)
        ordered.append((item.snapshot.z_index, item.object_id, DRAW_VECTOR, index))
        keepalive.extend(owned)

    for item in snapshot.rasters:
        if item.snapshot.opacity <= 0.0:
            continue
        wire, owned = _wire_raster(item.snapshot)
        index = len(rasters)
        rasters.append(wire)
        ordered.append((item.snapshot.z_index, item.object_id, DRAW_RASTER, index))
        keepalive.extend((owned, item.snapshot.frame.rgba))

    if snapshot.meshes3d:
        layer, owned = _wire_scene3d(snapshot)
        index = len(scene3d_layers)
        scene3d_layers.append(layer)
        # Camera3D owns one compositing layer. id=0 preserves the historical
        # behavior where a 3D layer sorts before ordinary objects at equal z.
        ordered.append((snapshot.camera3d.layer_z_index, 0, DRAW_SCENE3D, index))
        keepalive.extend(owned)

    # Interpolations are transient relations rather than persistent scene
    # objects. Preserve their historical behavior: draw them after persistent
    # content, but express that order through the same draw-command stream.
    transient_base = max((order for order, _, _, _ in ordered), default=0) + 1
    for offset, transient in enumerate(snapshot.transients):
        source, source_owned = _wire_object(transient.interpolation.source)
        target, target_owned = _wire_object(transient.interpolation.target)
        index = len(interpolations)
        interpolations.append(WireInterpolation(source, target, transient.alpha))
        ordered.append((transient_base + offset, 1_000_000_000 + offset, DRAW_INTERPOLATION, index))
        if source_owned is not None:
            keepalive.append(source_owned)
        if target_owned is not None:
            keepalive.append(target_owned)

    ordered.sort(key=lambda item: (item[0], item[1]))
    draw_items = [WireDrawItem(kind, index) for _, _, kind, index in ordered]
    draw_object_ids = (
        [
            0 if kind in (DRAW_INTERPOLATION, DRAW_SCENE3D) else object_id
            for _, object_id, kind, _ in ordered
        ]
        if include_object_ids
        else None
    )

    draw_array = (WireDrawItem * len(draw_items))(*draw_items) if draw_items else None
    object_array = (WireObject * len(objects))(*objects) if objects else None
    batch_array = (WireBatch * len(batches))(*batches) if batches else None
    vector_array = (WireVectorObject * len(vectors))(*vectors) if vectors else None
    raster_array = (WireRaster * len(rasters))(*rasters) if rasters else None
    scene3d_array = (
        (WireScene3DLayer * len(scene3d_layers))(*scene3d_layers) if scene3d_layers else None
    )
    interpolation_array = (
        (WireInterpolation * len(interpolations))(*interpolations) if interpolations else None
    )
    keepalive.extend(
        item
        for item in (
            draw_array,
            object_array,
            batch_array,
            vector_array,
            raster_array,
            scene3d_array,
            interpolation_array,
        )
        if item is not None
    )
    return EncodedScene(
        draw_items,
        draw_object_ids,
        objects,
        batches,
        vectors,
        rasters,
        scene3d_layers,
        interpolations,
        draw_array,
        object_array,
        batch_array,
        vector_array,
        raster_array,
        scene3d_array,
        interpolation_array,
        keepalive,
    )
