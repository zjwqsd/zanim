from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ..runtime import require_ffmpeg


def _atempo_chain(speed: float) -> list[float]:
    value = float(speed)
    if value <= 0:
        raise ValueError("audio playback speed must be positive")
    factors: list[float] = []
    while value > 2.0:
        factors.append(2.0)
        value /= 2.0
    while value < 0.5:
        factors.append(0.5)
        value /= 0.5
    if abs(value - 1.0) > 1e-12:
        factors.append(value)
    return factors


def _render_segment(
    obj, clip, output: Path, play_duration: float, sample_rate: int, *, scene_start: float
) -> None:
    source_start = clip.source_time(scene_start)
    base = f"aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts=stereo"

    if clip.loop:
        assert clip.source_duration is not None
        loop_start = clip.source_start
        loop_samples = max(1, round((clip.source_duration - loop_start) * sample_rate))
        # A sliced render may begin in the middle of a loop cycle. Emit that
        # cycle's tail first, then repeat the original loop interval.
        filters = (
            f"[0:a]{base},asplit=2[headsrc][loopsrc];"
            f"[headsrc]atrim=start={source_start:.12g}:end={clip.source_duration:.12g},"
            "asetpts=N/SR/TB[head];"
            f"[loopsrc]atrim=start={loop_start:.12g}:end={clip.source_duration:.12g},"
            f"asetpts=N/SR/TB,aloop=loop=-1:size={loop_samples},asetpts=N/SR/TB[loops];"
            "[head][loops]concat=n=2:v=0:a=1[seq]"
        )
        chain = "[seq]"
    else:
        source_end = source_start + play_duration * clip.speed
        filters = (
            f"[0:a]{base},atrim=start={source_start:.12g}:end={source_end:.12g},"
            "asetpts=N/SR/TB[seq]"
        )
        chain = "[seq]"

    post_filters = [
        *(f"atempo={factor:.12g}" for factor in _atempo_chain(clip.speed)),
        f"volume={obj.gain:.12g}",
        f"atrim=duration={play_duration:.12g}",
        "asetpts=N/SR/TB",
    ]
    filters += f";{chain}{','.join(post_filters)}[out]"

    subprocess.run(
        [
            require_ffmpeg(),
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(obj.source.path),
            "-filter_complex",
            filters,
            "-map",
            "[out]",
            "-t",
            f"{play_duration:.12g}",
            "-ar",
            str(sample_rate),
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(output),
        ],
        check=True,
    )


def render_audio_mix(
    scene,
    path: str | Path,
    duration: float,
    *,
    start: float = 0.0,
    sample_rate: int = 48_000,
) -> Path | None:
    """Render one absolute Scene timeline interval into a finite PCM WAV."""
    duration = float(duration)
    start = float(start)
    if duration <= 0:
        raise ValueError("audio render duration must be positive")
    if start < 0:
        raise ValueError("audio render start must be >= 0")
    end = start + duration

    tracks = [
        (obj, clip, max(start, clip.span.start), min(end, clip.span.end))
        for obj, clip in scene._audio_playbacks()
    ]
    tracks = [entry for entry in tracks if entry[3] > entry[2]]
    if not tracks:
        return None

    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zanim-audio-", dir=output.parent) as td:
        temp = Path(td)
        segment_paths: list[Path] = []
        starts: list[float] = []
        for index, (obj, clip, track_start, track_end) in enumerate(tracks):
            segment = temp / f"segment-{index:04d}.wav"
            _render_segment(
                obj,
                clip,
                segment,
                track_end - track_start,
                sample_rate,
                scene_start=track_start,
            )
            segment_paths.append(segment)
            starts.append(track_start - start)

        cmd = [require_ffmpeg(), "-y", "-loglevel", "error"]
        for segment in segment_paths:
            cmd += ["-i", str(segment)]
        filters: list[str] = []
        labels: list[str] = []
        for index, relative_start in enumerate(starts):
            delay_samples = max(0, round(relative_start * sample_rate))
            filters.append(f"[{index}:a]adelay={delay_samples}S:all=1,asetpts=N/SR/TB[a{index}]")
            labels.append(f"[a{index}]")
        filters.append(
            "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
            f"apad=pad_dur={duration:.12g},atrim=duration={duration:.12g},"
            "asetpts=N/SR/TB[mix]"
        )
        mixed = temp / "mix.wav"
        cmd += [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[mix]",
            "-t",
            f"{duration:.12g}",
            "-ar",
            str(sample_rate),
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(mixed),
        ]
        subprocess.run(cmd, check=True)
        mixed.replace(output)
    return output
