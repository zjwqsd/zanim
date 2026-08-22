from __future__ import annotations

import ctypes
from pathlib import Path

from .abi import load_library
from .wire import encode_snapshot


def render_snapshot_rgb0(buffer: bytearray, snapshot, canvas) -> None:
    """Render one snapshot into a caller-owned RGB0 buffer."""
    pixel_count = int(canvas.width) * int(canvas.height)
    expected_bytes = pixel_count * 4
    if len(buffer) != expected_bytes:
        raise ValueError(f"RGB0 buffer must be exactly {expected_bytes} bytes")

    encoded = encode_snapshot(snapshot)
    pixels = (ctypes.c_uint32 * pixel_count).from_buffer(buffer)
    result = load_library().zanim_render_scene_rgb0(
        int(canvas.width),
        int(canvas.height),
        float(canvas.unit_size),
        encoded.draw_array,
        len(encoded.draw_items),
        encoded.object_array,
        len(encoded.objects),
        encoded.batch_array,
        len(encoded.batches),
        encoded.vector_array,
        len(encoded.vectors),
        encoded.raster_array,
        len(encoded.rasters),
        encoded.scene3d_array,
        len(encoded.scene3d_layers),
        encoded.interpolation_array,
        len(encoded.interpolations),
        pixels,
        pixel_count,
    )
    if result != 0:
        raise RuntimeError(f"Zig RGB0 scene renderer failed with status {result}")


def render_snapshot_rgba(buffer: bytearray, snapshot, canvas) -> None:
    """Render one snapshot into caller-owned transparent straight-alpha RGBA."""
    pixel_count = int(canvas.width) * int(canvas.height)
    expected_bytes = pixel_count * 4
    if len(buffer) != expected_bytes:
        raise ValueError(f"RGBA buffer must be exactly {expected_bytes} bytes")

    encoded = encode_snapshot(snapshot)
    pixels = (ctypes.c_uint32 * pixel_count).from_buffer(buffer)
    result = load_library().zanim_render_scene_rgba0(
        int(canvas.width),
        int(canvas.height),
        float(canvas.unit_size),
        encoded.draw_array,
        len(encoded.draw_items),
        encoded.object_array,
        len(encoded.objects),
        encoded.batch_array,
        len(encoded.batches),
        encoded.vector_array,
        len(encoded.vectors),
        encoded.raster_array,
        len(encoded.rasters),
        encoded.scene3d_array,
        len(encoded.scene3d_layers),
        encoded.interpolation_array,
        len(encoded.interpolations),
        pixels,
        pixel_count,
    )
    if result != 0:
        raise RuntimeError(f"Zig RGBA scene renderer failed with status {result}")


def render_snapshot(path: str | Path, snapshot, canvas) -> Path:
    """Render one already-evaluated Scene snapshot through the Zig core."""
    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = encode_snapshot(snapshot)
    result = load_library().zanim_render_scene_frame(
        str(output).encode(),
        int(canvas.width),
        int(canvas.height),
        float(canvas.unit_size),
        encoded.draw_array,
        len(encoded.draw_items),
        encoded.object_array,
        len(encoded.objects),
        encoded.batch_array,
        len(encoded.batches),
        encoded.vector_array,
        len(encoded.vectors),
        encoded.raster_array,
        len(encoded.rasters),
        encoded.scene3d_array,
        len(encoded.scene3d_layers),
        encoded.interpolation_array,
        len(encoded.interpolations),
    )
    if result != 0:
        raise RuntimeError(f"Zig scene renderer failed with status {result}")
    return output


def pick_snapshot_object(snapshot, canvas, x: int, y: int) -> int | None:
    """Return the topmost persistent drawable object at one canvas pixel."""
    x = int(x)
    y = int(y)
    width = int(canvas.width)
    height = int(canvas.height)
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"pick pixel ({x}, {y}) is outside {width}x{height}")

    encoded = encode_snapshot(snapshot, include_object_ids=True)
    assert encoded.draw_object_ids is not None
    object_id = ctypes.c_uint32(0)
    object_ids = (ctypes.c_uint32 * len(encoded.draw_object_ids))(*encoded.draw_object_ids)
    result = load_library().zanim_pick_scene_object(
        width,
        height,
        float(canvas.unit_size),
        encoded.draw_array,
        object_ids,
        len(encoded.draw_items),
        encoded.object_array,
        len(encoded.objects),
        encoded.batch_array,
        len(encoded.batches),
        encoded.vector_array,
        len(encoded.vectors),
        encoded.raster_array,
        len(encoded.rasters),
        encoded.scene3d_array,
        len(encoded.scene3d_layers),
        encoded.interpolation_array,
        len(encoded.interpolations),
        x,
        y,
        ctypes.byref(object_id),
    )
    if result != 0:
        raise RuntimeError(f"Zig scene picker failed with status {result}")
    return int(object_id.value) or None
