"""Runtime dependency discovery used by CLI diagnostics and media backends."""

from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache

from .errors import MediaError


@lru_cache(maxsize=1)
def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


@lru_cache(maxsize=1)
def ffprobe_path() -> str | None:
    return shutil.which("ffprobe")


@lru_cache(maxsize=1)
def ffmpeg_has_libx264() -> bool:
    executable = ffmpeg_path()
    if executable is None:
        return False
    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-encoders"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "libx264" in result.stdout


def require_ffmpeg() -> str:
    executable = ffmpeg_path()
    if executable is None:
        raise MediaError(
            "FFmpeg was not found on PATH. Install FFmpeg and restart the shell. "
            "Ubuntu: `sudo apt install ffmpeg`; Windows: `winget install Gyan.FFmpeg`."
        )
    return executable


def require_ffprobe() -> str:
    executable = ffprobe_path()
    if executable is None:
        raise MediaError(
            "ffprobe was not found on PATH. Install the complete FFmpeg toolset; "
            "video sources require both ffmpeg and ffprobe."
        )
    return executable


def require_video_encoder() -> str:
    executable = require_ffmpeg()
    if not ffmpeg_has_libx264():
        raise MediaError(
            "FFmpeg is installed, but the libx264 encoder is unavailable. "
            "Install an FFmpeg build with libx264 support."
        )
    return executable
