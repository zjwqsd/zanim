from __future__ import annotations

from typing import TYPE_CHECKING

from .audio import AudioObject
from .batch import BatchGeometry, BatchObject2D, DynamicBatchObject2D
from .camera import Camera2D
from .geometry import Object2D
from .group import Group
from .interpolation import ObjectInterpolation
from .mesh3d import MeshObject3D
from .object import SceneObject2D
from .raster import RasterObject2D
from .space import (
    LOCAL,
    PARENT,
    SE2,
    WORLD,
    Point2,
    Transform2D,
    TransformFrame,
    as_vec2,
)
from .space3d import SE3, Transform3D
from .timeline import (
    BatchClip,
    Easing,
    InterpolationClip,
    OpacityClip,
    PathTrimClip,
    PlaybackClip,
    RevealClip,
    StyleClip,
    TransformClip,
    ValueClip,
)
from .value import ScalarValue
from .vector import VectorObject2D

if TYPE_CHECKING:
    from .scene import _RegisteredItem


class _SceneAuthoring:
    @staticmethod
    def _require_frame(frame: TransformFrame | None) -> TransformFrame:
        if frame is None:
            raise ValueError(
                "relative transform by= requires explicit frame=LOCAL, PARENT, or WORLD"
            )
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
            for clip in self._timeline._channel_clips(TransformClip, parent_id):
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
        self,
        registered: _RegisteredItem,
        current: Transform2D,
        delta: Transform2D,
        frame: TransformFrame,
        start_time: float,
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
        obj: SceneObject2D,
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
            clip = self._timeline.add_se2_transform(
                registered.object_id, before_se2, after_se2, duration, easing, at
            )
        else:
            clip = self._timeline.add_transform(
                registered.object_id, obj.transform, target, duration, easing, at
            )
        obj._set_scene_state("transform", target)
        return clip

    def _transform_to_se3(
        self,
        obj: MeshObject3D,
        target: SE3,
        duration: float,
        easing: Easing,
        at: float,
    ):
        registered = self._require_alive_for_span(obj, duration, at)
        start, end = self._scheduled_span(duration, at)
        self._assert_no_descendant_world_dependency(registered, start, end)
        before = SE3.from_affine(obj.transform)
        clip = self._timeline.add_se3_transform(
            registered.object_id, before, target, duration, easing, at
        )
        obj._set_scene_state("transform", target.as_affine())
        return clip

    def _transform_to_3d(
        self,
        obj: MeshObject3D,
        target: Transform3D,
        duration: float,
        easing: Easing,
        at: float,
    ):
        registered = self._require_alive_for_span(obj, duration, at)
        start, end = self._scheduled_span(duration, at)
        self._assert_no_descendant_world_dependency(registered, start, end)
        clip = self._timeline.add_transform3d(
            registered.object_id, obj.transform, target, duration, easing, at
        )
        obj._set_scene_state("transform", target)
        return clip

    def transform(
        self,
        obj: SceneObject2D | MeshObject3D,
        *,
        by: Transform2D | Transform3D | SE2 | SE3 | None = None,
        to: Transform2D | Transform3D | SE2 | SE3 | None = None,
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
                if isinstance(to, SE3):
                    return self._transform_to_se3(obj, to, duration, easing, at)
                if not isinstance(to, Transform3D):
                    raise TypeError("MeshObject3D transform target must be Transform3D or SE3")
                return self._transform_to_3d(obj, to, duration, easing, at)
            assert by is not None
            resolved = self._require_frame(frame)
            if isinstance(by, SE3):
                current = SE3.from_affine(obj.transform)
                target_pose = (
                    by @ current if resolved is PARENT or resolved is WORLD else current @ by
                )
                return self._transform_to_se3(obj, target_pose, duration, easing, at)
            if not isinstance(by, Transform3D):
                raise TypeError("MeshObject3D relative transform must be Transform3D or SE3")
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
                return self._transform_to_2d(obj, to.as_affine(), duration, easing, at, rigid=True)
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
                self._parent_world_transform_at(registered, start) if resolved is WORLD else None
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

            clip = self._timeline.add_transform_function(
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
        obj: SceneObject2D | MeshObject3D,
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
        by: Point2 | None = None,
        to: Point2 | None = None,
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
            by = as_vec2(by, name="by")
            return self.transform(
                obj,
                by=Transform2D.translation(by.x, by.y),
                frame=self._require_frame(frame),
                duration=duration,
                easing=easing,
                at=at,
            )
        if frame is not None:
            raise ValueError("move(to=...) is an absolute world target and does not accept frame=")
        to = as_vec2(to, name="to")
        registered = self._require_registered(obj)
        anchor_parent = obj.anchor(chosen_anchor)
        current_world = self._parent_world_transform_authored(registered).apply(anchor_parent)
        delta_world = to - current_world
        return self.transform(
            obj,
            by=Transform2D.translation(delta_world.x, delta_world.y),
            frame=WORLD,
            duration=duration,
            easing=easing,
            at=at,
        )

    def rotate(
        self,
        obj: SceneObject2D,
        *,
        by: float,
        frame: TransformFrame | None = None,
        about: Point2 | None = None,
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
            about = as_vec2(about, name="about")
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

            clip = self._timeline.add_transform_function(
                registered.object_id, around_world_pivot, current, duration, easing, at
            )
            obj._set_scene_state("transform", clip.after)
            if registered.parent_ids:
                self._record_world_span(registered.object_id, start, end)
            return clip
        resolved = self._require_frame(frame)
        return self.transform(
            obj,
            by=SE2(theta=float(by)),
            frame=resolved,
            duration=duration,
            easing=easing,
            at=at,
        )

    def scale(
        self,
        obj: SceneObject2D,
        *,
        by: float,
        frame: TransformFrame | None = None,
        about: Point2 | None = None,
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
            about = as_vec2(about, name="about")
            op = (
                Transform2D.translation(about.x, about.y)
                @ Transform2D.scaling(factor)
                @ Transform2D.translation(-about.x, -about.y)
            )
            return self.transform(obj, by=op, frame=WORLD, duration=duration, easing=easing, at=at)
        resolved = self._require_frame(frame)
        return self.transform(
            obj,
            by=Transform2D.scaling(factor),
            frame=resolved,
            duration=duration,
            easing=easing,
            at=at,
        )

    def transform_function(
        self,
        obj: SceneObject2D | MeshObject3D,
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
        obj: SceneObject2D | MeshObject3D,
        provider,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        registered = self._require_alive_for_span(obj, duration, at)
        if isinstance(obj, MeshObject3D):

            def affine3d_provider(alpha: float) -> Transform3D:
                value = provider(alpha)
                if isinstance(value, SE3):
                    return value.as_affine()
                if isinstance(value, Transform3D):
                    return value
                raise TypeError("3D transform function must return Transform3D or SE3")

            clip = self._timeline.add_transform3d_function(
                registered.object_id, affine3d_provider, obj.transform, duration, easing, at
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

        clip = self._timeline.add_transform_function(
            registered.object_id, affine_provider, obj.transform, duration, easing, at
        )
        obj._set_scene_state("transform", clip.after)
        return clip

    def _opacity_to(
        self,
        obj: SceneObject2D | MeshObject3D,
        target: float,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> OpacityClip:
        if isinstance(obj, Camera2D):
            raise TypeError("Camera2D only participates in the transform channel")
        registered = self._require_alive_for_span(obj, duration, at)
        clip = self._timeline.add_opacity(
            registered.object_id, obj.opacity, target, duration, easing, at
        )
        obj._set_scene_state("opacity", float(target))
        return clip

    def fade_in(
        self,
        obj: SceneObject2D | MeshObject3D,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
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

    def fade_out(
        self,
        obj: SceneObject2D | MeshObject3D,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> OpacityClip:
        if isinstance(obj, Camera2D):
            raise TypeError("Camera2D only participates in the transform channel")
        registered = self._require_alive_for_span(obj, duration, at)
        clip = self._timeline.add_opacity(
            registered.object_id, obj.opacity, 0.0, duration, easing, at
        )
        obj._set_scene_state("opacity", 0.0)
        return clip

    def _style_to(
        self,
        obj: Object2D,
        target,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> StyleClip:
        registered = self._require_alive_for_span(obj, duration, at)
        clip = self._timeline.add_style(
            registered.object_id, obj.style, target, duration, easing, at
        )
        obj._set_scene_state("style", target)
        return clip

    def _trim_to(
        self,
        obj: Object2D,
        target: float,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> PathTrimClip:
        registered = self._require_alive_for_span(obj, duration, at)
        clip = self._timeline.add_path_trim(
            registered.object_id, obj.trim, target, duration, easing, at
        )
        obj._set_scene_state("trim", float(target))
        return clip

    def create(
        self,
        obj: Object2D | VectorObject2D,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
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
        self,
        value: ScalarValue,
        target: float,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> ValueClip:
        registered = self._require_alive_for_span(value, duration, at)
        clip = self._timeline.add_value(
            registered.object_id, value.value, target, duration, easing, at
        )
        value._clips.append(clip)
        value._set_scene_state("value", float(target))
        return clip

    def _media(
        self,
        obj: RasterObject2D | AudioObject,
        duration: float | None = None,
        *,
        source_start: float = 0.0,
        speed: float = 1.0,
        loop: bool = False,
        at: float = 0.0,
    ) -> PlaybackClip:
        registered = self._require_registered(obj)
        source_duration = obj.source.duration
        if duration is None:
            if source_duration is None:
                raise ValueError("static media playback requires an explicit duration")
            duration = (source_duration - float(source_start)) / float(speed)
        registered = self._require_alive_for_span(obj, duration, at)
        return self._timeline.add_playback(
            registered.object_id,
            duration,
            source_start=source_start,
            speed=speed,
            loop=loop,
            source_duration=source_duration,
            at=at,
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
        clip = self._timeline.add_batch(
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
        clip = self._timeline.add_reveal(
            registered.object_id,
            duration=duration,
            easing=easing,
            at=at,
            before=obj.reveal,
            after=1.0,
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
        return self._timeline.add_interpolation(
            ObjectInterpolation.from_objects(source, target), duration, easing, at
        )

    def reveal(
        self,
        obj: VectorObject2D,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> RevealClip:
        return self._reveal(obj, duration, easing, at)

    def opacity(
        self,
        obj: SceneObject2D | MeshObject3D,
        *,
        to: float,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> OpacityClip:
        return self._opacity_to(obj, to, duration, easing, at)

    def style(
        self,
        obj: Object2D,
        *,
        to,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> StyleClip:
        return self._style_to(obj, to, duration, easing, at)

    def trim(
        self,
        obj: Object2D,
        *,
        to: float,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> PathTrimClip:
        return self._trim_to(obj, to, duration, easing, at)

    def value(
        self,
        value: ScalarValue,
        *,
        to: float,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> ValueClip:
        return self._value_to(value, to, duration, easing, at)

    def media(
        self,
        obj: RasterObject2D | AudioObject,
        duration: float | None = None,
        *,
        source_start: float = 0.0,
        speed: float = 1.0,
        loop: bool = False,
        at: float = 0.0,
    ) -> PlaybackClip:
        return self._media(obj, duration, source_start=source_start, speed=speed, loop=loop, at=at)

    def batch(
        self,
        obj: BatchObject2D,
        *,
        to: BatchGeometry,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ) -> BatchClip:
        return self._batch_to(obj, to, duration, easing, at)

    def interpolate(
        self,
        source: Object2D,
        target: Object2D,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
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
        self,
        source: Object2D,
        target: Object2D,
        *,
        duration: float | None = None,
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
            raise ValueError(
                "replace() requires a top-level source; nested parentage must be explicit"
            )
        if self._find_registered(target) is not None:
            raise ValueError("replace() target must not already be in the scene")
        start = self._timeline.cursor
        added_at, removed_at = self._effective_lifetime(source_registered)
        if start < added_at or (removed_at is not None and start >= removed_at):
            raise ValueError("replace() source is not alive at the current cursor")
        interpolation = ObjectInterpolation.from_objects(source, target)
        clip = self._timeline.add_interpolation(interpolation, duration, easing, at=0.0)
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

        Passing one Group lays out its direct children independently; passing
        ordinary objects lays out exactly those objects. Layout only determines
        target translations. Object identity, scale, rotation and style remain
        unchanged.
        """
        objects = tuple(self._unwrap(obj) for obj in objects)
        if len(objects) == 1 and isinstance(objects[0], Group):
            items = tuple(objects[0].children)
        else:
            items = tuple(objects)
        if not items:
            raise ValueError("layout() requires at least one object")
        if any(isinstance(obj, Group) for obj in items):
            raise TypeError("layout() expects 2D leaf objects, or one Group")
        targets = to.targets(*items)

        def schedule():
            return tuple(
                self.transform(obj, to=target, duration=duration, easing=easing, at=at)
                for obj, target in zip(items, targets)
            )

        if self._timeline._parallel_base is not None:
            return schedule()
        with self.parallel():
            return schedule()

    def parallel(self, duration: float | None = None):
        """Schedule clips from one cursor, optionally sharing a duration default.

        ``duration=...`` only supplies the default for calls that omit their own
        duration. Explicit per-clip durations always win; ``at=`` remains a
        relative offset from the common parallel base cursor.
        """
        return self._timeline.parallel(duration=duration)

    def wait(self, duration: float = 1.0):
        return self._timeline.wait(duration)
