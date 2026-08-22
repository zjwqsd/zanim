from __future__ import annotations

from dataclasses import dataclass, field

from .batch import BatchGeometry, BatchObject2D, DynamicBatchObject2D
from .audio import AudioObject
from .camera import Camera2D
from .camera3d import Camera3D
from .geometry import Object2D
from .group import Group2D
from .interpolation import ObjectInterpolation
from .object import SceneObject2D
from .mesh3d import MeshObject3D
from .raster import RasterObject2D
from .snapshot import (
    BatchSnapshot,
    NodeSnapshot,
    ObjectSnapshot,
    RenderBatch,
    RenderObject,
    RenderRaster,
    RenderSnapshot,
    RenderVector,
    TransientInterpolation,
    RasterSnapshot,
    RasterState,
    VectorSnapshot,
    Camera3DSnapshot, Mesh3DSnapshot, RenderMesh3D,
)
from .space import (
    Canvas, LOCAL, PARENT, WORLD, SE2, Transform2D, TransformFrame, Vec2,
)
from .space3d import Transform3D
from .timeline import (
    BatchClip, Easing, InterpolationClip, OpacityClip, PathTrimClip, RevealClip,
    PlaybackClip, SE2TransformClip, StyleClip, Timeline, TransformClip,
    Transform3DClip, ValueClip,
)
from .value import ScalarValue
from .vector import VectorObject2D

RenderableObject = Object2D | BatchObject2D | VectorObject2D | RasterObject2D
RenderableObject3D = MeshObject3D
SceneObject = RenderableObject | Group2D | Camera2D
SceneItem = SceneObject | MeshObject3D | ScalarValue | AudioObject
InitialSnapshot = ObjectSnapshot | BatchSnapshot | VectorSnapshot | RasterState | Mesh3DSnapshot | NodeSnapshot | float | None


@dataclass(slots=True)
class _RegisteredItem:
    object_id: int
    object_ref: SceneItem
    initial: InitialSnapshot
    parent_ids: tuple[int, ...] = ()
    added_at: float = 0.0
    removed_at: float | None = None


@dataclass(slots=True)
class Scene:
    """Deterministic authoring scene with one registry for all 2D objects."""

    canvas: Canvas = field(default_factory=Canvas)
    fps: int = 60
    timeline: Timeline = field(default_factory=Timeline)
    camera: Camera2D = field(default_factory=Camera2D)
    camera3d: Camera3D = field(default_factory=Camera3D)
    _registry: list[_RegisteredItem] = field(default_factory=list, init=False, repr=False)
    _by_id: dict[int, _RegisteredItem] = field(default_factory=dict, init=False, repr=False)
    _by_identity: dict[int, _RegisteredItem] = field(default_factory=dict, init=False, repr=False)
    _next_object_id: int = field(default=1, init=False, repr=False)
    _world_space_spans: dict[int, list[tuple[float, float]]] = field(default_factory=dict, init=False, repr=False)
    _handles: dict[int, object] = field(default_factory=dict, init=False, repr=False)
    _preview_source_info: object | None = field(default=None, init=False, repr=False)

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
        """Renderable leaves in stable insertion order (compatibility view)."""
        return tuple(
            item.object_ref for item in self._registry
            if isinstance(item.object_ref, (Object2D, BatchObject2D, VectorObject2D, RasterObject2D))
        )

    @property
    def objects3d(self) -> tuple[MeshObject3D, ...]:
        return tuple(
            item.object_ref for item in self._registry
            if isinstance(item.object_ref, MeshObject3D)
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
        added_at = self.timeline.cursor
        handles = []
        for obj in objects:
            if isinstance(obj, Camera2D) or not isinstance(obj, (SceneObject2D, MeshObject3D, ScalarValue, AudioObject)):
                raise TypeError(f"unsupported scene item: {type(obj).__name__}")
            self._register(obj, (), set(), added_at)
            handles.append(self.on(obj))
        return handles[0] if len(handles) == 1 else tuple(handles)

    def on(self, obj):
        """Return the stable Scene-bound handle for one registered item."""
        from .bound import (
            BoundAudio, BoundBatch2D, BoundGroup2D, BoundItem, BoundMesh3D, BoundObject2D,
            BoundRaster2D, BoundValue, BoundVector2D,
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
        elif isinstance(raw, Group2D):
            handle = BoundGroup2D(self, raw)
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
        removed_at = self.timeline.cursor
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
        if self.timeline._parallel_base is not None:
            raise ValueError("add() and remove() are not allowed inside parallel()")

    def _register(self, obj: SceneItem, parents: tuple[int, ...], ancestry: set[int], added_at: float) -> int:
        if self._find_registered(obj) is not None:
            raise ValueError("object is already in this scene")
        identity = id(obj)
        if identity in ancestry:
            raise ValueError("Group2D hierarchy contains a cycle")

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
                raise TypeError("MeshObject3D cannot be a Group2D child")
            initial = Mesh3DSnapshot.from_object(obj)
        elif isinstance(obj, Group2D):
            initial = NodeSnapshot(obj.transform, obj.opacity, obj.z_index)
        elif isinstance(obj, ScalarValue):
            if parents:
                raise TypeError("ScalarValue cannot be a Group2D child")
            initial = obj._initial
        elif isinstance(obj, AudioObject):
            if parents:
                raise TypeError("AudioObject cannot be a Group2D child")
            initial = None
        else:
            raise TypeError(f"unsupported scene item: {type(obj).__name__}")

        registered = _RegisteredItem(object_id, obj, initial, parents, added_at=added_at)
        self._registry.append(registered)
        self._by_id[object_id] = registered
        self._by_identity[identity] = registered

        if isinstance(obj, Group2D):
            next_ancestry = set(ancestry)
            next_ancestry.add(identity)
            child_parents = parents + (object_id,)
            for child in obj.children:
                self._register(child, child_parents, next_ancestry, added_at)
        if hasattr(obj, "_mark_scene_registered"):
            obj._mark_scene_registered()
        return object_id

    def _scheduled_span(self, duration: float | None, at: float) -> tuple[float, float]:
        start = self.timeline._schedule_base() + float(at)
        resolved = self.timeline._resolve_duration(duration)
        return start, start + resolved

    def _effective_lifetime(self, registered: _RegisteredItem) -> tuple[float, float | None]:
        added_at = registered.added_at
        removed_at = registered.removed_at
        for parent_id in registered.parent_ids:
            parent = self._by_id[parent_id]
            added_at = max(added_at, parent.added_at)
            if parent.removed_at is not None:
                removed_at = (
                    parent.removed_at if removed_at is None
                    else min(removed_at, parent.removed_at)
                )
        return added_at, removed_at

    def _require_alive_for_span(self, obj: SceneItem, duration: float | None, at: float = 0.0) -> _RegisteredItem:
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
                raise ValueError(
                    f"animation lies outside object lifetime ending at {removed_at:g}"
                )
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
        if not isinstance(initial, (ObjectSnapshot, BatchSnapshot, VectorSnapshot, RasterState, NodeSnapshot)):
            raise TypeError("object has no 2D transform")
        return (
            self._parent_world_transform_at(registered, time)
            @ self._transform_at(registered.object_id, initial.transform, time)
        )

    def world_point(
        self, obj: SceneObject2D, point: Vec2 = Vec2(), *, time: float | None = None
    ) -> Vec2:
        """Map an object-local point into world coordinates."""
        if not isinstance(point, Vec2):
            raise TypeError("world_point() requires a local Vec2 point")
        return self.world_transform(obj, time=time).apply(point)

    def world_anchor(self, obj: SceneObject2D, anchor=None) -> Vec2:
        """Return one authored visual-bounds anchor in Scene world coordinates."""
        from .layout import CENTER

        obj = self._unwrap(obj)
        registered = self._require_registered(obj)
        chosen = CENTER if anchor is None else anchor
        return self._parent_world_transform_authored(registered).apply(obj.anchor(chosen))

    @staticmethod
    def _require_frame(frame: TransformFrame | None) -> TransformFrame:
        if frame is None:
            raise ValueError("relative transform by= requires explicit frame=LOCAL, PARENT, or WORLD")
        if not isinstance(frame, TransformFrame):
            raise TypeError("frame must be LOCAL, PARENT, or WORLD")
        return frame

    @staticmethod
    def _spans_touch(a0: float, a1: float, b0: float, b1: float) -> bool:
        if a0 == a1 and b0 == b1:
            return abs(a0 - b0) <= 1e-12
        if a0 == a1:
            return b0 - 1e-12 <= a0 < b1 - 1e-12
        if b0 == b1:
            return a0 - 1e-12 <= b0 < a1 - 1e-12
        return a0 < b1 - 1e-12 and b0 < a1 - 1e-12

    def _assert_world_parent_static(
        self, registered: _RegisteredItem, start: float, end: float
    ) -> None:
        for parent_id in registered.parent_ids:
            for clip in self.timeline._channel_clips(TransformClip, parent_id):
                if self._spans_touch(start, end, clip.span.start, clip.span.end):
                    raise ValueError(
                        "WORLD transform on a nested object requires all ancestors "
                        "to remain transform-static over the same span; use LOCAL/PARENT "
                        "for articulated motion"
                    )

    def _assert_no_descendant_world_dependency(
        self, registered: _RegisteredItem, start: float, end: float
    ) -> None:
        for child_id, spans in self._world_space_spans.items():
            child = self._by_id.get(child_id)
            if child is None or registered.object_id not in child.parent_ids:
                continue
            if any(self._spans_touch(start, end, s0, s1) for s0, s1 in spans):
                raise ValueError(
                    "ancestor transform overlaps a nested WORLD transform; "
                    "use LOCAL/PARENT for articulated motion"
                )

    def _record_world_span(self, object_id: int, start: float, end: float) -> None:
        self._world_space_spans.setdefault(object_id, []).append((start, end))

    def _relative_target_2d(
        self, registered: _RegisteredItem, current: Transform2D, delta: Transform2D,
        frame: TransformFrame, start_time: float,
    ) -> Transform2D:
        if frame is LOCAL:
            return current @ delta
        if frame is PARENT:
            return delta @ current
        if frame is WORLD:
            parent_world = self._parent_world_transform_at(registered, start_time)
            delta_parent = parent_world.inverse() @ delta @ parent_world
            return delta_parent @ current
        raise AssertionError(f"unhandled transform frame: {frame}")

    def _transform_to_2d(
        self,
        obj: SceneObject,
        target: Transform2D,
        duration: float,
        easing: Easing,
        at: float,
        *,
        rigid: bool = False,
    ):
        registered = self._require_alive_for_span(obj, duration, at)
        start, end = self._scheduled_span(duration, at)
        self._assert_no_descendant_world_dependency(registered, start, end)
        if isinstance(obj, Camera2D) and obj.is_dynamic:
            raise TypeError("dynamic Camera2D cannot also use transform clips")
        if rigid:
            before_se2 = SE2.from_affine(obj.transform)
            after_se2 = SE2.from_affine(target)
            clip = self.timeline.add_se2_transform(
                registered.object_id, before_se2, after_se2, duration, easing, at
            )
        else:
            clip = self.timeline.add_transform(
                registered.object_id, obj.transform, target, duration, easing, at
            )
        obj._set_scene_state("transform", target)
        return clip

    def _transform_to_3d(
        self, obj: MeshObject3D, target: Transform3D, duration: float,
        easing: Easing, at: float,
    ):
        registered = self._require_alive_for_span(obj, duration, at)
        start, end = self._scheduled_span(duration, at)
        self._assert_no_descendant_world_dependency(registered, start, end)
        clip = self.timeline.add_transform3d(
            registered.object_id, obj.transform, target, duration, easing, at
        )
        obj._set_scene_state("transform", target)
        return clip

    def transform(
        self,
        obj: SceneObject | MeshObject3D,
        *,
        by: Transform2D | Transform3D | SE2 | None = None,
        to: Transform2D | Transform3D | SE2 | None = None,
        frame: TransformFrame | None = None,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate an explicit absolute transform or framed relative transform.

        ``to=`` is a complete local-to-parent target and therefore takes no
        frame. ``by=`` is relative and requires ``frame``:

        - ``PARENT``: ``T' = delta @ T``
        - ``LOCAL``: ``T' = T @ delta``
        - ``WORLD``: world delta conjugated through the authored parent pose

        Passing ``SE2`` selects group-preserving rigid interpolation whenever
        both endpoints are rigid. ``Transform2D`` selects general affine
        interpolation. No object identity is replaced.
        """
        if (by is None) == (to is None):
            raise ValueError("transform() requires exactly one of by= or to=")
        if to is not None and frame is not None:
            raise ValueError("transform(to=...) is absolute and does not accept frame=")

        if isinstance(obj, MeshObject3D):
            if isinstance(to, SE2) or isinstance(by, SE2):
                raise TypeError("SE2 is a 2D rigid transform and cannot animate MeshObject3D")
            if to is not None:
                if not isinstance(to, Transform3D):
                    raise TypeError("MeshObject3D transform target must be Transform3D")
                return self._transform_to_3d(obj, to, duration, easing, at)
            assert by is not None
            if not isinstance(by, Transform3D):
                raise TypeError("MeshObject3D relative transform must be Transform3D")
            resolved = self._require_frame(frame)
            if resolved is PARENT or resolved is WORLD:
                target3d = by @ obj.transform
            elif resolved is LOCAL:
                target3d = obj.transform @ by
            else:
                raise AssertionError
            return self._transform_to_3d(obj, target3d, duration, easing, at)

        if not isinstance(obj, (SceneObject2D, Camera2D)):
            raise TypeError("2D transform requires a 2D scene object")
        registered = self._require_alive_for_span(obj, duration, at)
        current = obj.transform

        if to is not None:
            if isinstance(to, SE2):
                return self._transform_to_2d(
                    obj, to.as_affine(), duration, easing, at, rigid=True
                )
            if not isinstance(to, Transform2D):
                raise TypeError("2D transform target must be Transform2D or SE2")
            return self._transform_to_2d(obj, to, duration, easing, at, rigid=False)

        assert by is not None
        resolved = self._require_frame(frame)
        start, end = self._scheduled_span(duration, at)
        if resolved is WORLD and registered.parent_ids:
            self._assert_world_parent_static(registered, start, end)
        if isinstance(by, SE2):
            self._assert_no_descendant_world_dependency(registered, start, end)
            # Relative SE(2) preserves the authored delta, including winding.
            # ``by=SE2(theta=2*pi)`` therefore performs one full turn instead
            # of collapsing to the identical endpoint pose.
            parent_world = (
                self._parent_world_transform_at(registered, start)
                if resolved is WORLD else None
            )
            parent_world_inv = parent_world.inverse() if parent_world is not None else None

            def relative_rigid(alpha: float) -> Transform2D:
                delta = SE2(
                    theta=by.theta * alpha,
                    translation=by.translation * alpha,
                ).as_affine()
                if resolved is LOCAL:
                    return current @ delta
                if resolved is PARENT:
                    return delta @ current
                assert parent_world is not None and parent_world_inv is not None
                return parent_world_inv @ delta @ parent_world @ current

            clip = self.timeline.add_transform_function(
                registered.object_id, relative_rigid, current, duration, easing, at
            )
            obj._set_scene_state("transform", clip.after)
            if resolved is WORLD and registered.parent_ids:
                self._record_world_span(registered.object_id, start, end)
            return clip
        if not isinstance(by, Transform2D):
            raise TypeError("2D relative transform must be Transform2D or SE2")
        target = self._relative_target_2d(registered, current, by, resolved, start)
        clip = self._transform_to_2d(obj, target, duration, easing, at, rigid=False)
        if resolved is WORLD and registered.parent_ids:
            self._record_world_span(registered.object_id, start, end)
        return clip

    def set_transform(
        self,
        obj: SceneObject | MeshObject3D,
        *,
        to: Transform2D | Transform3D | SE2,
        at: float = 0.0,
    ):
        """Set one complete transform instantaneously and seekably."""
        return self.transform(obj, to=to, duration=0.0, easing=Easing.LINEAR, at=at)

    def move(
        self,
        obj: SceneObject2D,
        *,
        by: Vec2 | None = None,
        to: Vec2 | None = None,
        frame: TransformFrame | None = None,
        anchor=None,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Translate one object with explicit relative/absolute semantics.

        ``by=`` requires a frame. ``to=`` is an absolute world-space visual
        placement; its ``anchor`` defaults explicitly to ``CENTER``.
        """
        from .layout import CENTER

        if isinstance(obj, Camera2D):
            raise TypeError("move() requires a bounded 2D object; use transform() for Camera2D")
        if (by is None) == (to is None):
            raise ValueError("move() requires exactly one of by= or to=")
        chosen_anchor = CENTER if anchor is None else anchor
        if by is not None:
            if anchor is not None:
                raise ValueError("move(by=...) does not accept anchor=")
            if not isinstance(by, Vec2):
                raise TypeError("move(by=...) requires Vec2")
            return self.transform(
                obj, by=Transform2D.translation(by.x, by.y), frame=self._require_frame(frame),
                duration=duration, easing=easing, at=at,
            )
        if frame is not None:
            raise ValueError("move(to=...) is an absolute world target and does not accept frame=")
        if not isinstance(to, Vec2):
            raise TypeError("move(to=...) requires Vec2")
        registered = self._require_registered(obj)
        anchor_parent = obj.anchor(chosen_anchor)
        current_world = self._parent_world_transform_authored(registered).apply(anchor_parent)
        delta_world = to - current_world
        return self.transform(
            obj, by=Transform2D.translation(delta_world.x, delta_world.y), frame=WORLD,
            duration=duration, easing=easing, at=at,
        )

    def rotate(
        self,
        obj: SceneObject2D,
        *,
        by: float,
        frame: TransformFrame | None = None,
        about: Vec2 | None = None,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Rotate in LOCAL/PARENT/WORLD, or about one explicit world point."""
        if isinstance(obj, Camera2D):
            raise TypeError("rotate() requires a bounded 2D object; use transform() for Camera2D")
        if about is not None:
            if frame is not None:
                raise ValueError("rotate() accepts either frame= or about=, not both")
            if not isinstance(about, Vec2):
                raise TypeError("rotate(about=...) requires Vec2")
            registered = self._require_alive_for_span(obj, duration, at)
            start, end = self._scheduled_span(duration, at)
            if registered.parent_ids:
                self._assert_world_parent_static(registered, start, end)
            self._assert_no_descendant_world_dependency(registered, start, end)
            parent_world = self._parent_world_transform_at(registered, start)
            parent_world_inv = parent_world.inverse()
            current = obj.transform
            angle = float(by)

            def around_world_pivot(alpha: float) -> Transform2D:
                op_world = (
                    Transform2D.translation(about.x, about.y)
                    @ Transform2D.rotation(angle * alpha)
                    @ Transform2D.translation(-about.x, -about.y)
                )
                return parent_world_inv @ op_world @ parent_world @ current

            clip = self.timeline.add_transform_function(
                registered.object_id, around_world_pivot, current, duration, easing, at
            )
            obj._set_scene_state("transform", clip.after)
            if registered.parent_ids:
                self._record_world_span(registered.object_id, start, end)
            return clip
        resolved = self._require_frame(frame)
        return self.transform(
            obj, by=SE2(theta=float(by)), frame=resolved,
            duration=duration, easing=easing, at=at,
        )

    def scale(
        self,
        obj: SceneObject2D,
        *,
        by: float,
        frame: TransformFrame | None = None,
        about: Vec2 | None = None,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Scale in LOCAL/PARENT/WORLD, or about one explicit world point."""
        factor = float(by)
        if factor < 0.0:
            raise ValueError("scale(by=...) must be >= 0")
        if isinstance(obj, Camera2D):
            raise TypeError("scale() requires a bounded 2D object; use transform() for Camera2D")
        if about is not None:
            if frame is not None:
                raise ValueError("scale() accepts either frame= or about=, not both")
            if not isinstance(about, Vec2):
                raise TypeError("scale(about=...) requires Vec2")
            op = (
                Transform2D.translation(about.x, about.y)
                @ Transform2D.scaling(factor)
                @ Transform2D.translation(-about.x, -about.y)
            )
            return self.transform(obj, by=op, frame=WORLD, duration=duration, easing=easing, at=at)
        resolved = self._require_frame(frame)
        return self.transform(
            obj, by=Transform2D.scaling(factor), frame=resolved,
            duration=duration, easing=easing, at=at,
        )

    def transform_function(
        self,
        obj: SceneObject | MeshObject3D,
        provider,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate with a pure ``alpha -> complete Transform`` provider.

        2D providers may return ``Transform2D`` or ``SE2``. The result is always
        a complete local-to-parent transform, never an incremental delta.
        """
        return self._transform_function(obj, provider, duration, easing, at)

    def _transform_function(
        self,
        obj: SceneObject | MeshObject3D,
        provider,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        registered = self._require_alive_for_span(obj, duration, at)
        if isinstance(obj, MeshObject3D):
            clip = self.timeline.add_transform3d_function(
                registered.object_id, provider, obj.transform, duration, easing, at
            )
            obj._set_scene_state("transform", clip.after)
            return clip
        if isinstance(obj, Camera2D) and obj.is_dynamic:
            raise TypeError("dynamic Camera2D cannot also use transform clips")

        def affine_provider(alpha: float) -> Transform2D:
            value = provider(alpha)
            if isinstance(value, SE2):
                return value.as_affine()
            if isinstance(value, Transform2D):
                return value
            raise TypeError("2D transform function must return Transform2D or SE2")

        clip = self.timeline.add_transform_function(
            registered.object_id, affine_provider, obj.transform, duration, easing, at
        )
        obj._set_scene_state("transform", clip.after)
        return clip

    def _opacity_to(
        self, obj: SceneObject2D | MeshObject3D, target: float, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> OpacityClip:
        if isinstance(obj, Camera2D):
            raise TypeError("Camera2D only participates in the transform channel")
        registered = self._require_alive_for_span(obj, duration, at)
        clip = self.timeline.add_opacity(registered.object_id, obj.opacity, target, duration, easing, at)
        obj._set_scene_state("opacity", float(target))
        return clip

    def fade_in(
        self, obj: SceneObject2D | MeshObject3D, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> OpacityClip:
        """Fade an explicitly transparent object from opacity 0 to 1.

        ``fade_in`` never invents a hidden pre-state. Set ``opacity=0`` before
        ``add()`` (or reach 0 through an earlier authored animation) first.
        Use ``opacity(..., to=...)`` for arbitrary opacity transitions.
        """
        if isinstance(obj, Camera2D):
            raise TypeError("Camera2D only participates in the transform channel")
        if abs(float(obj.opacity)) > 1e-12:
            raise ValueError(
                f"fade_in() requires current opacity to be 0; current opacity is {obj.opacity:g}"
            )
        return self._opacity_to(obj, 1.0, duration, easing, at)

    def fade_out(self, obj: SceneObject2D | MeshObject3D, duration: float | None = None, easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0) -> OpacityClip:
        if isinstance(obj, Camera2D):
            raise TypeError("Camera2D only participates in the transform channel")
        registered = self._require_alive_for_span(obj, duration, at)
        clip = self.timeline.add_opacity(registered.object_id, obj.opacity, 0.0, duration, easing, at)
        obj._set_scene_state("opacity", 0.0)
        return clip

    def _style_to(
        self, obj: Object2D, target, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> StyleClip:
        registered = self._require_alive_for_span(obj, duration, at)
        clip = self.timeline.add_style(registered.object_id, obj.style, target, duration, easing, at)
        obj._set_scene_state("style", target)
        return clip

    def _trim_to(
        self, obj: Object2D, target: float, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> PathTrimClip:
        registered = self._require_alive_for_span(obj, duration, at)
        clip = self.timeline.add_path_trim(registered.object_id, obj.trim, target, duration, easing, at)
        obj._set_scene_state("trim", float(target))
        return clip

    def create(
        self, obj: Object2D | VectorObject2D, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ):
        """Reveal an object whose authored creation state is explicitly zero.

        Geometry requires ``trim=0``; vector/text/math objects require
        ``reveal=0``. The call animates that current state to 1 and never
        rewrites the object's history before the clip starts.
        """
        if isinstance(obj, VectorObject2D):
            return self._reveal(obj, duration, easing, at)
        if not isinstance(obj, Object2D):
            raise TypeError("create() requires Object2D or VectorObject2D")
        if abs(float(obj.trim)) > 1e-12:
            raise ValueError(
                f"create() requires current trim to be 0; current trim is {obj.trim:g}"
            )
        return self._trim_to(obj, 1.0, duration, easing, at)

    def _value_to(
        self, value: ScalarValue, target: float, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> ValueClip:
        registered = self._require_alive_for_span(value, duration, at)
        clip = self.timeline.add_value(registered.object_id, value.value, target, duration, easing, at)
        value._clips.append(clip)
        value._set_scene_state("value", float(target))
        return clip

    def _media(
        self, obj: RasterObject2D | AudioObject, duration: float | None = None, *,
        source_start: float = 0.0, speed: float = 1.0, loop: bool = False, at: float = 0.0,
    ) -> PlaybackClip:
        registered = self._require_registered(obj)
        source_duration = obj.source.duration
        if duration is None:
            if source_duration is None:
                raise ValueError("static media playback requires an explicit duration")
            duration = (source_duration - float(source_start)) / float(speed)
        registered = self._require_alive_for_span(obj, duration, at)
        return self.timeline.add_playback(
            registered.object_id, duration, source_start=source_start, speed=speed,
            loop=loop, source_duration=source_duration, at=at,
        )

    def _batch_to(
        self,
        obj: BatchObject2D,
        target: BatchGeometry,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> BatchClip:
        registered = self._require_alive_for_span(obj, duration, at)
        if not isinstance(obj, BatchObject2D):
            raise TypeError("batch() requires a BatchObject2D")
        if isinstance(obj, DynamicBatchObject2D):
            raise TypeError("DynamicBatchObject2D owns its batch channel and cannot use BatchClip")
        clip = self.timeline.add_batch(
            registered.object_id, obj.batch, target, duration, easing, at
        )
        obj._set_scene_state("batch", target)
        return clip

    def _reveal(
        self,
        obj: VectorObject2D,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> RevealClip:
        if not isinstance(obj, VectorObject2D):
            raise TypeError("reveal() requires a VectorObject2D")
        if abs(float(obj.reveal)) > 1e-12:
            raise ValueError(
                f"reveal() requires current reveal to be 0; current reveal is {obj.reveal:g}"
            )
        registered = self._require_alive_for_span(obj, duration, at)
        clip = self.timeline.add_reveal(
            registered.object_id, duration=duration, easing=easing, at=at,
            before=obj.reveal, after=1.0,
        )
        obj._set_scene_state("reveal", 1.0)
        return clip

    def _interpolate(
        self,
        source: Object2D,
        target: Object2D,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> InterpolationClip:
        self._require_alive_for_span(source, duration, at)
        self._require_alive_for_span(target, duration, at)
        return self.timeline.add_interpolation(
            ObjectInterpolation.from_objects(source, target), duration, easing, at
        )

    def reveal(
        self, obj: VectorObject2D, *, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> RevealClip:
        return self._reveal(obj, duration, easing, at)

    def opacity(
        self, obj: SceneObject2D | MeshObject3D, *, to: float,
        duration: float | None = None, easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> OpacityClip:
        return self._opacity_to(obj, to, duration, easing, at)

    def style(
        self, obj: Object2D, *, to, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> StyleClip:
        return self._style_to(obj, to, duration, easing, at)

    def trim(
        self, obj: Object2D, *, to: float, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> PathTrimClip:
        return self._trim_to(obj, to, duration, easing, at)

    def value(
        self, value: ScalarValue, *, to: float, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> ValueClip:
        return self._value_to(value, to, duration, easing, at)

    def media(
        self, obj: RasterObject2D | AudioObject, duration: float | None = None, *,
        source_start: float = 0.0, speed: float = 1.0, loop: bool = False, at: float = 0.0,
    ) -> PlaybackClip:
        return self._media(
            obj, duration, source_start=source_start, speed=speed, loop=loop, at=at
        )

    def batch(
        self, obj: BatchObject2D, *, to: BatchGeometry, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> BatchClip:
        return self._batch_to(obj, to, duration, easing, at)

    def interpolate(
        self, source: Object2D, target: Object2D, *, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> InterpolationClip:
        """Render one extra transient interpolation between two existing objects.

        This operation is intentionally pure with respect to both endpoints:
        it changes no property, visibility, identity, or lifetime of ``source``
        or ``target``. The original objects keep rendering according to their
        own state while the transient exists.
        """
        source = self._unwrap(source)
        target = self._unwrap(target)
        return self._interpolate(source, target, duration, easing, at)

    def replace(
        self, source: Object2D, target: Object2D, *, duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
    ):
        """Hand off lifetime and return the newly active target handle.

        At the current cursor, ``source`` leaves the Scene. During ``duration``
        only the explicit source->target transient represents the handoff. At
        the clip end, ``target`` begins its Scene lifetime with exactly the state
        it was declared with. Neither endpoint's properties are rewritten.

        Replacement is a lifetime boundary and is therefore not allowed inside
        ``parallel()``. For now the source must be top-level so the target's
        parentage is never guessed silently.
        """
        self._require_lifetime_boundary()
        source = self._unwrap(source)
        target = self._unwrap(target)
        if not isinstance(source, Object2D) or not isinstance(target, Object2D):
            raise TypeError("replace() currently requires Object2D endpoints")
        source_registered = self._require_registered(source)
        if source_registered.parent_ids:
            raise ValueError("replace() requires a top-level source; nested parentage must be explicit")
        if self._find_registered(target) is not None:
            raise ValueError("replace() target must not already be in the scene")
        start = self.timeline.cursor
        added_at, removed_at = self._effective_lifetime(source_registered)
        if start < added_at or (removed_at is not None and start >= removed_at):
            raise ValueError("replace() source is not alive at the current cursor")
        interpolation = ObjectInterpolation.from_objects(source, target)
        clip = self.timeline.add_interpolation(interpolation, duration, easing, at=0.0)
        source_registered.removed_at = clip.span.start
        self._register(target, (), set(), clip.span.end)
        return self.on(target)

    def layout(
        self,
        *objects,
        to,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate existing 2D objects to an explicit layout specification.

        Passing one Group2D lays out its direct children independently; passing
        ordinary objects lays out exactly those objects. Layout only determines
        target translations. Object identity, scale, rotation and style remain
        unchanged.
        """
        objects = tuple(self._unwrap(obj) for obj in objects)
        if len(objects) == 1 and isinstance(objects[0], Group2D):
            items = tuple(objects[0].children)
        else:
            items = tuple(objects)
        if not items:
            raise ValueError("layout() requires at least one object")
        if any(isinstance(obj, Group2D) for obj in items):
            raise TypeError("layout() expects 2D leaf objects, or one Group2D")
        targets = to.targets(*items)

        def schedule():
            return tuple(
                self.transform(obj, to=target, duration=duration, easing=easing, at=at)
                for obj, target in zip(items, targets)
            )

        if self.timeline._parallel_base is not None:
            return schedule()
        with self.parallel():
            return schedule()

    def parallel(self, duration: float | None = None):
        """Schedule clips from one cursor, optionally sharing a duration default.

        ``duration=...`` only supplies the default for calls that omit their own
        duration. Explicit per-clip durations always win; ``at=`` remains a
        relative offset from the common parallel base cursor.
        """
        return self.timeline.parallel(duration=duration)

    def wait(self, duration: float = 1.0):
        return self.timeline.wait(duration)

    @property
    def duration(self) -> float:
        """Authored timeline duration in seconds."""
        return float(self.timeline.cursor)

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
        from .preview import preview_scene
        return preview_scene(self, **kwargs)

    def render(
        self, path, *, time: float | None = None,
        start: float | None = None, end: float | None = None, **video_kwargs
    ):
        """Render the scene using its timeline shape to select image or video output.

        A zero-duration scene renders one image at t=0. For an animated scene,
        ``time=...`` renders one random-access frame, while ``start``/``end``
        render only that absolute timeline interval. With no selector, an
        animated scene renders its complete timeline.
        """
        if time is not None and (start is not None or end is not None):
            raise ValueError("time cannot be combined with start/end")

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
        return self.render_video(
            path, start=resolved_start, end=end, **video_kwargs
        )

    def evaluate(self, time: float) -> RenderSnapshot:
        objects: list[RenderObject] = []
        batches: list[RenderBatch] = []
        vectors: list[RenderVector] = []
        rasters: list[RenderRaster] = []
        meshes3d: list[RenderMesh3D] = []
        for registered in self._registry:
            if not self._is_alive(registered, time):
                continue
            obj = registered.object_ref
            if isinstance(obj, Object2D):
                objects.append(self._evaluate_object(registered, obj, time))
            elif isinstance(obj, BatchObject2D):
                batches.append(self._evaluate_batch(registered, obj, time))
            elif isinstance(obj, VectorObject2D):
                vectors.append(self._evaluate_vector(registered, obj, time))
            elif isinstance(obj, RasterObject2D):
                rendered = self._evaluate_raster(registered, obj, time)
                if rendered is not None:
                    rasters.append(rendered)
            elif isinstance(obj, MeshObject3D):
                meshes3d.append(self._evaluate_mesh3d(registered, obj, time))

        transients = tuple(
            TransientInterpolation(clip.interpolation, clip.alpha(time))
            for clip in self.timeline.clips
            if isinstance(clip, InterpolationClip) and clip.span.contains(time)
        )
        return RenderSnapshot(
            time, tuple(objects), tuple(batches), tuple(vectors), tuple(rasters), transients,
            tuple(meshes3d), Camera3DSnapshot.from_camera(self.camera3d) if meshes3d else None,
        )

    def _context_at(self, registered: _RegisteredItem, time: float) -> tuple[Transform2D, float, int]:
        camera_registered = self._by_id[0]
        camera_initial = camera_registered.initial
        assert isinstance(camera_initial, NodeSnapshot)
        camera = camera_registered.object_ref
        assert isinstance(camera, Camera2D)
        if camera.is_dynamic:
            if self.timeline._channel_clips(TransformClip, 0):
                raise RuntimeError("dynamic Camera2D cannot also have TransformClip entries")
            transform = camera.transform_at(time, camera_initial.transform)
        else:
            transform = self._transform_at(0, camera_initial.transform, time)
        opacity = 1.0
        z_index = 0
        for parent_id in registered.parent_ids:
            parent = self._by_id[parent_id]
            assert isinstance(parent.initial, NodeSnapshot)
            transform = transform @ self._transform_at(parent_id, parent.initial.transform, time)
            opacity *= self._opacity_at(parent_id, parent.initial.opacity, time)
            z_index += parent.initial.z_index
        return transform, opacity, z_index

    def _evaluate_object(self, registered: _RegisteredItem, obj: Object2D, time: float) -> RenderObject:
        initial = registered.initial
        assert isinstance(initial, ObjectSnapshot)
        parent_transform, parent_opacity, parent_z = self._context_at(registered, time)
        trim = self._path_trim_at(registered.object_id, initial.trim, time)
        geometry = obj._geometry_at(time, initial.geometry)
        style = self._style_at(registered.object_id, initial.style, time)
        if trim < 1.0:
            from .path import trim_geometry, trim_style
            geometry = trim_geometry(geometry, trim)
            style = trim_style(style, trim)
        return RenderObject(
            registered.object_id,
            ObjectSnapshot(
                geometry=geometry,
                transform=parent_transform @ self._transform_at(registered.object_id, initial.transform, time),
                style=style,
                opacity=parent_opacity * self._opacity_at(registered.object_id, initial.opacity, time),
                z_index=parent_z + initial.z_index,
                trim=trim,
            ),
        )

    def _evaluate_batch(self, registered: _RegisteredItem, obj: BatchObject2D, time: float) -> RenderBatch:
        initial = registered.initial
        assert isinstance(initial, BatchSnapshot)
        parent_transform, parent_opacity, parent_z = self._context_at(registered, time)
        transform = parent_transform @ self._transform_at(registered.object_id, initial.transform, time)
        opacity = parent_opacity * self._opacity_at(registered.object_id, initial.opacity, time)
        z_index = parent_z + initial.z_index
        if isinstance(obj, DynamicBatchObject2D):
            if self.timeline._channel_clips(BatchClip, registered.object_id):
                raise RuntimeError("DynamicBatchObject2D cannot also have BatchClip entries")
            batch = obj._batch_at(time, initial.batch)
            return RenderBatch(registered.object_id, BatchSnapshot(batch, transform, opacity, z_index))
        batch, active = self._batch_at(registered.object_id, initial.batch, time)
        if active is None:
            return RenderBatch(registered.object_id, BatchSnapshot(batch, transform, opacity, z_index))
        return RenderBatch(
            registered.object_id,
            BatchSnapshot(active.before, transform, opacity, z_index),
            target=BatchSnapshot(active.after, transform, opacity, z_index),
            alpha=active.alpha(time),
        )

    def _evaluate_vector(self, registered: _RegisteredItem, obj: VectorObject2D, time: float) -> RenderVector:
        initial = registered.initial
        assert isinstance(initial, VectorSnapshot)
        parent_transform, parent_opacity, parent_z = self._context_at(registered, time)
        return RenderVector(
            registered.object_id,
            VectorSnapshot(
                document=obj._document_at(time, initial.document),
                transform=parent_transform @ self._transform_at(registered.object_id, initial.transform, time),
                reveal=self._reveal_at(registered.object_id, initial.reveal, time),
                opacity=parent_opacity * self._opacity_at(registered.object_id, initial.opacity, time),
                z_index=parent_z + initial.z_index,
            ),
        )

    def _evaluate_raster(
        self, registered: _RegisteredItem, obj: RasterObject2D, time: float
    ) -> RenderRaster | None:
        initial = registered.initial
        assert isinstance(initial, RasterState)
        source_time = self._playback_time_at(registered.object_id, obj.source.duration, time)
        if source_time is None:
            return None
        parent_transform, parent_opacity, parent_z = self._context_at(registered, time)
        return RenderRaster(
            registered.object_id,
            RasterSnapshot(
                frame=obj.frame_at(source_time), width=initial.width, height=initial.height,
                transform=parent_transform @ self._transform_at(registered.object_id, initial.transform, time),
                opacity=parent_opacity * self._opacity_at(registered.object_id, initial.opacity, time),
                z_index=parent_z + initial.z_index,
            ),
        )

    def _evaluate_mesh3d(
        self, registered: _RegisteredItem, obj: MeshObject3D, time: float
    ) -> RenderMesh3D:
        initial = registered.initial
        assert isinstance(initial, Mesh3DSnapshot)
        return RenderMesh3D(
            registered.object_id,
            Mesh3DSnapshot(
                initial.mesh,
                self._transform3d_at(registered.object_id, initial.transform, time),
                initial.color,
                self._opacity_at(registered.object_id, initial.opacity, time),
                initial.geometry_transform,
            ),
        )

    def _playback_time_at(self, object_id: int, source_duration: float | None, time: float) -> float | None:
        clips = self.timeline._channel_clips(PlaybackClip, object_id)
        if not clips:
            return 0.0
        for clip in clips:
            if clip.span.contains(time):
                return clip.source_time(time)
        return None

    def _audio_playbacks(self):
        for registered in self._registry:
            obj = registered.object_ref
            if not isinstance(obj, AudioObject):
                continue
            for clip in self.timeline._channel_clips(PlaybackClip, registered.object_id):
                yield obj, clip

    def _transform_at(self, object_id: int, initial: Transform2D, time: float) -> Transform2D:
        value = initial
        for clip in self.timeline._channel_clips(TransformClip, object_id):
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                value = clip.after.as_affine() if isinstance(clip, SE2TransformClip) else clip.after
                continue
            return clip.sample(time)
        return value

    def _transform3d_at(self, object_id: int, initial: Transform3D, time: float) -> Transform3D:
        value = initial
        for clip in self.timeline._channel_clips(Transform3DClip, object_id):
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                value = clip.after
                continue
            return clip.sample(time)
        return value

    def _opacity_at(self, object_id: int, initial: float, time: float) -> float:
        return self._scalar_object_channel_at(OpacityClip, object_id, initial, time)

    def _path_trim_at(self, object_id: int, initial: float, time: float) -> float:
        return self._scalar_object_channel_at(PathTrimClip, object_id, initial, time)

    def _scalar_object_channel_at(self, clip_type, object_id: int, initial: float, time: float) -> float:
        clips = self.timeline._channel_clips(clip_type, object_id)
        if not clips:
            return initial
        if time < clips[0].span.start:
            return clips[0].before
        value = initial
        for clip in clips:
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                value = clip.after
                continue
            return clip.sample(time)
        return value

    def _style_at(self, object_id: int, initial, time: float):
        clips = self.timeline._channel_clips(StyleClip, object_id)
        if not clips:
            return initial
        if time < clips[0].span.start:
            return clips[0].before
        value = initial
        for clip in clips:
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                value = clip.after
                continue
            return clip.sample(time)
        return value

    def _batch_at(self, object_id: int, initial: BatchGeometry, time: float) -> tuple[BatchGeometry, BatchClip | None]:
        value = initial
        for clip in self.timeline._channel_clips(BatchClip, object_id):
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                value = clip.after
                continue
            return value, clip
        return value, None

    def _reveal_at(self, object_id: int, initial: float, time: float) -> float:
        clips = self.timeline._channel_clips(RevealClip, object_id)
        if not clips:
            return initial
        if time < clips[0].span.start:
            return clips[0].before
        value = initial
        for clip in clips:
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                value = clip.after
                continue
            return clip.sample(time)
        return value


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
