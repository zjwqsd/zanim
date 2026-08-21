from __future__ import annotations

import json
from pathlib import Path
import subprocess


class AudioSource:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=duration", "-show_entries", "format=duration",
                "-of", "json", str(self.path),
            ],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        data = json.loads(proc.stdout)
        streams = data.get("streams") or []
        if not streams:
            raise ValueError(f"media has no audio stream: {self.path}")
        duration = streams[0].get("duration") or (data.get("format") or {}).get("duration")
        if duration is None:
            raise ValueError(f"audio duration cannot be determined: {self.path}")
        self.duration = float(duration)
        if self.duration <= 0:
            raise ValueError("audio duration must be positive")


class AudioObject:
    """Non-visual scene item whose playback is scheduled on Timeline."""

    def __setattr__(self, name: str, value) -> None:
        if not name.startswith("_") and getattr(self, "_zanim_scene_registered", False):
            raise RuntimeError(
                f"cannot assign {name!r} after Scene.add(); audio state is frozen"
            )
        object.__setattr__(self, name, value)

    def _mark_scene_registered(self) -> None:
        object.__setattr__(self, "_zanim_scene_registered", True)

    def __init__(self, source: AudioSource, *, gain: float = 1.0) -> None:
        if not isinstance(source, AudioSource):
            raise TypeError("AudioObject source must be AudioSource")
        if gain < 0:
            raise ValueError("audio gain must be >= 0")
        self.source = source
        self.gain = float(gain)


class Audio(AudioObject):
    def __init__(self, path: str | Path, *, gain: float = 1.0) -> None:
        self.path = Path(path).expanduser().resolve()
        super().__init__(AudioSource(self.path), gain=gain)
