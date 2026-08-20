from __future__ import annotations

import hashlib
import math
import os
import random
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import shutil
from pathlib import Path

@lru_cache(maxsize=1)
def _nvenc_available() -> bool:
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "-L"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if gpu.returncode != 0:
            return False
        encoders = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            check=True, capture_output=True, text=True,
        )
        return "h264_nvenc" in encoders.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def _resolve_video_encoder(video_encoder: str) -> str:
    if video_encoder == "auto":
        return "h264_nvenc" if _nvenc_available() else "libx264"
    if video_encoder not in {"libx264", "h264_nvenc"}:
        raise ValueError("video_encoder must be 'libx264', 'h264_nvenc', or 'auto'")
    return video_encoder


def _video_encoder_args(
    video_encoder: str, *, crf: int, preset: str, encoder_threads: int
) -> list[str]:
    if video_encoder == "libx264":
        return [
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-threads", str(encoder_threads),
        ]
    # NVENC uses CQ rather than x264 CRF. Keep the same quality-scale input so
    # callers can switch encoders without learning a second quality parameter.
    nvenc_preset = preset if preset in {f"p{i}" for i in range(1, 8)} else "p4"
    return [
        "-c:v", "h264_nvenc", "-preset", nvenc_preset, "-tune", "hq",
        "-rc", "vbr", "-cq", str(crf), "-b:v", "0",
    ]



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
    video_encoder: str,
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

    encoder_args = _video_encoder_args(
        video_encoder, crf=crf, preset=preset, encoder_threads=encoder_threads
    )
    proc = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", "rgb0",
            "-video_size", f"{width}x{height}", "-framerate", str(fps),
            "-i", "-",
            *encoder_args,
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
    video_encoder: str = "libx264",
) -> Path:
    """Render visual snapshots and Timeline audio into a final MP4."""
    if fps is None:
        fps = int(scene.fps)
    if fps <= 0:
        raise ValueError("fps must be positive")
    if encoder_threads <= 0:
        raise ValueError("encoder_threads must be positive")
    video_encoder = _resolve_video_encoder(video_encoder)
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
                video_encoder=video_encoder,
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
