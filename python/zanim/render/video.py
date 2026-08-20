from __future__ import annotations

import hashlib
import os
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def render_video(
    scene,
    path: str | Path,
    *,
    fps: int | None = None,
    workers: int | None = None,
    crf: int = 18,
    preset: str = "medium",
    verify_random_access: bool = False,
) -> Path:
    """Render a Scene through the optimized Zig RGB0 pipeline."""
    if fps is None:
        fps = int(scene.fps)
    if fps <= 0:
        raise ValueError("fps must be positive")
    duration = float(scene.timeline.cursor)
    if duration <= 0:
        raise ValueError("scene duration must be positive")

    # Production video rendering always uses the optimized Zig core. This is
    # cached by Zig and effectively free when the core did not change.
    subprocess.run(
        ["zig", "build", "-Doptimize=ReleaseFast"],
        cwd=Path(__file__).resolve().parents[3],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    from .frame import render_snapshot_rgb0

    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(2, round(fps * duration))
    width, height = scene.width, scene.height
    if workers is None:
        workers = min(8, os.cpu_count() or 1, frame_count)
    workers = max(1, min(int(workers), frame_count))

    snapshots = tuple(
        scene.evaluate(i / (frame_count - 1) * duration)
        for i in range(frame_count)
    )
    buffers = [bytearray(width * height * 4) for _ in range(workers)]

    selected = {0, frame_count // 4, frame_count // 2, frame_count * 3 // 4, frame_count - 1}
    expected: dict[int, str] = {}

    proc = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", "rgb0",
            "-video_size", f"{width}x{height}", "-framerate", str(fps),
            "-i", "-",
            "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(output),
        ],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="zanim-render") as pool:
        futures = [
            pool.submit(render_snapshot_rgb0, buffers[slot], snapshots[slot], scene.canvas)
            for slot in range(workers)
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
                    futures[slot] = pool.submit(
                        render_snapshot_rgb0,
                        buffers[slot],
                        snapshots[next_index],
                        scene.canvas,
                    )
        finally:
            proc.stdin.close()

    if proc.wait() != 0:
        raise RuntimeError("ffmpeg encoding failed")

    if verify_random_access:
        probe = bytearray(width * height * 4)
        indices = list(selected)
        random.Random(42).shuffle(indices)
        for i in indices:
            render_snapshot_rgb0(probe, snapshots[i], scene.canvas)
            if hashlib.sha256(probe).hexdigest() != expected[i]:
                raise AssertionError(f"non-deterministic frame at index {i}")

    return output
