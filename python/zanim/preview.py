from __future__ import annotations

import io
import ipaddress
import json
import math
import queue
import tempfile
import threading
import traceback
import webbrowser
from collections import OrderedDict
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import zstandard as zstd
from PIL import Image as PILImage

from .audio import AudioObject
from .batch import BatchObject2D, DynamicBatchObject2D
from .bounds import Bounds2D, bounds_from_render_item
from .camera import Camera2D
from .geometry import Object2D
from .group import Group
from .mesh3d import MeshObject3D
from .raster import RasterObject2D
from .snapshot import (
    BatchSnapshot,
    Mesh3DSnapshot,
    NodeSnapshot,
    ObjectSnapshot,
    RasterState,
    VectorSnapshot,
)
from .source import get_preview_reload, get_preview_source, reload_preview_scene
from .space import Transform2D
from .timeline import PlaybackClip
from .value import ScalarValue
from .vector import VectorObject2D

_HTML = Path(__file__).with_name("_preview.html")


class _ByteLRU:
    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max(1, int(max_bytes))
        self._data: OrderedDict[int, bytes | bytearray] = OrderedDict()
        self._bytes = 0
        self._lock = threading.RLock()

    def get(self, key: int) -> bytes | bytearray | None:
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def put(self, key: int, value: bytes | bytearray) -> None:
        with self._lock:
            old = self._data.pop(key, None)
            if old is not None:
                self._bytes -= len(old)
            self._data[key] = value
            self._bytes += len(value)
            self._data.move_to_end(key)
            while self._bytes > self.max_bytes and len(self._data) > 1:
                _, evicted = self._data.popitem(last=False)
                self._bytes -= len(evicted)

    def keys(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(self._data.keys())

    @property
    def size_bytes(self) -> int:
        with self._lock:
            return self._bytes

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._bytes = 0


class _FrameCodec:
    """Small lossless codec wrapper used only by preview render caching."""

    name = "zstd1"

    @staticmethod
    def compress(raw: bytes | bytearray) -> bytes:
        return zstd.compress(raw, 1)

    @staticmethod
    def decompress(payload: bytes, raw_size: int) -> bytes:
        raw = zstd.decompress(payload, max_output_size=raw_size)
        if len(raw) != raw_size:
            raise RuntimeError("cold frame cache decompressed to the wrong size")
        return raw


class _CompressedFrameCache:
    """Bounded append-only cache for independently compressed RGB0 frames.

    The file never exceeds ``max_bytes``. Once the budget is exhausted the
    cache simply stops accepting new frames; existing entries remain valid and
    random-access. This keeps preview storage predictable without introducing
    eviction/compaction machinery into the exploratory UI.
    """

    def __init__(self, path: Path, *, max_bytes: int) -> None:
        self.path = Path(path)
        self.max_bytes = max(1, int(max_bytes))
        self.codec = _FrameCodec()
        self._stream = self.path.open("w+b", buffering=0)
        self._index: dict[int, tuple[int, int, int]] = {}
        self._compressed_bytes = 0
        self._raw_bytes = 0
        self._full = False
        self._lock = threading.RLock()

    def contains(self, key: int) -> bool:
        with self._lock:
            return key in self._index

    def get(self, key: int) -> bytes | None:
        with self._lock:
            entry = self._index.get(key)
            if entry is None:
                return None
            offset, compressed_size, raw_size = entry
            self._stream.seek(offset)
            payload = self._stream.read(compressed_size)
        if len(payload) != compressed_size:
            raise RuntimeError("cold frame cache payload is truncated")
        return self.codec.decompress(payload, raw_size)

    def put(self, key: int, raw: bytes | bytearray) -> bool:
        with self._lock:
            if key in self._index:
                return True
            if self._full:
                return False

        payload = self.codec.compress(raw)
        with self._lock:
            if key in self._index:
                return True
            if self._compressed_bytes + len(payload) > self.max_bytes:
                self._full = True
                return False
            offset = self._compressed_bytes
            self._stream.seek(offset)
            self._stream.write(payload)
            self._index[key] = (offset, len(payload), len(raw))
            self._compressed_bytes += len(payload)
            self._raw_bytes += len(raw)
            return True

    def keys(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(self._index.keys())

    @property
    def size_bytes(self) -> int:
        with self._lock:
            return self._compressed_bytes

    @property
    def raw_size_bytes(self) -> int:
        with self._lock:
            return self._raw_bytes

    @property
    def is_full(self) -> bool:
        with self._lock:
            return self._full

    def close(self) -> None:
        with self._lock:
            self._stream.close()
            self._index.clear()
            self._compressed_bytes = 0
            self._raw_bytes = 0
            self._full = False


class _EntryLRU:
    def __init__(self, max_entries: int) -> None:
        self.max_entries = max(1, int(max_entries))
        self._data: OrderedDict[int, object] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: int):
        with self._lock:
            value = self._data.get(key)
            if value is not None:
                self._data.move_to_end(key)
            return value

    def put(self, key: int, value) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


@dataclass(slots=True)
class _Inflight:
    event: threading.Event
    value: bytes | None = None
    error: BaseException | None = None


class PreviewSession:
    """One immutable Scene preview with random-access frame and inspection caches."""

    def __init__(
        self,
        scene,
        *,
        hot_cache_mb: int = 64,
        cold_cache_mb: int = 1024,
        snapshot_cache: int = 48,
        prefetch_seconds: float = 2.5,
        prefetch_workers: int = 2,
    ) -> None:
        self.scene = scene
        self.source_info = get_preview_source(scene)
        self.fps = max(1, int(scene.fps))
        self.duration = max(0.0, float(scene._timeline.cursor))
        self.frame_count = max(1, math.ceil(self.duration * self.fps - 1e-12))
        self.frame_bytes = int(scene.width) * int(scene.height) * 4
        hot_bytes = max(self.frame_bytes, int(hot_cache_mb) * 1024 * 1024)
        cold_bytes = max(1, int(cold_cache_mb) * 1024 * 1024)
        self.raw_cache = _ByteLRU(hot_bytes)
        self.snapshots = _EntryLRU(snapshot_cache)
        self._tempdir = tempfile.TemporaryDirectory(prefix="zanim-preview-")
        self.cold_cache = _CompressedFrameCache(
            Path(self._tempdir.name) / "frames.zcache", max_bytes=cold_bytes
        )
        requested = max(1, round(max(0.1, float(prefetch_seconds)) * self.fps))
        self.prefetch_frames = requested
        self.prefetch_workers = max(1, int(prefetch_workers))

        self._lock = threading.RLock()
        self._inflight: dict[int, _Inflight] = {}
        self._generation = 0
        self._selected = 0
        self._selected_time = 0.0
        self._queue: queue.PriorityQueue[tuple[int, int, int, float]] = queue.PriorityQueue()
        self._sequence = 0
        self._stop = threading.Event()
        self._workers: list[threading.Thread] = []
        self._exports: dict[tuple[int, int, int, str], Path] = {}
        self._stats = {
            "hot_hits": 0,
            "cold_hits": 0,
            "cache_misses": 0,
            "renders": 0,
            "prefetch_renders": 0,
            "png_encodes": 0,
        }
        for index in range(self.prefetch_workers):
            worker = threading.Thread(
                target=self._prefetch_loop,
                name=f"zanim-preview-prefetch-{index}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def close(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        for _ in self._workers:
            self._queue.put((10**9, 10**9, -1, -1))
        for worker in self._workers:
            worker.join(timeout=1.0)
        self.scene._close_media_sources()
        self.cold_cache.close()
        self._tempdir.cleanup()

    def _clamp_frame(self, index: int) -> int:
        return max(0, min(self.frame_count - 1, int(index)))

    def clamp_time(self, value: float) -> float:
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("time must be finite")
        maximum = self.duration if self.duration > 0 else 0.0
        return max(0.0, min(maximum, value))

    def time_for_frame(self, index: int) -> float:
        return self._clamp_frame(index) / self.fps

    def frame_for_time(self, value: float) -> int:
        return self._clamp_frame(round(self.clamp_time(value) * self.fps))

    def _cache_key_for_time(self, value: float) -> int:
        t = self.clamp_time(value)
        frame = self.frame_for_time(t)
        grid_time = self.time_for_frame(frame)
        if abs(grid_time - t) <= 1e-10:
            return frame
        # Negative keys cannot collide with ordinary frame indices. Nanosecond
        # quantization keeps repeated textual/JSON representations stable.
        return -(round(t * 1_000_000_000) + 1)

    def prefetch_plan(self, selected: int) -> tuple[int, ...]:
        selected = self._clamp_frame(selected)
        end = min(self.frame_count, selected + 1 + self.prefetch_frames)
        return tuple(range(selected + 1, end))

    def _clear_prefetch_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
            else:
                self._queue.task_done()

    def select_time(self, value: float) -> float:
        """Render the chosen absolute time first, then prefetch forward from it."""
        t = self.clamp_time(value)
        with self._lock:
            self._selected = self.frame_for_time(t)
            self._selected_time = t
            self._generation += 1
            generation = self._generation

        # Foreground selection wins. Old queued work is discarded only after
        # the requested sample is available, so stale prefetch never delays it.
        self.raw_time(t)
        self._clear_prefetch_queue()

        with self._lock:
            if generation != self._generation or self.cold_cache.is_full:
                return t
            for priority in range(1, self.prefetch_frames + 1):
                sample_time = t + priority / self.fps
                if self.duration > 0 and sample_time >= self.duration - 1e-12:
                    break
                key = self._cache_key_for_time(sample_time)
                if self.raw_cache.get(key) is not None or self.cold_cache.contains(key):
                    continue
                self._sequence += 1
                self._queue.put((priority, self._sequence, generation, sample_time))
        return t

    def select(self, index: int) -> int:
        index = self._clamp_frame(index)
        self.select_time(self.time_for_frame(index))
        return index

    def _snapshot_at_time(self, value: float):
        t = self.clamp_time(value)
        key = self._cache_key_for_time(t)
        cached = self.snapshots.get(key)
        if cached is not None:
            return cached
        snapshot = self.scene.evaluate(t)
        self.snapshots.put(key, snapshot)
        return snapshot

    def _snapshot(self, index: int):
        return self._snapshot_at_time(self.time_for_frame(index))

    def raw_time(self, value: float, *, prefetch: bool = False) -> bytes | bytearray:
        t = self.clamp_time(value)
        key = self._cache_key_for_time(t)
        cached = self.raw_cache.get(key)
        if cached is not None:
            with self._lock:
                self._stats["hot_hits"] += 1
            return cached

        with self._lock:
            inflight = self._inflight.get(key)
            if inflight is None:
                inflight = _Inflight(threading.Event())
                self._inflight[key] = inflight
                owner = True
            else:
                owner = False
        if not owner:
            inflight.event.wait()
            if inflight.error is not None:
                raise inflight.error
            cached = self.raw_cache.get(key)
            if cached is not None:
                return cached
            cached = self.cold_cache.get(key)
            if cached is None:
                raise RuntimeError("preview frame completed without a cache entry")
            self.raw_cache.put(key, cached)
            return cached

        try:
            # A previous request can finish between the optimistic hot lookup
            # and becoming owner, so re-check both tiers before rasterizing.
            cached = self.raw_cache.get(key)
            if cached is not None:
                with self._lock:
                    self._stats["hot_hits"] += 1
                inflight.value = cached
                return cached

            cached = self.cold_cache.get(key)
            if cached is not None:
                self.raw_cache.put(key, cached)
                with self._lock:
                    self._stats["cold_hits"] += 1
                inflight.value = cached
                return cached

            with self._lock:
                self._stats["cache_misses"] += 1

            from .render.frame import render_snapshot_rgb0

            result = bytearray(self.frame_bytes)
            render_snapshot_rgb0(result, self._snapshot_at_time(t), self.scene.canvas)
            self.raw_cache.put(key, result)
            self.cold_cache.put(key, result)
            with self._lock:
                self._stats["renders"] += 1
                if prefetch:
                    self._stats["prefetch_renders"] += 1
            inflight.value = result
            return result
        except BaseException as exc:
            inflight.error = exc
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)
                inflight.event.set()

    def raw_frame(self, index: int, *, prefetch: bool = False) -> bytes:
        return self.raw_time(self.time_for_frame(index), prefetch=prefetch)

    def png_time(self, value: float) -> bytes:
        t = self.clamp_time(value)
        raw = self.raw_time(t)
        image = PILImage.frombytes(
            "RGB", (int(self.scene.width), int(self.scene.height)), raw, "raw", "RGBX"
        )
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=False, compress_level=1)
        with self._lock:
            self._stats["png_encodes"] += 1
        return output.getvalue()

    def png_frame(self, index: int) -> bytes:
        return self.png_time(self.time_for_frame(index))

    def _prefetch_loop(self) -> None:
        while not self._stop.is_set():
            try:
                _, _, generation, sample_time = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                if sample_time < 0 or self._stop.is_set():
                    continue
                with self._lock:
                    current_generation = self._generation
                if generation != current_generation:
                    continue
                key = self._cache_key_for_time(sample_time)
                if (
                    not self.cold_cache.is_full
                    and self.raw_cache.get(key) is None
                    and not self.cold_cache.contains(key)
                ):
                    self.raw_time(sample_time, prefetch=True)
            except Exception:
                pass
            finally:
                self._queue.task_done()

    def cache_state(self) -> dict:
        # Cold cache is the authoritative record of completed raster work.
        # Hot RGB0 is only a small transient working set and does not affect
        # whether the timeline is considered rendered.
        rendered_keys = self.cold_cache.keys()
        frame_keys = sorted(key for key in rendered_keys if key >= 0)
        ranges: list[list[int]] = []
        for index in frame_keys:
            if not ranges or index != ranges[-1][1] + 1:
                ranges.append([index, index])
            else:
                ranges[-1][1] = index

        sample_times = sorted(
            self.time_for_frame(key) if key >= 0 else (-key - 1) / 1_000_000_000
            for key in rendered_keys
        )
        spans: list[list[float]] = []
        tolerance = 1.5 / self.fps
        for sample_time in sample_times:
            if not spans or sample_time - spans[-1][1] > tolerance:
                spans.append([sample_time, sample_time])
            else:
                spans[-1][1] = sample_time
        with self._lock:
            stats = dict(self._stats)
            selected = self._selected
            selected_time = self._selected_time
            generation = self._generation
            inflight_count = len(self._inflight)
        requests = stats["hot_hits"] + stats["cold_hits"] + stats["cache_misses"]
        stats["cache_hit_rate"] = (
            (stats["hot_hits"] + stats["cold_hits"]) / requests if requests else 0.0
        )
        raw_equivalent = self.cold_cache.raw_size_bytes
        compressed = self.cold_cache.size_bytes
        return {
            "selected": selected,
            "selected_time": selected_time,
            "generation": generation,
            "cached_ranges": ranges,
            "cached_spans": spans,
            "cached_frames": len(frame_keys),
            "cached_entries": len(rendered_keys),
            "hot_entries": len(self.raw_cache.keys()),
            "inflight": inflight_count,
            "hot_bytes": self.raw_cache.size_bytes,
            "hot_limit": self.raw_cache.max_bytes,
            "cold_bytes": compressed,
            "cold_limit": self.cold_cache.max_bytes,
            "cold_full": self.cold_cache.is_full,
            "cold_raw_equivalent": raw_equivalent,
            "cold_ratio": (raw_equivalent / compressed) if compressed else 0.0,
            "prefetch_frames": self.prefetch_frames,
            "stats": stats,
        }

    @staticmethod
    def _transform2d(value) -> dict[str, float]:
        return {
            "xx": value.xx,
            "xy": value.xy,
            "yx": value.yx,
            "yy": value.yy,
            "tx": value.tx,
            "ty": value.ty,
        }

    @staticmethod
    def _transform3d(value) -> list[float]:
        return list(value.as_tuple())

    def _clips_for(self, object_id: int, time_value: float) -> tuple[list[dict], list[dict]]:
        all_clips: list[dict] = []
        active: list[dict] = []
        for clip in self.scene._timeline.clips:
            key = getattr(clip, "object_id", getattr(clip, "value_id", None))
            if key != object_id:
                continue
            span = clip.span
            source = None if self.source_info is None else self.source_info.clip_source(clip)
            item = {
                "type": type(clip).__name__,
                "start": span.start,
                "end": span.end,
                "duration": span.duration,
                "source": None if source is None else source.as_dict(),
            }
            all_clips.append(item)
            if span.contains(time_value):
                progress = 1.0 if span.duration == 0 else (time_value - span.start) / span.duration
                active.append({**item, "progress": max(0.0, min(1.0, progress))})
        return all_clips, active

    def inspect_time(self, value: float, *, frame_object_ids=()) -> dict:
        t = self.clamp_time(value)
        requested_frames = {int(object_id) for object_id in frame_object_ids}
        index = self.frame_for_time(t)
        snapshot = self._snapshot_at_time(t)
        rendered = {}
        for item in (
            *snapshot.objects,
            *snapshot.batches,
            *snapshot.vectors,
            *snapshot.rasters,
            *snapshot.meshes3d,
        ):
            rendered[item.object_id] = item

        def local_bounds_at(registered) -> Bounds2D | None:
            obj = registered.object_ref
            if not isinstance(
                obj, (Object2D, BatchObject2D, VectorObject2D, RasterObject2D, Group)
            ):
                return None
            if not isinstance(obj, Group):
                rendered_item = rendered.get(registered.object_id)
                return None if rendered_item is None else bounds_from_render_item(rendered_item)

            pieces: list[Bounds2D] = []
            group_id = registered.object_id
            for leaf in self.scene._registry:
                if group_id not in leaf.parent_ids:
                    continue
                rendered_item = rendered.get(leaf.object_id)
                if rendered_item is None:
                    continue
                relative = Transform2D()
                group_index = leaf.parent_ids.index(group_id)
                for parent_id in leaf.parent_ids[group_index + 1 :]:
                    parent = self.scene._by_id[parent_id]
                    if not isinstance(parent.initial, NodeSnapshot):
                        continue
                    relative = relative @ self.scene._transform_at(
                        parent_id, parent.initial.transform, t
                    )
                initial = leaf.initial
                if not isinstance(
                    initial, (ObjectSnapshot, BatchSnapshot, VectorSnapshot, RasterState)
                ):
                    continue
                relative = relative @ self.scene._transform_at(leaf.object_id, initial.transform, t)
                pieces.append(bounds_from_render_item(rendered_item, relative))
            return Bounds2D.union(*pieces) if pieces else Bounds2D(0.0, 0.0, 0.0, 0.0)

        def bounds_dict(bounds: Bounds2D | None):
            if bounds is None:
                return None
            return {
                "left": bounds.left,
                "bottom": bounds.bottom,
                "right": bounds.right,
                "top": bounds.top,
            }

        objects: list[dict] = []
        for registered in self.scene._registry:
            object_id = registered.object_id
            obj = registered.object_ref
            alive = self.scene._is_alive(registered, t)
            lifetime_start, lifetime_end = self.scene._effective_lifetime(registered)
            clips, active = self._clips_for(object_id, t)
            if not alive:
                active = []
            info = {
                "id": object_id,
                "name": None
                if self.source_info is None
                else self.source_info.primary_name(object_id),
                "type": type(obj).__name__,
                "alive": alive,
                "parents": list(registered.parent_ids),
                "lifetime": {"start": lifetime_start, "end": lifetime_end},
                "active_clips": active,
                "clips": clips,
                "clip_count": len(clips),
                "frameable": alive
                and isinstance(
                    obj, (Object2D, BatchObject2D, VectorObject2D, RasterObject2D, Group)
                ),
                "local_bounds": (
                    bounds_dict(local_bounds_at(registered))
                    if alive and object_id in requested_frames
                    else None
                ),
                "state": {},
            }
            state = info["state"]
            if not alive:
                objects.append(info)
                continue
            initial = registered.initial
            rendered_item = rendered.get(object_id)
            rendered_state = None if rendered_item is None else rendered_item.snapshot
            if isinstance(
                initial, (ObjectSnapshot, BatchSnapshot, VectorSnapshot, RasterState, NodeSnapshot)
            ):
                if isinstance(obj, Camera2D) and obj.is_dynamic:
                    local = obj.transform_at(t, initial.transform)
                else:
                    local = self.scene._transform_at(object_id, initial.transform, t)
                state["local_transform"] = self._transform2d(local)
                state["opacity"] = self.scene._opacity_at(object_id, initial.opacity, t)
                if alive and isinstance(
                    obj, (Object2D, BatchObject2D, VectorObject2D, RasterObject2D, Group)
                ):
                    state["world_transform"] = self._transform2d(
                        self.scene.world_transform(obj, time=t)
                    )
                if rendered_state is not None and hasattr(rendered_state, "transform"):
                    state["render_transform"] = self._transform2d(rendered_state.transform)
                    state["render_opacity"] = rendered_state.opacity
            if isinstance(obj, Object2D):
                state["trim"] = self.scene._path_trim_at(object_id, initial.trim, t)
                style = self.scene._style_at(object_id, initial.style, t)
                state["style"] = {
                    "fill": (
                        None
                        if style.fill is None
                        else [style.fill.r, style.fill.g, style.fill.b, style.fill.a]
                    ),
                    "stroke": (
                        None
                        if style.stroke is None
                        else {
                            "rgba": [
                                style.stroke.color.r,
                                style.stroke.color.g,
                                style.stroke.color.b,
                                style.stroke.color.a,
                            ],
                            "width": style.stroke.width,
                        }
                    ),
                }
            elif isinstance(obj, BatchObject2D):
                if isinstance(obj, DynamicBatchObject2D):
                    active_batch = None
                else:
                    _, active_batch = self.scene._batch_at(object_id, initial.batch, t)
                if active_batch is not None:
                    state["batch_alpha"] = active_batch.alpha(t)
            elif isinstance(obj, VectorObject2D):
                state["reveal"] = self.scene._reveal_at(object_id, initial.reveal, t)
            elif isinstance(obj, RasterObject2D):
                state["source_time"] = self.scene._playback_time_at(
                    object_id, obj.source.duration, t
                )
            elif isinstance(obj, MeshObject3D):
                assert isinstance(initial, Mesh3DSnapshot)
                state["transform3d"] = self._transform3d(
                    self.scene._transform3d_at(object_id, initial.transform, t)
                )
                state["opacity"] = self.scene._opacity_at(object_id, initial.opacity, t)
            elif isinstance(obj, ScalarValue):
                state["value"] = obj.value_at(t)
            elif isinstance(obj, AudioObject):
                playback = None
                for clip in self.scene._timeline._channel_clips(PlaybackClip, object_id):
                    if clip.span.contains(t):
                        playback = clip.source_time(t)
                        break
                state["source_time"] = playback
            objects.append(info)

        active_sources = []
        seen_sources: set[tuple[str, int, int, int, str]] = set()
        for info in objects:
            for clip in info["active_clips"]:
                source = clip.get("source")
                if source is None:
                    continue
                key = (
                    str(source["path"]),
                    int(source["start_line"]),
                    int(source["end_line"]),
                    int(info["id"]),
                    str(clip["type"]),
                )
                if key in seen_sources:
                    continue
                seen_sources.add(key)
                active_sources.append(
                    {
                        "object_id": info["id"],
                        "name": info["name"],
                        "type": info["type"],
                        "clip_type": clip["type"],
                        "source": source,
                    }
                )
        camera_info = next(info for info in objects if info["id"] == 0)
        return {
            "frame": index,
            "time": t,
            "objects": objects,
            "view_transform": camera_info["state"]["local_transform"],
            "active_sources": active_sources,
        }

    def source_document(self) -> dict:
        if self.source_info is None:
            return {"available": False}
        return {
            "available": True,
            "path": self.source_info.path,
            "text": self.source_info.text,
        }

    def inspect(self, index: int) -> dict:
        return self.inspect_time(self.time_for_frame(index))

    def pick_time(self, value: float, x: int, y: int) -> dict:
        from .render.frame import pick_snapshot_object

        t = self.clamp_time(value)
        object_id = pick_snapshot_object(self._snapshot_at_time(t), self.scene.canvas, x, y)
        return {"time": t, "x": int(x), "y": int(y), "object_id": object_id}

    def _export_range_fully_cached(self, start: float, end: float) -> bool:
        frame_count = max(1, math.ceil(self.fps * (end - start) - 1e-12))
        available = set(self.cold_cache.keys())
        return all(
            self._cache_key_for_time(start + index / self.fps) in available
            for index in range(frame_count)
        )

    def export_video_time(
        self, start: float, end: float, *, crf: int = 18, preset: str = "veryfast"
    ) -> Path:
        start = self.clamp_time(start)
        end = self.clamp_time(end)
        if end <= start:
            raise ValueError("video export end must be greater than start")
        start_key = round(start * 1_000_000_000)
        end_key = round(end * 1_000_000_000)
        key = (start_key, end_key, int(crf), str(preset))
        cached = self._exports.get(key)
        if cached is not None and cached.is_file():
            return cached

        output = Path(self._tempdir.name) / f"{start_key}-{end_key}-{crf}-{preset}.mp4"
        render_kwargs = dict(start=start, end=end, fps=self.fps, crf=crf, preset=preset)

        if self._export_range_fully_cached(start, end):
            # A complete cache is safe to reuse: every requested sample can be
            # restored without Scene.evaluate() or Zig rasterization.
            self.scene.render_video(output, _frame_provider=self.raw_time, **render_kwargs)
        else:
            # Partial cache coverage deliberately falls back to the mature
            # renderer. This guarantees that previewing can never make export
            # slower by mixing cache decode, raster work, and cache writes.
            self.scene.render_video(output, **render_kwargs)

        self._exports[key] = output
        return output

    def export_video(
        self, start_frame: int, end_frame: int, *, crf: int = 18, preset: str = "veryfast"
    ) -> Path:
        start_frame = self._clamp_frame(start_frame)
        end_frame = max(start_frame + 1, min(self.frame_count, int(end_frame)))
        start = self.time_for_frame(start_frame)
        end = min(self.duration, end_frame / self.fps)
        if end <= start:
            end = min(self.duration, start + 1.0 / self.fps)
        return self.export_video_time(start, end, crf=crf, preset=preset)

    def metadata(self) -> dict:
        return {
            "width": int(self.scene.width),
            "height": int(self.scene.height),
            "unit_size": float(self.scene.canvas.unit_size),
            "fps": self.fps,
            "duration": self.duration,
            "frame_count": self.frame_count,
            "static": self.duration <= 0,
            "objects": len(self.scene._registry),
            "prefetch_frames": self.prefetch_frames,
            "preview_pixel_format": "rgb0",
            "preview_frame_bytes": self.frame_bytes,
            "preview_cache": f"hot-rgb0+cold-{self.cold_cache.codec.name}",
            "source_available": self.source_info is not None,
        }


def _is_loopback_host(host: str) -> bool:
    value = str(host).strip().lower()
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


class PreviewServer:
    def __init__(
        self,
        scene,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        hot_cache_mb: int = 64,
        cold_cache_mb: int = 1024,
        prefetch_seconds: float = 2.5,
        prefetch_workers: int = 2,
        allow_remote_reload: bool = False,
    ) -> None:
        self._session_options = {
            "hot_cache_mb": hot_cache_mb,
            "cold_cache_mb": cold_cache_mb,
            "prefetch_seconds": prefetch_seconds,
            "prefetch_workers": prefetch_workers,
        }
        self.session = PreviewSession(scene, **self._session_options)
        self.host = host
        self.port = int(port)
        self.reload_allowed = _is_loopback_host(host) or bool(allow_remote_reload)
        self._request_condition = threading.Condition()
        self._active_requests = 0
        self._reloading = False
        self._reload_lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "ZanimPreview/0.1"

            def log_message(self, format: str, *args) -> None:
                return None

            def _json(self, value, status=HTTPStatus.OK) -> None:
                payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def _error(self, exc: Exception, status=HTTPStatus.BAD_REQUEST) -> None:
                self._json({"error": str(exc)}, status)

            def _params(self):
                return parse_qs(urlsplit(self.path).query)

            def _time_param(self, session, params) -> float:
                if "t" in params:
                    return session.clamp_time(float(params["t"][0]))
                if "frame" in params:
                    return session.time_for_frame(int(params["frame"][0]))
                return 0.0

            def do_GET(self) -> None:
                session = None
                try:
                    parsed = urlsplit(self.path)
                    params = parse_qs(parsed.query)
                    if parsed.path == "/":
                        payload = _HTML.read_bytes()
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(payload)))
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(payload)
                        return
                    session = owner._begin_request()
                    if parsed.path == "/api/meta":
                        metadata = session.metadata()
                        metadata["reload_available"] = bool(
                            owner.reload_allowed and get_preview_reload(session.scene) is not None
                        )
                        self._json(metadata)
                        return
                    if parsed.path == "/api/source":
                        self._json(session.source_document())
                        return
                    if parsed.path == "/api/cache":
                        self._json(session.cache_state())
                        return
                    if parsed.path == "/api/frame/raw":
                        sample_time = self._time_param(session, params)
                        if params.get("select", ["0"])[0] == "1":
                            session.select_time(sample_time)
                        payload = session.raw_time(sample_time)
                        frame = session.frame_for_time(sample_time)
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Length", str(len(payload)))
                        self.send_header("X-Zanim-Pixel-Format", "rgb0")
                        self.send_header("X-Zanim-Width", str(session.scene.width))
                        self.send_header("X-Zanim-Height", str(session.scene.height))
                        self.send_header("X-Zanim-Frame", str(frame))
                        self.send_header("X-Zanim-Time", f"{sample_time:.12g}")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        self.wfile.write(payload)
                        return
                    if parsed.path == "/api/frame":
                        sample_time = self._time_param(session, params)
                        if params.get("select", ["0"])[0] == "1":
                            session.select_time(sample_time)
                        payload = session.png_time(sample_time)
                        frame = session.frame_for_time(sample_time)
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "image/png")
                        self.send_header("Content-Length", str(len(payload)))
                        self.send_header("X-Zanim-Frame", str(frame))
                        self.send_header("X-Zanim-Time", f"{sample_time:.12g}")
                        self.send_header("Cache-Control", "private, max-age=31536000, immutable")
                        self.end_headers()
                        self.wfile.write(payload)
                        return
                    if parsed.path == "/api/inspect":
                        sample_time = self._time_param(session, params)
                        frame_ids = tuple(
                            int(value)
                            for chunk in params.get("frames", [])
                            for value in chunk.split(",")
                            if value
                        )
                        self._json(session.inspect_time(sample_time, frame_object_ids=frame_ids))
                        return
                    if parsed.path == "/api/pick":
                        sample_time = self._time_param(session, params)
                        if "x" not in params or "y" not in params:
                            raise ValueError("pick requires x and y pixel coordinates")
                        self._json(
                            session.pick_time(sample_time, int(params["x"][0]), int(params["y"][0]))
                        )
                        return
                    if parsed.path == "/api/export/image":
                        sample_time = self._time_param(session, params)
                        frame = session.frame_for_time(sample_time)
                        payload = session.png_time(sample_time)
                        name = f"zanim-frame-{frame:06d}-{sample_time:.3f}s.png"
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "image/png")
                        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                        self.wfile.write(payload)
                        return
                    if parsed.path == "/api/export/video":
                        crf = int(params.get("crf", ["18"])[0])
                        preset = params.get("preset", ["veryfast"])[0]
                        if "start_t" in params or "end_t" in params:
                            start_t = float(params.get("start_t", ["0"])[0])
                            end_t = float(params.get("end_t", [str(session.duration)])[0])
                            output = session.export_video_time(
                                start_t, end_t, crf=crf, preset=preset
                            )
                            download_name = f"zanim-{start_t:.3f}s-{end_t:.3f}s.mp4"
                        else:
                            start = int(params.get("start", ["0"])[0])
                            end = int(params.get("end", [str(session.frame_count)])[0])
                            output = session.export_video(start, end, crf=crf, preset=preset)
                            download_name = f"zanim-{start:06d}-{end:06d}.mp4"
                        payload_size = output.stat().st_size
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "video/mp4")
                        self.send_header(
                            "Content-Disposition",
                            f'attachment; filename="{download_name}"',
                        )
                        self.send_header("Content-Length", str(payload_size))
                        self.end_headers()
                        with output.open("rb") as stream:
                            while chunk := stream.read(1024 * 1024):
                                self.wfile.write(chunk)
                        return
                    self.send_error(HTTPStatus.NOT_FOUND)
                except (ValueError, TypeError) as exc:
                    self._error(exc)
                except BrokenPipeError:
                    pass
                except Exception as exc:
                    self._error(exc, HTTPStatus.INTERNAL_SERVER_ERROR)
                finally:
                    if session is not None:
                        owner._end_request()

            def do_POST(self) -> None:
                parsed = urlsplit(self.path)
                if parsed.path != "/api/reload":
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                if not owner.reload_allowed:
                    self._json(
                        {
                            "ok": False,
                            "error": "source reload is disabled for non-loopback Preview hosts",
                        },
                        HTTPStatus.FORBIDDEN,
                    )
                    return
                params = parse_qs(parsed.query)
                try:
                    requested_time = float(params.get("t", ["0"])[0])
                    self._json(owner.reload_source(requested_time))
                except Exception as exc:
                    self._json(
                        {
                            "ok": False,
                            "error": str(exc),
                            "traceback": traceback.format_exc(),
                        },
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )

        self.httpd = ThreadingHTTPServer((host, self.port), Handler)
        self.port = int(self.httpd.server_address[1])
        self._thread: threading.Thread | None = None

    def _begin_request(self) -> PreviewSession:
        with self._request_condition:
            while self._reloading:
                self._request_condition.wait()
            self._active_requests += 1
            return self.session

    def _end_request(self) -> None:
        with self._request_condition:
            self._active_requests -= 1
            if self._active_requests == 0:
                self._request_condition.notify_all()

    def reload_source(self, requested_time: float) -> dict:
        """Explicitly rebuild the backing script/builder and replace its PreviewSession."""
        with self._reload_lock:
            with self._request_condition:
                self._reloading = True
                while self._active_requests:
                    self._request_condition.wait()
                old_session = self.session

            new_session = None
            try:
                new_scene = reload_preview_scene(old_session.scene)
                try:
                    new_session = PreviewSession(new_scene, **self._session_options)
                except BaseException:
                    new_scene._close_media_sources()
                    raise
                preserved_time = new_session.clamp_time(float(requested_time))
                new_session.select_time(preserved_time)
                self.session = new_session
                new_session = None
                old_session.close()
                return {"ok": True, "time": preserved_time}
            finally:
                if new_session is not None:
                    new_session.close()
                with self._request_condition:
                    self._reloading = False
                    self._request_condition.notify_all()

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def serve_forever(self, *, open_browser: bool = True) -> None:
        if open_browser:
            threading.Timer(0.15, lambda: webbrowser.open(self.url)).start()
        print(f"Zanim preview: {self.url}")
        try:
            self.httpd.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def start(self, *, open_browser: bool = True) -> "PreviewServer":
        if self._thread is not None:
            return self
        self._thread = threading.Thread(
            target=self.httpd.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="zanim-preview-http",
            daemon=True,
        )
        self._thread.start()
        if open_browser:
            webbrowser.open(self.url)
        return self

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.session.close()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
            self._thread = None


def preview_scene(scene, **kwargs) -> PreviewServer:
    """Launch the local random-access preview UI and block until it is closed."""
    open_browser = bool(kwargs.pop("open_browser", True))
    block = bool(kwargs.pop("block", True))
    server = PreviewServer(scene, **kwargs)
    if block:
        server.serve_forever(open_browser=open_browser)
    else:
        server.start(open_browser=open_browser)
    return server
