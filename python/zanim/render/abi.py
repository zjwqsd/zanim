from __future__ import annotations

import ctypes
from functools import lru_cache
import platform
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]


class WireObject(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_uint32),
        ("p0", ctypes.c_double), ("p1", ctypes.c_double),
        ("p2", ctypes.c_double), ("p3", ctypes.c_double),
        ("p4", ctypes.c_double), ("p5", ctypes.c_double),
        ("p6", ctypes.c_double), ("p7", ctypes.c_double),
        ("points", ctypes.POINTER(ctypes.c_double)),
        ("point_count", ctypes.c_uint32),
        ("xx", ctypes.c_double), ("xy", ctypes.c_double),
        ("yx", ctypes.c_double), ("yy", ctypes.c_double),
        ("tx", ctypes.c_double), ("ty", ctypes.c_double),
        ("fill_present", ctypes.c_uint32),
        ("fill_rgba", ctypes.c_uint32),
        ("stroke_present", ctypes.c_uint32),
        ("stroke_rgba", ctypes.c_uint32),
        ("stroke_width", ctypes.c_double),
        ("opacity", ctypes.c_double),
    ]


class WireBatch(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
        ("data", ctypes.POINTER(ctypes.c_double)),
        ("fill_rgba", ctypes.POINTER(ctypes.c_uint32)),
        ("stroke_rgba", ctypes.POINTER(ctypes.c_uint32)),
        ("stroke_widths", ctypes.POINTER(ctypes.c_double)),
        ("target_data", ctypes.POINTER(ctypes.c_double)),
        ("target_fill_rgba", ctypes.POINTER(ctypes.c_uint32)),
        ("target_stroke_rgba", ctypes.POINTER(ctypes.c_uint32)),
        ("target_stroke_widths", ctypes.POINTER(ctypes.c_double)),
        ("alpha", ctypes.c_double),
        ("xx", ctypes.c_double), ("xy", ctypes.c_double),
        ("yx", ctypes.c_double), ("yy", ctypes.c_double),
        ("tx", ctypes.c_double), ("ty", ctypes.c_double),
        ("opacity", ctypes.c_double),
    ]


class WireVectorPath(ctypes.Structure):
    _fields_ = [
        ("segment_count", ctypes.c_uint32),
        ("segments", ctypes.POINTER(ctypes.c_double)),
        ("contour_count", ctypes.c_uint32),
        ("contour_ends", ctypes.POINTER(ctypes.c_uint32)),
        ("contour_closed", ctypes.POINTER(ctypes.c_uint8)),
        ("fill_present", ctypes.c_uint32),
        ("fill_rgba", ctypes.c_uint32),
        ("stroke_present", ctypes.c_uint32),
        ("stroke_rgba", ctypes.c_uint32),
        ("stroke_width", ctypes.c_double),
        ("group", ctypes.c_uint32),
    ]


class WireVectorObject(ctypes.Structure):
    _fields_ = [
        ("path_count", ctypes.c_uint32),
        ("paths", ctypes.POINTER(WireVectorPath)),
        ("group_count", ctypes.c_uint32),
        ("reveal", ctypes.c_double),
        ("xx", ctypes.c_double), ("xy", ctypes.c_double),
        ("yx", ctypes.c_double), ("yy", ctypes.c_double),
        ("tx", ctypes.c_double), ("ty", ctypes.c_double),
        ("opacity", ctypes.c_double),
    ]


class WireRaster(ctypes.Structure):
    _fields_ = [
        ("pixels", ctypes.POINTER(ctypes.c_uint8)),
        ("pixel_width", ctypes.c_uint32),
        ("pixel_height", ctypes.c_uint32),
        ("logical_width", ctypes.c_double),
        ("logical_height", ctypes.c_double),
        ("xx", ctypes.c_double), ("xy", ctypes.c_double),
        ("yx", ctypes.c_double), ("yy", ctypes.c_double),
        ("tx", ctypes.c_double), ("ty", ctypes.c_double),
        ("opacity", ctypes.c_double),
    ]


class WireCamera3D(ctypes.Structure):
    _fields_ = [
        ("px", ctypes.c_float), ("py", ctypes.c_float), ("pz", ctypes.c_float),
        ("tx", ctypes.c_float), ("ty", ctypes.c_float), ("tz", ctypes.c_float),
        ("ux", ctypes.c_float), ("uy", ctypes.c_float), ("uz", ctypes.c_float),
        ("fov_y_degrees", ctypes.c_float),
        ("near_plane", ctypes.c_float), ("far_plane", ctypes.c_float),
        ("orthographic_height", ctypes.c_float),
        ("projection_kind", ctypes.c_uint32),
    ]


class WireMesh3D(ctypes.Structure):
    _fields_ = [
        ("vertex_count", ctypes.c_uint32),
        ("positions", ctypes.POINTER(ctypes.c_float)),
        ("normals", ctypes.POINTER(ctypes.c_float)),
        ("index_count", ctypes.c_uint32),
        ("indices", ctypes.POINTER(ctypes.c_uint32)),
        ("model", ctypes.c_float * 16),
        ("color_rgba", ctypes.c_uint32),
        ("opacity", ctypes.c_float),
    ]


class WireScene3DLayer(ctypes.Structure):
    _fields_ = [
        ("camera", WireCamera3D),
        ("meshes", ctypes.POINTER(WireMesh3D)),
        ("mesh_count", ctypes.c_uint32),
    ]


class WireInterpolation(ctypes.Structure):
    _fields_ = [
        ("source", WireObject),
        ("target", WireObject),
        ("alpha", ctypes.c_double),
    ]


class WireDrawItem(ctypes.Structure):
    _fields_ = [
        ("kind", ctypes.c_uint32),
        ("index", ctypes.c_uint32),
    ]


def library_path() -> Path:
    system = platform.system()
    if system == "Linux":
        name = "libzanim_core.so"
    elif system == "Darwin":
        name = "libzanim_core.dylib"
    elif system == "Windows":
        name = "zanim_core.dll"
    else:
        raise RuntimeError(f"unsupported platform: {system}")
    return _ROOT / "zig-out" / "lib" / name


@lru_cache(maxsize=1)
def load_library() -> ctypes.CDLL:
    path = library_path()
    if not path.exists():
        raise RuntimeError(f"Zanim core is not built: {path}. Run `zig build` first.")

    lib = ctypes.CDLL(str(path))
    lib.zanim_render_scene_frame.argtypes = [
        ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_double,
        ctypes.POINTER(WireDrawItem), ctypes.c_uint32,
        ctypes.POINTER(WireObject), ctypes.c_uint32,
        ctypes.POINTER(WireBatch), ctypes.c_uint32,
        ctypes.POINTER(WireVectorObject), ctypes.c_uint32,
        ctypes.POINTER(WireRaster), ctypes.c_uint32,
        ctypes.POINTER(WireScene3DLayer), ctypes.c_uint32,
        ctypes.POINTER(WireInterpolation), ctypes.c_uint32,
    ]
    lib.zanim_render_scene_frame.restype = ctypes.c_int32
    lib.zanim_render_scene_rgb0.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_double,
        ctypes.POINTER(WireDrawItem), ctypes.c_uint32,
        ctypes.POINTER(WireObject), ctypes.c_uint32,
        ctypes.POINTER(WireBatch), ctypes.c_uint32,
        ctypes.POINTER(WireVectorObject), ctypes.c_uint32,
        ctypes.POINTER(WireRaster), ctypes.c_uint32,
        ctypes.POINTER(WireScene3DLayer), ctypes.c_uint32,
        ctypes.POINTER(WireInterpolation), ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
    ]
    lib.zanim_render_scene_rgb0.restype = ctypes.c_int32
    lib.zanim_render_scene_rgba0.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_double,
        ctypes.POINTER(WireDrawItem), ctypes.c_uint32,
        ctypes.POINTER(WireObject), ctypes.c_uint32,
        ctypes.POINTER(WireBatch), ctypes.c_uint32,
        ctypes.POINTER(WireVectorObject), ctypes.c_uint32,
        ctypes.POINTER(WireRaster), ctypes.c_uint32,
        ctypes.POINTER(WireScene3DLayer), ctypes.c_uint32,
        ctypes.POINTER(WireInterpolation), ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
    ]
    lib.zanim_render_scene_rgba0.restype = ctypes.c_int32
    lib.zanim_rgb0_to_nv12.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
    ]
    lib.zanim_rgb0_to_nv12.restype = ctypes.c_int32
    return lib
