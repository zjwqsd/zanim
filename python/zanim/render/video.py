from __future__ import annotations

import ctypes
import hashlib
import math
import os
import queue
import random
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
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
    # NVENC uses CQ rather than x264 CRF. Explicit p1..p7 requests are kept;
    # generic x264-style preset names use p5, the best throughput/size point in
    # the local 1080p animation benchmark without changing the public API.
    nvenc_preset = preset if preset in {f"p{i}" for i in range(1, 8)} else "p5"
    return [
        "-c:v", "h264_nvenc", "-preset", nvenc_preset, "-tune", "hq",
        "-rc", "vbr", "-cq", str(crf), "-b:v", "0",
    ]


def _selected_frame_indices(frame_count: int) -> set[int]:
    return {0, frame_count // 4, frame_count // 2, frame_count * 3 // 4, frame_count - 1}


def _verify_random_access(scene, *, fps: int, selected: set[int], expected: dict[int, str]) -> None:
    from .frame import render_snapshot_rgb0

    probe = bytearray(scene.width * scene.height * 4)
    indices = list(selected)
    random.Random(42).shuffle(indices)
    for i in indices:
        render_snapshot_rgb0(probe, scene.evaluate(i / fps), scene.canvas)
        if hashlib.sha256(probe).hexdigest() != expected[i]:
            raise AssertionError(f"non-deterministic frame at index {i}")


def _render_visual_rgb0(
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
    """Portable RGB0 pipe used by libx264 and odd-sized NVENC frames."""
    from .frame import render_snapshot_rgb0

    duration = float(scene.timeline.cursor)
    frame_count = max(1, math.ceil(fps * duration - 1e-12))
    width, height = scene.width, scene.height
    workers = max(1, min(int(workers), frame_count))
    buffers = [bytearray(width * height * 4) for _ in range(workers)]

    def render_index(buffer: bytearray, index: int) -> None:
        render_snapshot_rgb0(buffer, scene.evaluate(index / fps), scene.canvas)

    selected = _selected_frame_indices(frame_count)
    expected: dict[int, str] = {}
    proc = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", "rgb0",
            "-video_size", f"{width}x{height}", "-framerate", str(fps),
            "-i", "-",
            *_video_encoder_args(
                video_encoder, crf=crf, preset=preset, encoder_threads=encoder_threads
            ),
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
        _verify_random_access(scene, fps=fps, selected=selected, expected=expected)


def _render_visual_nv12(
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
    """Frame-parallel RGB rendering feeding a bounded NV12/NVENC pipeline."""
    from .abi import load_library
    from .frame import render_snapshot_rgb0

    duration = float(scene.timeline.cursor)
    frame_count = max(1, math.ceil(fps * duration - 1e-12))
    width, height = scene.width, scene.height
    if (width & 1) or (height & 1):
        raise ValueError("NV12 video output requires even width and height")
    workers = max(1, min(int(workers), frame_count))

    # Two slots per render worker are enough to overlap rendering and encoder
    # backpressure. More than 16 showed no measurable throughput gain at 1080p.
    slot_count = min(frame_count, max(2, min(16, workers * 2)))
    rgb_bytes = width * height * 4
    nv12_bytes = width * height * 3 // 2
    rgb_buffers = [bytearray(rgb_bytes) for _ in range(slot_count)]
    nv12_buffers = [bytearray(nv12_bytes) for _ in range(slot_count)]
    rgb_arrays = [(ctypes.c_uint8 * rgb_bytes).from_buffer(buf) for buf in rgb_buffers]
    nv12_arrays = [(ctypes.c_uint8 * nv12_bytes).from_buffer(buf) for buf in nv12_buffers]
    convert = load_library().zanim_rgb0_to_nv12

    selected = _selected_frame_indices(frame_count)
    expected: dict[int, str] = {}

    def render_convert(slot: int, index: int) -> str | None:
        rgb = rgb_buffers[slot]
        render_snapshot_rgb0(rgb, scene.evaluate(index / fps), scene.canvas)
        digest = hashlib.sha256(rgb).hexdigest() if verify_random_access and index in selected else None
        result = convert(
            width, height,
            rgb_arrays[slot], rgb_bytes,
            nv12_arrays[slot], nv12_bytes,
        )
        if result != 0:
            raise RuntimeError(f"RGB0 to NV12 conversion failed with status {result}")
        return digest

    proc = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", "nv12",
            "-video_size", f"{width}x{height}", "-framerate", str(fps),
            "-i", "-",
            *_video_encoder_args(
                "h264_nvenc", crf=crf, preset=preset, encoder_threads=encoder_threads
            ),
            "-pix_fmt", "nv12", "-movflags", "+faststart",
            str(output),
        ],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None

    ready: queue.Queue[int | None] = queue.Queue(maxsize=slot_count)
    free_slots: queue.Queue[int] = queue.Queue(maxsize=slot_count)
    writer_errors: list[BaseException] = []

    def writer() -> None:
        try:
            while True:
                slot = ready.get()
                if slot is None:
                    return
                written = proc.stdin.write(nv12_buffers[slot])
                if written is not None and written != nv12_bytes:
                    raise RuntimeError(f"short ffmpeg pipe write: {written} / {nv12_bytes}")
                free_slots.put(slot)
        except BaseException as exc:
            writer_errors.append(exc)

    writer_thread = threading.Thread(target=writer, name="zanim-encoder-writer")
    writer_thread.start()

    def check_writer() -> None:
        if writer_errors:
            raise RuntimeError("ffmpeg encoder writer failed") from writer_errors[0]

    def acquire_slot() -> int:
        while True:
            check_writer()
            try:
                return free_slots.get(timeout=0.05)
            except queue.Empty:
                continue

    def enqueue_ready(slot: int | None) -> None:
        while True:
            check_writer()
            try:
                ready.put(slot, timeout=0.05)
                return
            except queue.Full:
                continue

    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="zanim-render") as pool:
            inflight: dict[int, tuple[object, int]] = {}
            initial = min(slot_count, frame_count)
            for index in range(initial):
                inflight[index] = (pool.submit(render_convert, index, index), index)
            next_index = initial

            for index in range(frame_count):
                future, slot = inflight.pop(index)
                digest = future.result()
                if digest is not None:
                    expected[index] = digest
                enqueue_ready(slot)

                if next_index < frame_count:
                    next_slot = acquire_slot()
                    inflight[next_index] = (
                        pool.submit(render_convert, next_slot, next_index), next_slot
                    )
                    next_index += 1

        enqueue_ready(None)
        writer_thread.join()
        check_writer()
    except BaseException:
        # Do not leave a blocked writer or ffmpeg child behind on render errors.
        if writer_thread.is_alive():
            try:
                ready.put_nowait(None)
            except queue.Full:
                pass
            writer_thread.join(timeout=1.0)
        try:
            proc.kill()
        except OSError:
            pass
        proc.wait()
        raise
    finally:
        try:
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    if proc.wait() != 0:
        raise RuntimeError("ffmpeg NVENC video encoding failed")
    if verify_random_access:
        _verify_random_access(scene, fps=fps, selected=selected, expected=expected)


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
    # NV12 removes FFmpeg's serial RGB->YUV swscale stage and cuts pipe traffic
    # by 62.5%. Odd dimensions retain the portable RGB0 path.
    if video_encoder == "h264_nvenc" and scene.width % 2 == 0 and scene.height % 2 == 0:
        _render_visual_nv12(
            scene, output, fps=fps, workers=workers, crf=crf, preset=preset,
            verify_random_access=verify_random_access, encoder_threads=encoder_threads,
        )
    else:
        _render_visual_rgb0(
            scene, output, fps=fps, workers=workers, crf=crf, preset=preset,
            verify_random_access=verify_random_access, encoder_threads=encoder_threads,
            video_encoder=video_encoder,
        )


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
