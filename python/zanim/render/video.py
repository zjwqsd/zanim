from __future__ import annotations

import hashlib
import math
import os
import random
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _render_visual(
    scene,
    output: Path,
    *,
    fps: int,
    workers: int,
    crf: int,
    preset: str,
    verify_random_access: bool,
    encoder_threads: int,
) -> None:
    from .frame import render_snapshot_rgb0

    duration = float(scene.timeline.cursor)
    frame_count = max(1, math.ceil(fps * duration - 1e-12))
    width, height = scene.width, scene.height
    workers = max(1, min(int(workers), frame_count))
    buffers = [bytearray(width * height * 4) for _ in range(workers)]

    def frame_time(index: int) -> float:
        return min(duration, index / fps)

    def render_index(buffer: bytearray, index: int) -> None:
        # Evaluate inside the worker so large raster frames live only for the
        # active worker slots rather than for the entire movie.
        render_snapshot_rgb0(buffer, scene.evaluate(frame_time(index)), scene.canvas)

    selected = {0, frame_count // 4, frame_count // 2, frame_count * 3 // 4, frame_count - 1}
    expected: dict[int, str] = {}

    proc = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", "rgb0",
            "-video_size", f"{width}x{height}", "-framerate", str(fps),
            "-i", "-",
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-threads", str(encoder_threads),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(output),
        ],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="zanim-render") as pool:
        futures = [
            pool.submit(render_index, buffers[slot], slot)
            for slot in range(min(workers, frame_count))
        ]
        try:
            for i in range(frame_count):
                slot = i % workers
                futures[slot].result()
                frame = buffers[slot]
                if verify_random_access and i in selected:
                    expected[i] = hashlib.sha256(frame).hexdigest()
                proc.stdin.write(frame)
                next_index = i + workers
                if next_index < frame_count:
                    futures[slot] = pool.submit(render_index, buffers[slot], next_index)
        finally:
            proc.stdin.close()

    if proc.wait() != 0:
        raise RuntimeError("ffmpeg video encoding failed")

    if verify_random_access:
        probe = bytearray(width * height * 4)
        indices = list(selected)
        random.Random(42).shuffle(indices)
        for i in indices:
            render_index(probe, i)
            if hashlib.sha256(probe).hexdigest() != expected[i]:
                raise AssertionError(f"non-deterministic frame at index {i}")


def render_video(
    scene,
    path: str | Path,
    *,
    fps: int | None = None,
    workers: int | None = None,
    crf: int = 18,
    preset: str = "medium",
    verify_random_access: bool = False,
    audio_bitrate: str = "192k",
    encoder_threads: int = 4,
) -> Path:
    """Render visual snapshots and Timeline audio into a final MP4."""
    if fps is None:
        fps = int(scene.fps)
    if fps <= 0:
        raise ValueError("fps must be positive")
    if encoder_threads <= 0:
        raise ValueError("encoder_threads must be positive")
    duration = float(scene.timeline.cursor)
    if duration <= 0:
        raise ValueError("scene duration must be positive")

    subprocess.run(
        ["zig", "build", "-Doptimize=ReleaseFast"],
        cwd=Path(__file__).resolve().parents[3],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, math.ceil(fps * duration - 1e-12))
    if workers is None:
        workers = min(8, os.cpu_count() or 1, frame_count)

    has_audio = any(True for _ in scene._audio_playbacks())
    from .audio import render_audio_mix

    try:
        # Keep all intermediate files beside the requested output rather than in
        # global /tmp. The final path is replaced only after a complete render.
        with tempfile.TemporaryDirectory(prefix=".zanim-media-", dir=output.parent) as temp_dir:
            temp = Path(temp_dir)
            visual = temp / "visual.mp4"
            _render_visual(
                scene, visual, fps=fps, workers=workers, crf=crf, preset=preset,
                verify_random_access=verify_random_access, encoder_threads=encoder_threads,
            )
            if not has_audio:
                visual.replace(output)
                return output

            audio = temp / "audio.wav"
            rendered_audio = render_audio_mix(scene, audio, duration)
            if rendered_audio is None:
                visual.replace(output)
                return output

            muxed = temp / "muxed.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(visual), "-i", str(rendered_audio),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", audio_bitrate,
                    "-t", f"{duration:.12g}", "-movflags", "+faststart", str(muxed),
                ],
                check=True,
            )
            muxed.replace(output)
            return output
    finally:
        # Streaming VideoSource instances may own a blocked ffmpeg pipe when a
        # scene only consumes part of a long source. Never leave that process
        # tied to the lifetime of the Scene object.
        scene._close_media_sources()
