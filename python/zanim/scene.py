from __future__ import annotations

from dataclasses import dataclass, field

from .batch import BatchGeometry, BatchObject2D
from .camera import Camera2D
from .geometry import Object2D
from .group import Group2D
from .interpolation import ObjectInterpolation
from .object import SceneObject2D
from .snapshot import (
    BatchSnapshot,
    NodeSnapshot,
    ObjectSnapshot,
    RenderBatch,
    RenderObject,
    RenderSnapshot,
    RenderVector,
    TransientInterpolation,
    VectorSnapshot,
)
from .space import Canvas, Transform2D
from .timeline import (
    BatchClip, Easing, InterpolationClip, OpacityClip, PathTrimClip, RevealClip,
    StyleClip, Timeline, TransformClip, ValueClip,
)
from .value import ScalarValue
from .vector import VectorObject2D

RenderableObject = Object2D | BatchObject2D | VectorObject2D
SceneObject = RenderableObject | Group2D | Camera2D
SceneItem = SceneObject | ScalarValue
InitialSnapshot = ObjectSnapshot | BatchSnapshot | VectorSnapshot | NodeSnapshot | float


@dataclass(frozen=True, slots=True)
class _RegisteredItem:
    object_id: int
    object_ref: SceneItem
    initial: InitialSnapshot
    parent_ids: tuple[int, ...] = ()


@dataclass(slots=True)
class Scene:
    """Deterministic authoring scene with one registry for all 2D objects."""

    canvas: Canvas = field(default_factory=Canvas)
    fps: int = 60
    timeline: Timeline = field(default_factory=Timeline)
    camera: Camera2D = field(default_factory=Camera2D)
    _registry: list[_RegisteredItem] = field(default_factory=list, init=False, repr=False)
    _by_id: dict[int, _RegisteredItem] = field(default_factory=dict, init=False, repr=False)
    _next_object_id: int = field(default=1, init=False, repr=False)

    def __post_init__(self) -> None:
        # Camera uses the reserved id 0 so ordinary insertion order remains 1+.
        initial = NodeSnapshot(self.camera.transform, self.camera.opacity, self.camera.z_index)
        registered = _RegisteredItem(0, self.camera, initial)
        self._registry.append(registered)
        self._by_id[0] = registered

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
            if isinstance(item.object_ref, (Object2D, BatchObject2D, VectorObject2D))
        )

    @property
    def items(self) -> tuple[SceneItem, ...]:
        """All registered authoring objects except the implicit camera."""
        return tuple(item.object_ref for item in self._registry if item.object_id != 0)

    def add(self, *objects: SceneItem) -> "Scene":
        for obj in objects:
            if isinstance(obj, Camera2D) or not isinstance(obj, (SceneObject2D, ScalarValue)):
                raise TypeError(f"unsupported scene item: {type(obj).__name__}")
            self._register(obj, (), set())
        return self

    def _register(self, obj: SceneItem, parents: tuple[int, ...], ancestry: set[int]) -> int:
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
        elif isinstance(obj, Group2D):
            initial = NodeSnapshot(obj.transform, obj.opacity, obj.z_index)
        elif isinstance(obj, ScalarValue):
            if parents:
                raise TypeError("ScalarValue cannot be a Group2D child")
            initial = obj._initial
        else:
            raise TypeError(f"unsupported scene item: {type(obj).__name__}")

        registered = _RegisteredItem(object_id, obj, initial, parents)
        self._registry.append(registered)
        self._by_id[object_id] = registered

        if isinstance(obj, Group2D):
            next_ancestry = set(ancestry)
            next_ancestry.add(identity)
            child_parents = parents + (object_id,)
            for child in obj.children:
                self._register(child, child_parents, next_ancestry)
        return object_id

    def play_transform(
        self,
        obj: SceneObject,
        target: Transform2D,
        duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> TransformClip:
        if isinstance(obj, Camera2D) and obj.is_dynamic:
            raise TypeError("dynamic Camera2D cannot also use TransformClip")
        registered = self._require_registered(obj)
        clip = self.timeline.add_transform(
            registered.object_id, obj.transform, target, duration, easing, at
        )
        obj.transform = target
        return clip

    def play_opacity(
        self, obj: SceneObject2D, target: float, duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> OpacityClip:
        if isinstance(obj, Camera2D):
            raise TypeError("Camera2D only participates in the transform channel")
        registered = self._require_registered(obj)
        clip = self.timeline.add_opacity(registered.object_id, obj.opacity, target, duration, easing, at)
        obj.opacity = float(target)
        return clip

    def fade_in(
        self, obj: SceneObject2D, duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0, target: float = 1.0,
    ) -> OpacityClip:
        if isinstance(obj, Camera2D):
            raise TypeError("Camera2D only participates in the transform channel")
        registered = self._require_registered(obj)
        clip = self.timeline.add_opacity(registered.object_id, 0.0, target, duration, easing, at)
        obj.opacity = float(target)
        return clip

    def fade_out(self, obj: SceneObject2D, duration: float = 1.0, easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0) -> OpacityClip:
        if isinstance(obj, Camera2D):
            raise TypeError("Camera2D only participates in the transform channel")
        registered = self._require_registered(obj)
        clip = self.timeline.add_opacity(registered.object_id, obj.opacity, 0.0, duration, easing, at)
        obj.opacity = 0.0
        return clip

    def play_style(
        self, obj: Object2D, target, duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> StyleClip:
        registered = self._require_registered(obj)
        clip = self.timeline.add_style(registered.object_id, obj.style, target, duration, easing, at)
        obj.style = target
        return clip

    def play_path_trim(
        self, obj: Object2D, target: float, duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> PathTrimClip:
        registered = self._require_registered(obj)
        clip = self.timeline.add_path_trim(registered.object_id, obj.trim, target, duration, easing, at)
        obj.trim = float(target)
        return clip

    def create(
        self, obj: Object2D | VectorObject2D, duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ):
        if isinstance(obj, VectorObject2D):
            return self.play_reveal(obj, duration, easing, at)
        registered = self._require_registered(obj)
        clip = self.timeline.add_path_trim(registered.object_id, 0.0, 1.0, duration, easing, at)
        obj.trim = 1.0
        return clip

    def play_value(
        self, value: ScalarValue, target: float, duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP, at: float = 0.0,
    ) -> ValueClip:
        registered = self._require_registered(value)
        clip = self.timeline.add_value(registered.object_id, value.value, target, duration, easing, at)
        value._clips.append(clip)
        value.value = float(target)
        return clip

    def play_batch(
        self,
        obj: BatchObject2D,
        target: BatchGeometry,
        duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> BatchClip:
        registered = self._require_registered(obj)
        if not isinstance(obj, BatchObject2D):
            raise TypeError("play_batch requires a BatchObject2D")
        clip = self.timeline.add_batch(
            registered.object_id, obj.batch, target, duration, easing, at
        )
        obj.batch = target
        return clip

    def play_reveal(
        self,
        obj: VectorObject2D,
        duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> RevealClip:
        registered = self._require_registered(obj)
        if not isinstance(obj, VectorObject2D):
            raise TypeError("play_reveal requires a VectorObject2D")
        clip = self.timeline.add_reveal(
            registered.object_id, duration=duration, easing=easing, at=at,
            before=0.0, after=1.0,
        )
        obj.reveal = 1.0
        return clip

    def play_interpolation(
        self,
        source: Object2D,
        target: Object2D,
        duration: float = 1.0,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> InterpolationClip:
        self._require_registered(source)
        self._require_registered(target)
        return self.timeline.add_interpolation(
            ObjectInterpolation.from_objects(source, target), duration, easing, at
        )

    def parallel(self):
        return self.timeline.parallel()

    def wait(self, duration: float = 1.0):
        return self.timeline.wait(duration)

    def render_frame(self, path, time: float):
        from .render import render_snapshot
        return render_snapshot(path, self.evaluate(time), self.canvas)

    def render_video(self, path, **kwargs):
        from .render import render_video
        return render_video(self, path, **kwargs)

    def evaluate(self, time: float) -> RenderSnapshot:
        objects: list[RenderObject] = []
        batches: list[RenderBatch] = []
        vectors: list[RenderVector] = []
        for registered in self._registry:
            obj = registered.object_ref
            if isinstance(obj, Object2D):
                objects.append(self._evaluate_object(registered, obj, time))
            elif isinstance(obj, BatchObject2D):
                batches.append(self._evaluate_batch(registered, obj, time))
            elif isinstance(obj, VectorObject2D):
                vectors.append(self._evaluate_vector(registered, obj, time))

        transients = tuple(
            TransientInterpolation(clip.interpolation, clip.alpha(time))
            for clip in self.timeline.clips
            if isinstance(clip, InterpolationClip) and clip.span.contains(time)
        )
        return RenderSnapshot(time, tuple(objects), tuple(batches), tuple(vectors), transients)

    def _context_at(self, registered: _RegisteredItem, time: float) -> tuple[Transform2D, float, int]:
        camera_registered = self._by_id[0]
        camera_initial = camera_registered.initial
        assert isinstance(camera_initial, NodeSnapshot)
        camera = camera_registered.object_ref
        assert isinstance(camera, Camera2D)
        if camera.is_dynamic:
            if any(isinstance(clip, TransformClip) and clip.object_id == 0 for clip in self.timeline.clips):
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

    def _transform_at(self, object_id: int, initial: Transform2D, time: float) -> Transform2D:
        value = initial
        for clip in self.timeline.clips:
            if not isinstance(clip, TransformClip) or clip.object_id != object_id:
                continue
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
        clips = [c for c in self.timeline.clips if isinstance(c, clip_type) and c.object_id == object_id]
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
        clips = [c for c in self.timeline.clips if isinstance(c, StyleClip) and c.object_id == object_id]
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
        for clip in self.timeline.clips:
            if not isinstance(clip, BatchClip) or clip.object_id != object_id:
                continue
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                value = clip.after
                continue
            return value, clip
        return value, None

    def _reveal_at(self, object_id: int, initial: float, time: float) -> float:
        clips = [c for c in self.timeline.clips if isinstance(c, RevealClip) and c.object_id == object_id]
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

    def _find_registered(self, obj) -> _RegisteredItem | None:
        for registered in self._registry:
            if registered.object_ref is obj:
                return registered
        return None

    def _require_registered(self, obj) -> _RegisteredItem:
        registered = self._find_registered(obj)
        if registered is None:
            raise ValueError("object must be added to the scene first")
        return registered
