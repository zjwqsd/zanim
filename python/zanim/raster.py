from __future__ import annotations

from bisect import bisect_right
from collections import OrderedDict
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import threading

from PIL import Image as PILImage, ImageChops, ImageFilter

from .object import SceneObject2D
from .space import SE2, Transform2D


@dataclass(frozen=True, slots=True)
class RasterFrame:
    width: int
    height: int
    rgba: bytearray

    def __post_init__(self) -> None:
        if not isinstance(self.rgba, bytearray):
            object.__setattr__(self, "rgba", bytearray(self.rgba))
        if self.width <= 0 or self.height <= 0:
            raise ValueError("raster frame dimensions must be positive")
        if len(self.rgba) != self.width * self.height * 4:
            raise ValueError("RGBA frame byte length does not match dimensions")


class RasterSource:
    """Random-access raster source addressed in source seconds."""

    width: int
    height: int
    duration: float | None
    frame_count: int

    @property
    def animated(self) -> bool:
        return self.frame_count > 1

    def frame_at(self, source_time: float) -> RasterFrame:
        raise NotImplementedError

    def close(self) -> None:
        """Release transient decoder resources; immutable source data remains usable."""
        return None


class ImageSource(RasterSource):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        with PILImage.open(self.path) as image:
            rgba = image.convert("RGBA")
            self.width, self.height = rgba.size
            self._frame = RasterFrame(self.width, self.height, rgba.tobytes())
        self.duration = None
        self.frame_count = 1

    def frame_at(self, source_time: float) -> RasterFrame:
        _ = source_time
        return self._frame


class AnimatedImageSource(RasterSource):
    """GIF/animated-image source preserving per-frame durations."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        frames: list[RasterFrame] = []
        starts: list[float] = []
        elapsed = 0.0
        with PILImage.open(self.path) as image:
            count = int(getattr(image, "n_frames", 1))
            if count <= 1:
                raise ValueError("animated image requires more than one frame")
            self.width, self.height = image.size
            for index in range(count):
                image.seek(index)
                starts.append(elapsed)
                rgba = image.convert("RGBA")
                frames.append(RasterFrame(self.width, self.height, rgba.tobytes()))
                milliseconds = float(image.info.get("duration", 100.0))
                elapsed += max(0.001, milliseconds / 1000.0)
        self._frames = tuple(frames)
        self._starts = tuple(starts)
        self.duration = elapsed
        self.frame_count = len(frames)

    def frame_at(self, source_time: float) -> RasterFrame:
        if self.duration is None or self.duration <= 0:
            return self._frames[0]
        t = max(0.0, min(float(source_time), max(0.0, self.duration - 1e-12)))
        index = max(0, min(len(self._frames) - 1, bisect_right(self._starts, t) - 1))
        return self._frames[index]


def _read_exact(stream, size: int) -> bytes:
    chunks=[]
    remaining=size
    while remaining:
        chunk=stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining-=len(chunk)
    return b''.join(chunks)


def _probe_video(path: Path) -> tuple[int, int, float, tuple[float, ...]]:
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration,avg_frame_rate",
            "-show_entries", "frame=best_effort_timestamp_time",
            "-of", "json", str(path),
        ],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    data = json.loads(proc.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise ValueError(f"video has no visual stream: {path}")
    stream = streams[0]
    width, height = int(stream["width"]), int(stream["height"])
    frames = data.get("frames") or []
    timestamps = tuple(
        float(frame["best_effort_timestamp_time"])
        for frame in frames if frame.get("best_effort_timestamp_time") is not None
    )
    duration_value = stream.get("duration")
    if duration_value is not None:
        duration = float(duration_value)
    elif timestamps:
        rate_text = stream.get("avg_frame_rate", "0/1")
        num, den = (float(v) for v in rate_text.split("/"))
        fps = num / den if den and num else 30.0
        duration = timestamps[-1] + 1.0 / fps
    else:
        raise ValueError(f"video duration cannot be determined: {path}")
    if not timestamps:
        rate_text = stream.get("avg_frame_rate", "30/1")
        num, den = (float(v) for v in rate_text.split("/"))
        fps = num / den if den and num else 30.0
        count = max(1, round(duration * fps))
        timestamps = tuple(i / fps for i in range(count))
    return width, height, duration, timestamps


class VideoSource(RasterSource):
    """Random-access video backed by a bounded in-memory ffmpeg decoder.

    Normal movie rendering asks for monotonically increasing source frames, so
    one ffmpeg process streams raw RGBA directly into a small LRU.  Backward
    seeks restart the decoder only when the requested frame is no longer in
    memory.  No decoded frame sequence is written to disk.
    """

    def __init__(self, path: str | Path, *, cache_frames: int = 16) -> None:
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        self.width, self.height, self.duration, self._timestamps = _probe_video(self.path)
        self.frame_count = len(self._timestamps)
        self._frame_bytes = self.width * self.height * 4
        self._decode_lock = threading.Lock()
        self._frame_cache: OrderedDict[int, RasterFrame] = OrderedDict()
        self._frame_cache_limit = max(2, int(cache_frames))
        self._decoder: subprocess.Popen | None = None
        self._next_index = 0

    def _stop_decoder(self) -> None:
        proc = self._decoder
        self._decoder = None
        self._next_index = 0
        if proc is None:
            return
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def close(self) -> None:
        with self._decode_lock:
            self._stop_decoder()

    def __del__(self):
        try:
            self._stop_decoder()
        except Exception:
            pass

    def _start_decoder(self) -> None:
        self._stop_decoder()
        self._decoder = subprocess.Popen(
            [
                "ffmpeg", "-loglevel", "error", "-i", str(self.path),
                "-map", "0:v:0", "-pix_fmt", "rgba",
                "-fps_mode", "passthrough", "-f", "rawvideo", "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._next_index = 0

    def _remember(self, index: int, frame: RasterFrame) -> None:
        self._frame_cache[index] = frame
        self._frame_cache.move_to_end(index)
        while len(self._frame_cache) > self._frame_cache_limit:
            self._frame_cache.popitem(last=False)

    def _frame(self, index: int) -> RasterFrame:
        index = max(0, min(self.frame_count - 1, int(index)))
        with self._decode_lock:
            cached = self._frame_cache.get(index)
            if cached is not None:
                self._frame_cache.move_to_end(index)
                return cached

            if self._decoder is None or index < self._next_index:
                self._start_decoder()
            assert self._decoder is not None and self._decoder.stdout is not None

            while self._next_index <= index:
                raw = _read_exact(self._decoder.stdout, self._frame_bytes)
                if len(raw) != self._frame_bytes:
                    self._stop_decoder()
                    raise RuntimeError(
                        f"ffmpeg ended before video frame {self._next_index} in {self.path}"
                    )
                frame = RasterFrame(self.width, self.height, raw)
                current = self._next_index
                self._next_index += 1
                self._remember(current, frame)

            result = self._frame_cache.get(index)
            if result is None:
                raise RuntimeError("requested frame was evicted while decoding")
            return result

    def frame_at(self, source_time: float) -> RasterFrame:
        t = max(0.0, min(float(source_time), max(0.0, float(self.duration) - 1e-12)))
        index = max(0, min(self.frame_count - 1, bisect_right(self._timestamps, t) - 1))
        return self._frame(index)


class SceneRasterSource(RasterSource):
    """Random-access transparent rendering of another Zanim Scene."""

    def __init__(self, scene, *, duration: float | None = None) -> None:
        self.scene = scene
        self.width = int(scene.width)
        self.height = int(scene.height)
        resolved = float(scene.timeline.cursor) if duration is None else float(duration)
        self.duration = resolved if resolved > 0 else None
        self.frame_count = max(1, round((self.duration or 0.0) * max(1, int(scene.fps))))

    def frame_at(self, source_time: float) -> RasterFrame:
        from .render.frame import render_snapshot_rgba
        t = max(0.0, float(source_time))
        if self.duration is not None:
            t = min(t, max(0.0, self.duration - 1e-12))
        rgba = bytearray(self.width * self.height * 4)
        render_snapshot_rgba(rgba, self.scene.evaluate(t), self.scene.canvas)
        return RasterFrame(self.width, self.height, rgba)

    def close(self) -> None:
        self.scene._close_media_sources()


class AlphaMaskSource(RasterSource):
    """Apply one raster source's alpha channel to another source."""

    def __init__(self, content: RasterSource, mask: RasterSource, *, invert=0.0, feather=0.0) -> None:
        if content.width != mask.width or content.height != mask.height:
            raise ValueError("content and mask raster dimensions must match")
        self.content = content
        self.mask = mask
        self.width = content.width
        self.height = content.height
        durations = [d for d in (content.duration, mask.duration) if d is not None]
        self.duration = min(durations) if durations else None
        self.frame_count = max(content.frame_count, mask.frame_count)
        self.invert = invert
        self.feather = feather

    @staticmethod
    def _value(value, time: float) -> float:
        return float(value(time) if callable(value) else value)

    def frame_at(self, source_time: float) -> RasterFrame:
        content = self.content.frame_at(source_time)
        mask = self.mask.frame_at(source_time)
        # Pillow can share RGBA bytearray storage with ``frombuffer``.  Copy
        # only content because putalpha mutates it; mask remains zero-copy.
        content_image = PILImage.frombuffer(
            "RGBA", (self.width, self.height), content.rgba, "raw", "RGBA", 0, 1
        ).copy()
        mask_image = PILImage.frombuffer(
            "RGBA", (self.width, self.height), mask.rgba, "raw", "RGBA", 0, 1
        )
        alpha = mask_image.getchannel("A")
        feather = max(0.0, self._value(self.feather, source_time))
        if feather > 1e-9:
            alpha = alpha.filter(ImageFilter.GaussianBlur(feather))
        invert = max(0.0, min(1.0, self._value(self.invert, source_time)))
        if invert > 0.0:
            inverse = alpha.point(lambda x: 255 - x)
            alpha = PILImage.blend(alpha, inverse, invert)
        content_alpha = content_image.getchannel("A")
        content_image.putalpha(ImageChops.multiply(content_alpha, alpha))
        return RasterFrame(self.width, self.height, content_image.tobytes())

    def close(self) -> None:
        self.content.close()
        if self.mask is not self.content:
            self.mask.close()


class RasterObject2D(SceneObject2D):
    """Transformable raster media with local dimensions in scene units."""

    def __init__(
        self,
        source: RasterSource,
        *,
        width: float | None = None,
        height: float | None = None,
        transform: Transform2D | SE2 = Transform2D(),
        opacity: float = 1.0,
        z_index: int = 0,
    ) -> None:
        if not isinstance(source, RasterSource):
            raise TypeError("RasterObject2D source must be RasterSource")
        aspect = source.width / source.height
        if width is None and height is None:
            width = source.width / 100.0
            height = source.height / 100.0
        elif width is None:
            width = float(height) * aspect  # type: ignore[arg-type]
        elif height is None:
            height = float(width) / aspect
        self.width = float(width)
        self.height = float(height)
        if self.width <= 0 or self.height <= 0:
            raise ValueError("raster logical dimensions must be positive")
        self.source = source
        self.transform = transform
        self.opacity = float(opacity)
        self.z_index = int(z_index)
        self._validate_scene_state()

    def frame_at(self, source_time: float) -> RasterFrame:
        return self.source.frame_at(source_time)


class Image(RasterObject2D):
    def __init__(self, path: str | Path, **kwargs) -> None:
        self.path = Path(path).expanduser().resolve()
        super().__init__(ImageSource(self.path), **kwargs)


class GIF(RasterObject2D):
    def __init__(self, path: str | Path, **kwargs) -> None:
        self.path = Path(path).expanduser().resolve()
        super().__init__(AnimatedImageSource(self.path), **kwargs)


class Video(RasterObject2D):
    def __init__(self, path: str | Path, **kwargs) -> None:
        self.path = Path(path).expanduser().resolve()
        super().__init__(VideoSource(self.path), **kwargs)

    def audio_track(self, *, gain: float = 1.0):
        from .audio import Audio
        return Audio(self.path, gain=gain)
