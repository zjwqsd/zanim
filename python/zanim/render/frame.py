from __future__ import annotations

import ctypes
from pathlib import Path

from .abi import load_library
from .wire import encode_snapshot


def render_snapshot_rgb0(buffer: bytearray, snapshot, canvas) -> None:
    """Render into a caller-owned RGB0 buffer for direct video piping."""
    pixel_count = int(canvas.width) * int(canvas.height)
    expected_bytes = pixel_count * 4
    if len(buffer) != expected_bytes:
        raise ValueError(f"RGB0 buffer must be exactly {expected_bytes} bytes")

    encoded = encode_snapshot(snapshot)
    pixels = (ctypes.c_uint32 * pixel_count).from_buffer(buffer)
    result = load_library().zanim_render_scene_rgb0(
        int(canvas.width), int(canvas.height), float(canvas.unit_size),
        encoded.draw_array, len(encoded.draw_items),
        encoded.object_array, len(encoded.objects),
        encoded.batch_array, len(encoded.batches),
        encoded.vector_array, len(encoded.vectors),
        encoded.interpolation_array, len(encoded.interpolations),
        pixels, pixel_count,
    )
    if result != 0:
        raise RuntimeError(f"Zig RGB0 scene renderer failed with status {result}")


def render_snapshot(path: str | Path, snapshot, canvas) -> Path:
    """Render one already-evaluated Scene snapshot through the Zig core."""
    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = encode_snapshot(snapshot)
    result = load_library().zanim_render_scene_frame(
        str(output).encode(),
        int(canvas.width), int(canvas.height), float(canvas.unit_size),
        encoded.draw_array, len(encoded.draw_items),
        encoded.object_array, len(encoded.objects),
        encoded.batch_array, len(encoded.batches),
        encoded.vector_array, len(encoded.vectors),
        encoded.interpolation_array, len(encoded.interpolations),
    )
    if result != 0:
        raise RuntimeError(f"Zig scene renderer failed with status {result}")
    return output
