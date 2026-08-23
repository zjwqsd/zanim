from __future__ import annotations

from typing import TYPE_CHECKING

from .audio import AudioObject
from .batch import BatchGeometry, BatchObject2D, DynamicBatchObject2D
from .camera import Camera2D
from .geometry import Object2D
from .infinite import ComplexMappedGrid, InfiniteObject2D
from .mesh3d import MeshObject3D
from .raster import RasterObject2D
from .snapshot import (
    BatchSnapshot,
    Camera3DSnapshot,
    InfiniteSnapshot,
    Mesh3DSnapshot,
    NodeSnapshot,
    ObjectSnapshot,
    RasterSnapshot,
    RasterState,
    RenderBatch,
    RenderInfinite,
    RenderMesh3D,
    RenderObject,
    RenderRaster,
    RenderSnapshot,
    RenderVector,
    TransientInterpolation,
    VectorSnapshot,
)
from .space import Transform2D
from .space3d import Transform3D
from .timeline import (
    BatchClip,
    InterpolationClip,
    OpacityClip,
    PathTrimClip,
    PlaybackClip,
    RevealClip,
    SE2TransformClip,
    StyleClip,
    Transform3DClip,
    TransformClip,
)
from .vector import VectorObject2D

if TYPE_CHECKING:
    from .scene import _RegisteredItem


class _SceneEvaluator:
    def evaluate(self, time: float) -> RenderSnapshot:
        objects: list[RenderObject] = []
        batches: list[RenderBatch] = []
        vectors: list[RenderVector] = []
        rasters: list[RenderRaster] = []
        infinite2d: list[RenderInfinite] = []
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
            elif isinstance(obj, InfiniteObject2D):
                infinite2d.append(self._evaluate_infinite(registered, obj, time))
            elif isinstance(obj, MeshObject3D):
                meshes3d.append(self._evaluate_mesh3d(registered, obj, time))

        transients = tuple(
            TransientInterpolation(clip.interpolation, clip.alpha(time))
            for clip in self._timeline.clips
            if isinstance(clip, InterpolationClip) and clip.span.contains(time)
        )
        return RenderSnapshot(
            time,
            tuple(objects),
            tuple(batches),
            tuple(vectors),
            tuple(rasters),
            tuple(infinite2d),
            transients,
            tuple(meshes3d),
            Camera3DSnapshot.from_camera(self.camera3d) if meshes3d else None,
        )

    def _context_at(
        self, registered: _RegisteredItem, time: float
    ) -> tuple[Transform2D, float, int]:
        camera_registered = self._by_id[0]
        camera_initial = camera_registered.initial
        assert isinstance(camera_initial, NodeSnapshot)
        camera = camera_registered.object_ref
        assert isinstance(camera, Camera2D)
        if camera.is_dynamic:
            if self._timeline._channel_clips(TransformClip, 0):
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

    def _evaluate_object(
        self, registered: _RegisteredItem, obj: Object2D, time: float
    ) -> RenderObject:
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
                transform=parent_transform
                @ self._transform_at(registered.object_id, initial.transform, time),
                style=style,
                opacity=parent_opacity
                * self._opacity_at(registered.object_id, initial.opacity, time),
                z_index=parent_z + initial.z_index,
                trim=trim,
            ),
        )

    def _evaluate_batch(
        self, registered: _RegisteredItem, obj: BatchObject2D, time: float
    ) -> RenderBatch:
        initial = registered.initial
        assert isinstance(initial, BatchSnapshot)
        parent_transform, parent_opacity, parent_z = self._context_at(registered, time)
        transform = parent_transform @ self._transform_at(
            registered.object_id, initial.transform, time
        )
        opacity = parent_opacity * self._opacity_at(registered.object_id, initial.opacity, time)
        z_index = parent_z + initial.z_index
        if isinstance(obj, DynamicBatchObject2D):
            if self._timeline._channel_clips(BatchClip, registered.object_id):
                raise RuntimeError("DynamicBatchObject2D cannot also have BatchClip entries")
            batch = obj._batch_at(time, initial.batch)
            return RenderBatch(
                registered.object_id, BatchSnapshot(batch, transform, opacity, z_index)
            )
        batch, active = self._batch_at(registered.object_id, initial.batch, time)
        if active is None:
            return RenderBatch(
                registered.object_id, BatchSnapshot(batch, transform, opacity, z_index)
            )
        return RenderBatch(
            registered.object_id,
            BatchSnapshot(active.before, transform, opacity, z_index),
            target=BatchSnapshot(active.after, transform, opacity, z_index),
            alpha=active.alpha(time),
        )

    def _evaluate_vector(
        self, registered: _RegisteredItem, obj: VectorObject2D, time: float
    ) -> RenderVector:
        initial = registered.initial
        assert isinstance(initial, VectorSnapshot)
        parent_transform, parent_opacity, parent_z = self._context_at(registered, time)
        return RenderVector(
            registered.object_id,
            VectorSnapshot(
                document=obj._document_at(time, initial.document),
                transform=parent_transform
                @ self._transform_at(registered.object_id, initial.transform, time),
                reveal=self._reveal_at(registered.object_id, initial.reveal, time),
                opacity=parent_opacity
                * self._opacity_at(registered.object_id, initial.opacity, time),
                z_index=parent_z + initial.z_index,
            ),
        )

    def _evaluate_infinite(
        self, registered: _RegisteredItem, obj: InfiniteObject2D, time: float
    ) -> RenderInfinite:
        initial = registered.initial
        assert isinstance(initial, InfiniteSnapshot)
        parent_transform, parent_opacity, parent_z = self._context_at(registered, time)
        progress = obj.progress_at(time) if isinstance(obj, ComplexMappedGrid) else initial.progress
        return RenderInfinite(
            registered.object_id,
            InfiniteSnapshot(
                initial.kind, initial.p0, initial.p1, initial.p2, initial.p3,
                parent_transform @ self._transform_at(registered.object_id, initial.transform, time),
                initial.color, initial.stroke_width,
                parent_opacity * self._opacity_at(registered.object_id, initial.opacity, time),
                parent_z + initial.z_index, initial.secondary_color, initial.map_kind,
                progress, initial.map_params,
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
                frame=obj.frame_at(source_time),
                width=initial.width,
                height=initial.height,
                transform=parent_transform
                @ self._transform_at(registered.object_id, initial.transform, time),
                opacity=parent_opacity
                * self._opacity_at(registered.object_id, initial.opacity, time),
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

    def _playback_time_at(
        self, object_id: int, source_duration: float | None, time: float
    ) -> float | None:
        clips = self._timeline._channel_clips(PlaybackClip, object_id)
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
            for clip in self._timeline._channel_clips(PlaybackClip, registered.object_id):
                yield obj, clip

    def _transform_at(self, object_id: int, initial: Transform2D, time: float) -> Transform2D:
        value = initial
        for clip in self._timeline._channel_clips(TransformClip, object_id):
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                value = clip.after.as_affine() if isinstance(clip, SE2TransformClip) else clip.after
                continue
            return clip.sample(time)
        return value

    def _transform3d_at(self, object_id: int, initial: Transform3D, time: float) -> Transform3D:
        value = initial
        for clip in self._timeline._channel_clips(Transform3DClip, object_id):
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

    def _scalar_object_channel_at(
        self, clip_type, object_id: int, initial: float, time: float
    ) -> float:
        clips = self._timeline._channel_clips(clip_type, object_id)
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
        clips = self._timeline._channel_clips(StyleClip, object_id)
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

    def _batch_at(
        self, object_id: int, initial: BatchGeometry, time: float
    ) -> tuple[BatchGeometry, BatchClip | None]:
        value = initial
        for clip in self._timeline._channel_clips(BatchClip, object_id):
            if time < clip.span.start:
                break
            if time >= clip.span.end:
                value = clip.after
                continue
            return value, clip
        return value, None

    def _reveal_at(self, object_id: int, initial: float, time: float) -> float:
        clips = self._timeline._channel_clips(RevealClip, object_id)
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
