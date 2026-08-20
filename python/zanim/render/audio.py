from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile


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


def _render_segment(obj, clip, output: Path, play_duration: float, sample_rate: int) -> None:
    source_start = clip.source_start
    base = (
        f"aresample={sample_rate},"
        "aformat=sample_fmts=fltp:channel_layouts=stereo"
    )
    if clip.loop:
        assert clip.source_duration is not None
        remaining = max(1e-9, clip.source_duration - source_start)
        loop_samples = max(1, round(remaining * sample_rate))
        chain = (
            f"{base},atrim=start={source_start:.12g}:end={clip.source_duration:.12g},"
            f"asetpts=N/SR/TB,aloop=loop=-1:size={loop_samples},asetpts=N/SR/TB"
        )
    else:
        source_end = source_start + play_duration * clip.speed
        chain = (
            f"{base},atrim=start={source_start:.12g}:end={source_end:.12g},"
            "asetpts=N/SR/TB"
        )
    for factor in _atempo_chain(clip.speed):
        chain += f",atempo={factor:.12g}"
    chain += f",volume={obj.gain:.12g},atrim=duration={play_duration:.12g},asetpts=N/SR/TB"

    # -t is an independent muxer-level safety bound: even if a future ffmpeg
    # filter changes timestamp semantics, a broken clip cannot grow unbounded.
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(obj.source.path),
            "-filter:a", chain, "-t", f"{play_duration:.12g}",
            "-ar", str(sample_rate), "-ac", "2", "-c:a", "pcm_s16le", str(output),
        ],
        check=True,
    )


def render_audio_mix(scene, path: str | Path, duration: float, *, sample_rate: int = 48_000) -> Path | None:
    """Render Timeline PlaybackClips for AudioObject into one finite PCM WAV."""
    tracks = [
        (obj, clip, max(0.0, clip.span.start), min(float(duration), clip.span.end))
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
        for index, (obj, clip, start, end) in enumerate(tracks):
            segment = temp / f"segment-{index:04d}.wav"
            _render_segment(obj, clip, segment, end - start, sample_rate)
            segment_paths.append(segment)
            starts.append(start)

        cmd = ["ffmpeg", "-y", "-loglevel", "error"]
        for segment in segment_paths:
            cmd += ["-i", str(segment)]
        filters: list[str] = []
        labels: list[str] = []
        for index, start in enumerate(starts):
            delay_samples = max(0, round(start * sample_rate))
            filters.append(
                f"[{index}:a]adelay={delay_samples}S:all=1,asetpts=N/SR/TB[a{index}]"
            )
            labels.append(f"[a{index}]")
        filters.append(
            "".join(labels)
            + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
              f"apad=pad_dur={duration:.12g},atrim=duration={duration:.12g},"
              "asetpts=N/SR/TB[mix]"
        )
        mixed = temp / "mix.wav"
        cmd += [
            "-filter_complex", ";".join(filters), "-map", "[mix]",
            "-t", f"{duration:.12g}",
            "-ar", str(sample_rate), "-ac", "2", "-c:a", "pcm_s16le", str(mixed),
        ]
        subprocess.run(cmd, check=True)
        mixed.replace(output)
    return output
