from __future__ import annotations

from dataclasses import dataclass, field

from ._scene_authoring import _SceneAuthoring
from ._scene_evaluator import _SceneEvaluator
from .audio import AudioObject
from .batch import BatchObject2D
from .camera import Camera2D
from .camera3d import Camera3D
from .geometry import Object2D
from .group import Group
from .mesh3d import MeshObject3D
from .object import SceneObject2D
from .raster import RasterObject2D
from .snapshot import (
    BatchSnapshot,
    Mesh3DSnapshot,
    NodeSnapshot,
    ObjectSnapshot,
    RasterState,
    VectorSnapshot,
)
from .space import (
    Canvas,
    Point2,
    Transform2D,
    Vec2,
    as_vec2,
)
from .timeline import (
    Timeline,
)
from .value import ScalarValue
from .vector import VectorObject2D

RenderableObject = Object2D | BatchObject2D | VectorObject2D | RasterObject2D
SceneObject = RenderableObject | Group | Camera2D
SceneItem = SceneObject | MeshObject3D | ScalarValue | AudioObject
InitialSnapshot = (
    ObjectSnapshot
    | BatchSnapshot
    | VectorSnapshot
    | RasterState
    | Mesh3DSnapshot
    | NodeSnapshot
    | float
    | None
)


@dataclass(slots=True)
class _RegisteredItem:
    object_id: int
    object_ref: SceneItem
    initial: InitialSnapshot
    parent_ids: tuple[int, ...] = ()
    added_at: float = 0.0
    removed_at: float | None = None


@dataclass(slots=True)
class Scene(_SceneAuthoring, _SceneEvaluator):
    """Deterministic authoring scene with one registry and one private scheduler."""

    canvas: Canvas = field(default_factory=Canvas)
    fps: int = 60
    _timeline: Timeline = field(default_factory=Timeline, init=False, repr=False)
    camera: Camera2D = field(default_factory=Camera2D)
    camera3d: Camera3D = field(default_factory=Camera3D)
    _registry: list[_RegisteredItem] = field(default_factory=list, init=False, repr=False)
    _by_id: dict[int, _RegisteredItem] = field(default_factory=dict, init=False, repr=False)
    _by_identity: dict[int, _RegisteredItem] = field(default_factory=dict, init=False, repr=False)
    _next_object_id: int = field(default=1, init=False, repr=False)
    _world_space_spans: dict[int, list[tuple[float, float]]] = field(
        default_factory=dict, init=False, repr=False
    )
    _handles: dict[int, object] = field(default_factory=dict, init=False, repr=False)
    _preview_source_info: object | None = field(default=None, init=False, repr=False)
    _preview_reload_info: object | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        # Camera uses the reserved id 0 so ordinary insertion order remains 1+.
        initial = NodeSnapshot(self.camera.transform, self.camera.opacity, self.camera.z_index)
        registered = _RegisteredItem(0, self.camera, initial, added_at=0.0)
        self._registry.append(registered)
        self._by_id[0] = registered
        self._by_identity[id(self.camera)] = registered
        self.camera._mark_scene_registered()
        self.camera._bind_scene(self)

    @property
    def frame(self):
        """World-space layout frame corresponding to the current Canvas."""
        from .layout import Frame

        return Frame.from_canvas(self.canvas)

    @property
    def width(self) -> int:
        return self.canvas.width

    @property
    def height(self) -> int:
        return self.canvas.height

    @property
    def objects(self) -> tuple[RenderableObject, ...]:
        """2D renderable leaves in stable insertion order."""
        return tuple(
            item.object_ref
            for item in self._registry
            if isinstance(
                item.object_ref, (Object2D, BatchObject2D, VectorObject2D, RasterObject2D)
            )
        )

    @property
    def objects3d(self) -> tuple[MeshObject3D, ...]:
        return tuple(
            item.object_ref for item in self._registry if isinstance(item.object_ref, MeshObject3D)
        )

    @property
    def has_3d(self) -> bool:
        return any(isinstance(item.object_ref, MeshObject3D) for item in self._registry)

    @property
    def items(self) -> tuple[SceneItem, ...]:
        """All registered authoring objects except the implicit camera."""
        return tuple(item.object_ref for item in self._registry if item.object_id != 0)

    def add(self, *objects: SceneItem):
        """Begin object lifetime and return Scene-bound authoring handle(s).

        ``add`` is the explicit boundary between pre-Scene declaration/layout
        and post-add timeline authoring. One object returns one bound handle;
        multiple objects return a tuple in the same order. The underlying object
        identity is unchanged and no visual state is modified.
        """
        self._require_lifetime_boundary()
        if not objects:
            raise ValueError("add() requires at least one object")
        added_at = self._timeline.cursor
        handles = []
        for obj in objects:
            if isinstance(obj, Camera2D) or not isinstance(
                obj, (SceneObject2D, MeshObject3D, ScalarValue, AudioObject)
            ):
                raise TypeError(f"unsupported scene item: {type(obj).__name__}")
            self._register(obj, (), set(), added_at)
            handles.append(self.on(obj))
        return handles[0] if len(handles) == 1 else tuple(handles)

    def on(self, obj):
        """Return the stable Scene-bound handle for one registered item."""
        from .bound import (
            BoundAudio,
            BoundBatch2D,
            BoundGroup,
            BoundItem,
            BoundMesh3D,
            BoundObject2D,
            BoundRaster2D,
            BoundValue,
            BoundVector2D,
        )

        # Accepting an existing handle is useful in generic code but crossing
        # Scene ownership is never guessed.
        if isinstance(obj, BoundItem):
            if obj.scene is not self:
                raise ValueError("bound handle belongs to a different Scene")
            return obj
        registered = self._require_registered(obj)
        cached = self._handles.get(registered.object_id)
        if cached is not None:
            return cached
        raw = registered.object_ref
        if isinstance(raw, Object2D):
            handle = BoundObject2D(self, raw)
        elif isinstance(raw, BatchObject2D):
            handle = BoundBatch2D(self, raw)
        elif isinstance(raw, VectorObject2D):
            handle = BoundVector2D(self, raw)
        elif isinstance(raw, RasterObject2D):
            handle = BoundRaster2D(self, raw)
        elif isinstance(raw, Group):
            handle = BoundGroup(self, raw)
        elif isinstance(raw, MeshObject3D):
            handle = BoundMesh3D(self, raw)
        elif isinstance(raw, ScalarValue):
            handle = BoundValue(self, raw)
        elif isinstance(raw, AudioObject):
            handle = BoundAudio(self, raw)
        else:
            raise TypeError(f"unsupported bound item: {type(raw).__name__}")
        self._handles[registered.object_id] = handle
        return handle

    @staticmethod
    def _unwrap(obj):
        from .bound import BoundItem

        return obj.raw if isinstance(obj, BoundItem) else obj

    def remove(self, *objects: SceneItem) -> "Scene":
        """Remove existing objects from the scene at the current cursor.

        Lifetimes are half-open: ``[add_time, remove_time)``. Removing an
        object does not fade it or otherwise alter its authored state.
        """
        self._require_lifetime_boundary()
        removed_at = self._timeline.cursor
        for obj in objects:
            obj = self._unwrap(obj)
            registered = self._require_registered(obj)
            if registered.object_id == 0:
                raise TypeError("Camera2D cannot be removed from Scene")
            if registered.removed_at is not None:
                raise ValueError("object has already been removed from this scene")
            if removed_at < registered.added_at:
                raise ValueError("object cannot be removed before it is added")
            registered.removed_at = removed_at
        return self

    def _require_lifetime_boundary(self) -> None:
        if self._timeline._parallel_base is not None:
            raise ValueError("add() and remove() are not allowed inside parallel()")

    def _register(
        self, obj: SceneItem, parents: tuple[int, ...], ancestry: set[int], added_at: float
    ) -> int:
        if self._find_registered(obj) is not None:
            raise ValueError("object is already in this scene")
        identity = id(obj)
        if identity in ancestry:
            raise ValueError("Group hierarchy contains a cycle")

        object_id = self._next_object_id
        self._next_object_id += 1
        if isinstance(obj, Object2D):
            initial: InitialSnapshot = ObjectSnapshot.from_object(obj)
        elif isinstance(obj, BatchObject2D):
            initial = BatchSnapshot.from_object(obj)
        elif isinstance(obj, VectorObject2D):
            initial = VectorSnapshot.from_object(obj)
        elif isinstance(obj, RasterObject2D):
            initial = RasterState.from_object(obj)
        elif isinstance(obj, MeshObject3D):
            if parents:
                raise TypeError("MeshObject3D cannot be a Group child")
            initial = Mesh3DSnapshot.from_object(obj)
        elif isinstance(obj, Group):
            initial = NodeSnapshot(obj.transform, obj.opacity, obj.z_index)
        elif isinstance(obj, ScalarValue):
            if parents:
                raise TypeError("ScalarValue cannot be a Group child")
            initial = obj._initial
        elif isinstance(obj, AudioObject):
            if parents:
                raise TypeError("AudioObject cannot be a Group child")
            initial = None
        else:
            raise TypeError(f"unsupported scene item: {type(obj).__name__}")

        registered = _RegisteredItem(object_id, obj, initial, parents, added_at=added_at)
        self._registry.append(registered)
        self._by_id[object_id] = registered
        self._by_identity[identity] = registered

        if isinstance(obj, Group):
            next_ancestry = set(ancestry)
            next_ancestry.add(identity)
            child_parents = parents + (object_id,)
            for child in obj.children:
                self._register(child, child_parents, next_ancestry, added_at)
        if hasattr(obj, "_mark_scene_registered"):
            obj._mark_scene_registered()
        return object_id

    def _scheduled_span(self, duration: float | None, at: float) -> tuple[float, float]:
        start = self._timeline._schedule_base() + float(at)
        resolved = self._timeline._resolve_duration(duration)
        return start, start + resolved

    def _effective_lifetime(self, registered: _RegisteredItem) -> tuple[float, float | None]:
        added_at = registered.added_at
        removed_at = registered.removed_at
        for parent_id in registered.parent_ids:
            parent = self._by_id[parent_id]
            added_at = max(added_at, parent.added_at)
            if parent.removed_at is not None:
                removed_at = (
                    parent.removed_at if removed_at is None else min(removed_at, parent.removed_at)
                )
        return added_at, removed_at

    def _require_alive_for_span(
        self, obj: SceneItem, duration: float | None, at: float = 0.0
    ) -> _RegisteredItem:
        registered = self._require_registered(obj)
        start, end = self._scheduled_span(duration, at)
        added_at, removed_at = self._effective_lifetime(registered)
        if start < added_at - 1e-12:
            raise ValueError(
                f"animation starts at {start:g}, before object lifetime begins at {added_at:g}"
            )
        if removed_at is not None:
            # A positive-duration clip must finish by removal. A zero-duration
            # event at remove_time is outside the half-open lifetime.
            if end > removed_at + 1e-12 or start >= removed_at - 1e-12:
                raise ValueError(f"animation lies outside object lifetime ending at {removed_at:g}")
        return registered

    def _is_alive(self, registered: _RegisteredItem, time: float) -> bool:
        if time < registered.added_at:
            return False
        if registered.removed_at is not None and time >= registered.removed_at:
            return False
        for parent_id in registered.parent_ids:
            parent = self._by_id[parent_id]
            if time < parent.added_at:
                return False
            if parent.removed_at is not None and time >= parent.removed_at:
                return False
        return True

    def _parent_world_transform_authored(self, registered: _RegisteredItem) -> Transform2D:
        """Authored parent-frame pose in world coordinates, excluding Camera2D."""
        result = Transform2D()
        for parent_id in registered.parent_ids:
            parent = self._by_id[parent_id].object_ref
            if not isinstance(parent, SceneObject2D):
                raise TypeError("2D parent chain contains a non-2D object")
            result = result @ parent.transform
        return result

    def _parent_world_transform_at(self, registered: _RegisteredItem, time: float) -> Transform2D:
        """Historical parent-frame pose in world coordinates, excluding Camera2D."""
        result = Transform2D()
        for parent_id in registered.parent_ids:
            parent = self._by_id[parent_id]
            assert isinstance(parent.initial, NodeSnapshot)
            result = result @ self._transform_at(parent_id, parent.initial.transform, time)
        return result

    def world_transform(self, obj: SceneObject2D, *, time: float | None = None) -> Transform2D:
        """Return ``local -> world`` for a registered 2D object or group.

        With ``time=None`` this uses the latest authored target state. Passing a
        time reconstructs the historical transform through the whole parent chain.
        Camera2D is intentionally excluded: camera/view coordinates are not world.
        """
        obj = self._unwrap(obj)
        registered = self._require_registered(obj)
        if time is None:
            return self._parent_world_transform_authored(registered) @ obj.transform
        time = float(time)
        if not self._is_alive(registered, time):
            raise ValueError("object is outside its Scene lifetime at the requested time")
        initial = registered.initial
        if not isinstance(
            initial, (ObjectSnapshot, BatchSnapshot, VectorSnapshot, RasterState, NodeSnapshot)
        ):
            raise TypeError("object has no 2D transform")
        return self._parent_world_transform_at(registered, time) @ self._transform_at(
            registered.object_id, initial.transform, time
        )

    def world_point(
        self, obj: SceneObject2D, point: Point2 = Vec2(), *, time: float | None = None
    ) -> Vec2:
        """Map an object-local point into world coordinates."""
        point = as_vec2(point, name="point")
        return self.world_transform(obj, time=time).apply(point)

    def world_anchor(self, obj: SceneObject2D, anchor=None) -> Vec2:
        """Return one authored visual-bounds anchor in Scene world coordinates."""
        from .layout import CENTER

        obj = self._unwrap(obj)
        registered = self._require_registered(obj)
        chosen = CENTER if anchor is None else anchor
        return self._parent_world_transform_authored(registered).apply(obj.anchor(chosen))

    @property
    def duration(self) -> float:
        """Authored timeline duration in seconds."""
        return float(self._timeline.cursor)

    def render_frame(self, path, time: float = 0.0):
        """Render one absolute scene time without evaluating earlier frames."""
        from .render import render_snapshot

        time = float(time)
        if time < 0:
            raise ValueError("time must be >= 0")
        try:
            return render_snapshot(path, self.evaluate(time), self.canvas)
        finally:
            self._close_media_sources()

    def render_video(self, path, **kwargs):
        """Render all or part of the timeline; ``start``/``end`` are absolute seconds."""
        from .render import render_video

        return render_video(self, path, **kwargs)

    def preview(self, **kwargs):
        """Open the local random-access timeline preview UI.

        By default this blocks until Ctrl-C. Pass ``block=False`` to run the
        preview server on a daemon thread and receive its server handle.
        """
        import inspect

        from .source import infer_script_reload, preview_calls_suppressed

        if preview_calls_suppressed():
            return None
        infer_script_reload(self, inspect.currentframe().f_back)
        from .preview import preview_scene

        return preview_scene(self, **kwargs)

    def render(
        self,
        path=None,
        *,
        time: float | None = None,
        start: float | None = None,
        end: float | None = None,
        **video_kwargs,
    ):
        """Render the scene using its timeline shape to select image or video output.

        A zero-duration scene renders one image at t=0. For an animated scene,
        ``time=...`` renders one random-access frame, while ``start``/``end``
        render only that absolute timeline interval. With no selector, an
        animated scene renders its complete timeline.

        In a Jupyter kernel, ``path`` may be omitted to return an inline PNG or
        MP4 display object. Outside Jupyter an explicit output path is required.
        """
        if time is not None and (start is not None or end is not None):
            raise ValueError("time cannot be combined with start/end")

        if path is None:
            from .notebook import is_notebook, render_inline

            if not is_notebook():
                raise ValueError(
                    "render() without an output path is only available in a Jupyter notebook"
                )
            return render_inline(self, time=time, start=start, end=end, **video_kwargs)

        if time is not None:
            if video_kwargs:
                names = ", ".join(sorted(video_kwargs))
                raise TypeError(f"video options are invalid for frame rendering: {names}")
            return self.render_frame(path, float(time))

        if self.duration <= 0:
            if start is not None or end is not None:
                raise ValueError("start/end require a scene with positive timeline duration")
            if video_kwargs:
                names = ", ".join(sorted(video_kwargs))
                raise TypeError(f"video options are invalid for a static scene: {names}")
            return self.render_frame(path, 0.0)

        resolved_start = 0.0 if start is None else float(start)
        return self.render_video(path, start=resolved_start, end=end, **video_kwargs)

    def _close_media_sources(self) -> None:
        """Release transient decoder processes held by raster sources."""
        seen: set[int] = set()
        for registered in self._registry:
            obj = registered.object_ref
            if not isinstance(obj, RasterObject2D):
                continue
            source = obj.source
            identity = id(source)
            if identity in seen:
                continue
            seen.add(identity)
            source.close()

    def _find_registered(self, obj) -> _RegisteredItem | None:
        registered = self._by_identity.get(id(obj))
        return registered if registered is not None and registered.object_ref is obj else None

    def _require_registered(self, obj) -> _RegisteredItem:
        registered = self._find_registered(obj)
        if registered is None:
            raise ValueError("object must be added to the scene first")
        return registered
