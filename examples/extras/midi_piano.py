"""Render a MIDI file as falling piano notes with synchronized synthesized audio."""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import os
import struct
import tempfile
import wave
from collections import defaultdict, deque
from math import log2
from pathlib import Path
from typing import NamedTuple

import numpy as np
from zanim import (
    BLUE,
    CYAN,
    GREEN,
    MUTED,
    ORANGE,
    PINK,
    PURPLE,
    RED,
    WHITE,
    YELLOW,
    Audio,
    Canvas,
    Color,
    Scene,
    Text,
    Vec2,
)
from zanim.batch import BatchObject2D, DynamicBatchObject2D, LineSet, RectSet

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MIDI = ROOT / "examples/assets/midi_piano_demo.mid"
OUTPUT = ROOT / "media/extras/midi_piano.mp4"

PIANO_LOW = 21  # A0
PIANO_HIGH = 108  # C8
BLACK_CLASSES = frozenset((1, 3, 6, 8, 10))
WHITE_NOTES = tuple(
    note for note in range(PIANO_LOW, PIANO_HIGH + 1) if note % 12 not in BLACK_CLASSES
)
WHITE_INDEX = {note: index for index, note in enumerate(WHITE_NOTES)}

KEYBOARD_LEFT = -5.72
KEYBOARD_WIDTH = 11.44
WHITE_KEY_WIDTH = KEYBOARD_WIDTH / len(WHITE_NOTES)
BLACK_KEY_WIDTH = WHITE_KEY_WIDTH * 0.62
STRIKE_Y = -3.02
KEYBOARD_BOTTOM = -4.48
WHITE_KEY_HEIGHT = STRIKE_Y - KEYBOARD_BOTTOM
BLACK_KEY_HEIGHT = WHITE_KEY_HEIGHT * 0.62
TOP_EDGE = 4.72
FALL_SPEED = 2.8
LEAD_TIME = (TOP_EDGE - STRIKE_Y) / FALL_SPEED
OUTRO = 0.55

WHITE_KEY = Color(236, 239, 246)
WHITE_KEY_STROKE = Color(92, 102, 122, 180)
BLACK_KEY = Color(24, 28, 37)
BLACK_KEY_STROKE = Color(8, 10, 15, 220)
STRIKE_COLOR = Color(205, 216, 240, 125)
TRANSPARENT = Color(0, 0, 0, 0)
NOTE_COLORS = (CYAN, BLUE, PURPLE, PINK, RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, PINK)

SAMPLE_RATE = 48_000
SYNTH_VERSION = 3
SOUNDFONT_SYNTH_VERSION = 3
SOUNDFONT_TAIL = 3.0
SOUNDFONT_CANDIDATES = (
    Path.home() / ".cache/zanim/soundfonts/MuseScore_General.sf3",
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
    Path("/usr/share/sounds/sf2/TimGM6mb.sf2"),
    Path("/usr/share/soundfonts/default.sf2"),
    Path("/usr/share/soundfonts/FluidR3_GM.sf2"),
)


class MidiNote(NamedTuple):
    pitch: int
    velocity: int
    start: float
    end: float
    channel: int = 0

    @property
    def duration(self) -> float:
        return self.end - self.start


class MidiControl(NamedTuple):
    time: float
    channel: int
    controller: int
    value: int


class MidiSong(NamedTuple):
    notes: tuple[MidiNote, ...]
    duration: float
    ticks_per_quarter: int
    track_name: str | None = None
    controls: tuple[MidiControl, ...] = ()


class _RawNoteEvent(NamedTuple):
    tick: int
    order: int
    on: bool
    channel: int
    pitch: int
    velocity: int


class _RawControlEvent(NamedTuple):
    tick: int
    order: int
    channel: int
    controller: int
    value: int


class _TempoEvent(NamedTuple):
    tick: int
    order: int
    microseconds_per_quarter: int


def _read_vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if offset >= len(data):
            raise ValueError("truncated MIDI variable-length quantity")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, offset
    raise ValueError("MIDI variable-length quantity exceeds four bytes")


def _parse_track(
    data: bytes, track_order: int
) -> tuple[list[_RawNoteEvent], list[_RawControlEvent], list[_TempoEvent], str | None]:
    events: list[_RawNoteEvent] = []
    controls: list[_RawControlEvent] = []
    tempos: list[_TempoEvent] = []
    track_name: str | None = None
    offset = 0
    tick = 0
    running_status: int | None = None
    event_order = 0

    while offset < len(data):
        delta, offset = _read_vlq(data, offset)
        tick += delta
        if offset >= len(data):
            raise ValueError("truncated MIDI event")

        status = data[offset]
        if status >= 0x80:
            offset += 1
            if status < 0xF0:
                running_status = status
        elif running_status is None:
            raise ValueError("MIDI running status appears before a channel status byte")
        else:
            status = running_status

        global_order = track_order * 1_000_000 + event_order
        event_order += 1

        if status == 0xFF:
            if offset >= len(data):
                raise ValueError("truncated MIDI meta event")
            meta_type = data[offset]
            offset += 1
            length, offset = _read_vlq(data, offset)
            end = offset + length
            if end > len(data):
                raise ValueError("truncated MIDI meta payload")
            payload = data[offset:end]
            offset = end
            if meta_type == 0x51 and length == 3:
                tempo = int.from_bytes(payload, "big")
                if tempo <= 0:
                    raise ValueError("MIDI tempo must be positive")
                tempos.append(_TempoEvent(tick, global_order, tempo))
            elif meta_type == 0x03 and track_name is None:
                track_name = payload.decode("utf-8", errors="replace").strip() or None
            elif meta_type == 0x2F:
                break
            continue

        if status in (0xF0, 0xF7):
            length, offset = _read_vlq(data, offset)
            offset += length
            if offset > len(data):
                raise ValueError("truncated MIDI SysEx payload")
            running_status = None
            continue

        if status >= 0xF0:
            system_lengths = {
                0xF1: 1,
                0xF2: 2,
                0xF3: 1,
                0xF6: 0,
                0xF8: 0,
                0xFA: 0,
                0xFB: 0,
                0xFC: 0,
                0xFE: 0,
            }
            length = system_lengths.get(status)
            if length is None:
                raise ValueError(f"unsupported MIDI system status 0x{status:02x}")
            offset += length
            if offset > len(data):
                raise ValueError("truncated MIDI system message")
            continue

        kind = status & 0xF0
        channel = status & 0x0F
        length = 1 if kind in (0xC0, 0xD0) else 2
        if offset + length > len(data):
            raise ValueError("truncated MIDI channel message")
        first = data[offset]
        second = data[offset + 1] if length == 2 else 0
        offset += length

        if kind == 0x90:
            events.append(_RawNoteEvent(tick, global_order, second > 0, channel, first, second))
        elif kind == 0x80:
            events.append(_RawNoteEvent(tick, global_order, False, channel, first, second))
        elif kind == 0xB0:
            controls.append(_RawControlEvent(tick, global_order, channel, first, second))

    return events, controls, tempos, track_name


def _tick_converter(ticks_per_quarter: int, tempos: list[_TempoEvent]):
    if ticks_per_quarter <= 0:
        raise ValueError("ticks_per_quarter must be positive")
    ordered = sorted(tempos, key=lambda event: (event.tick, event.order))
    collapsed: list[tuple[int, int]] = [(0, 500_000)]
    for event in ordered:
        if event.tick == collapsed[-1][0]:
            collapsed[-1] = (event.tick, event.microseconds_per_quarter)
        else:
            collapsed.append((event.tick, event.microseconds_per_quarter))

    starts: list[tuple[int, float, int]] = []
    seconds = 0.0
    previous_tick, previous_tempo = collapsed[0]
    starts.append((previous_tick, seconds, previous_tempo))
    for tick, tempo in collapsed[1:]:
        seconds += (tick - previous_tick) * previous_tempo / (ticks_per_quarter * 1_000_000.0)
        starts.append((tick, seconds, tempo))
        previous_tick, previous_tempo = tick, tempo

    def convert(tick: int) -> float:
        selected_tick, selected_seconds, selected_tempo = starts[0]
        for start_tick, start_seconds, tempo in starts[1:]:
            if start_tick > tick:
                break
            selected_tick, selected_seconds, selected_tempo = start_tick, start_seconds, tempo
        return selected_seconds + (tick - selected_tick) * selected_tempo / (
            ticks_per_quarter * 1_000_000.0
        )

    return convert


def parse_midi(path: str | Path) -> MidiSong:
    """Parse a Standard MIDI File into note intervals with tempo changes applied."""
    midi_path = Path(path).expanduser().resolve()
    data = midi_path.read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError(f"not a Standard MIDI File: {midi_path}")
    header_length = int.from_bytes(data[4:8], "big")
    if header_length < 6 or 8 + header_length > len(data):
        raise ValueError("invalid MIDI header length")
    midi_format, track_count, division = struct.unpack(">HHH", data[8:14])
    if midi_format not in (0, 1):
        raise ValueError(f"unsupported MIDI format {midi_format}; expected format 0 or 1")
    if track_count <= 0:
        raise ValueError("MIDI file contains no tracks")
    if division & 0x8000:
        raise ValueError("SMPTE-timed MIDI files are not supported")
    ticks_per_quarter = division

    offset = 8 + header_length
    note_events: list[_RawNoteEvent] = []
    control_events: list[_RawControlEvent] = []
    tempo_events: list[_TempoEvent] = []
    track_name: str | None = None
    for track_order in range(track_count):
        if offset + 8 > len(data) or data[offset : offset + 4] != b"MTrk":
            raise ValueError(f"missing MIDI track chunk {track_order}")
        length = int.from_bytes(data[offset + 4 : offset + 8], "big")
        start = offset + 8
        end = start + length
        if end > len(data):
            raise ValueError("truncated MIDI track chunk")
        events, controls, tempos, name = _parse_track(data[start:end], track_order)
        note_events.extend(events)
        control_events.extend(controls)
        tempo_events.extend(tempos)
        if track_name is None and name:
            track_name = name
        offset = end

    if not note_events:
        raise ValueError("MIDI file contains no note events")
    to_seconds = _tick_converter(ticks_per_quarter, tempo_events)
    active: dict[tuple[int, int], deque[tuple[int, int]]] = defaultdict(deque)
    notes: list[MidiNote] = []
    for event in sorted(
        note_events, key=lambda item: (item.tick, 0 if not item.on else 1, item.order)
    ):
        key = (event.channel, event.pitch)
        if event.on:
            active[key].append((event.tick, event.velocity))
            continue
        if not active[key]:
            continue
        start_tick, velocity = active[key].popleft()
        if event.tick <= start_tick:
            continue
        notes.append(
            MidiNote(
                event.pitch,
                velocity,
                to_seconds(start_tick),
                to_seconds(event.tick),
                event.channel,
            )
        )

    if not notes:
        raise ValueError("MIDI file contains no complete note-on/note-off pairs")
    first_start = min(note.start for note in notes)
    normalized = tuple(
        MidiNote(
            note.pitch,
            note.velocity,
            note.start - first_start,
            note.end - first_start,
            note.channel,
        )
        for note in sorted(notes, key=lambda note: (note.start, note.pitch, note.end))
    )
    normalized_controls = tuple(
        MidiControl(
            max(0.0, to_seconds(event.tick) - first_start),
            event.channel,
            event.controller,
            event.value,
        )
        for event in sorted(control_events, key=lambda event: (event.tick, event.order))
    )
    duration = max(note.end for note in normalized)
    return MidiSong(normalized, duration, ticks_per_quarter, track_name, normalized_controls)


def _is_black(pitch: int) -> bool:
    return pitch % 12 in BLACK_CLASSES


def _key_x(pitch: int) -> float:
    if not PIANO_LOW <= pitch <= PIANO_HIGH:
        raise ValueError(f"MIDI pitch {pitch} is outside the 88-key piano range 21..108")
    if not _is_black(pitch):
        index = WHITE_INDEX[pitch]
        return KEYBOARD_LEFT + (index + 0.5) * WHITE_KEY_WIDTH
    lower_white = pitch - 1
    index = WHITE_INDEX[lower_white]
    return KEYBOARD_LEFT + (index + 1.0) * WHITE_KEY_WIDTH


def _key_width(pitch: int) -> float:
    return BLACK_KEY_WIDTH if _is_black(pitch) else WHITE_KEY_WIDTH


def _pitch_color(pitch: int, alpha: int = 255) -> Color:
    base = NOTE_COLORS[pitch % 12]
    return base.with_alpha(alpha)


def _blend(a: Color, b: Color, amount: float) -> Color:
    t = max(0.0, min(1.0, float(amount)))
    return Color(
        round(a.r + (b.r - a.r) * t),
        round(a.g + (b.g - a.g) * t),
        round(a.b + (b.b - a.b) * t),
        round(a.a + (b.a - a.a) * t),
    )


def _visual_start(note: MidiNote) -> float:
    return LEAD_TIME + note.start


def _visual_end(note: MidiNote) -> float:
    """Absolute key-release time; kept faithful to the MIDI note-off event."""
    return LEAD_TIME + note.end


def visual_note_duration(duration: float) -> float:
    """Compress only long rain blocks while preserving short rhythmic differences.

    Durations up to one second stay linear. Beyond one second, logarithmic
    compression maps 2s -> 1.5s, 4s -> 2.0s, and 6s -> about 2.29s.
    Audio, key press duration, and sustain controllers remain untouched.
    """
    value = max(float(duration), 0.025)
    if value <= 1.0:
        return value
    return 1.0 + 0.5 * log2(value)


def _rain_end(note: MidiNote) -> float:
    return _visual_start(note) + visual_note_duration(note.duration)


def note_rect(note: MidiNote, time: float) -> tuple[Vec2, Vec2]:
    """Return compressed rain-block geometry; its leading edge still hits at note-on."""
    start = _visual_start(note)
    height = visual_note_duration(note.duration) * FALL_SPEED
    bottom = STRIKE_Y - FALL_SPEED * (float(time) - start)
    center = Vec2(_key_x(note.pitch), bottom + height * 0.5)
    width = _key_width(note.pitch) * (0.72 if _is_black(note.pitch) else 0.78)
    return center, Vec2(width, height)


def _visible_note_state(notes: tuple[MidiNote, ...], time: float) -> RectSet:
    centers: list[Vec2] = []
    sizes: list[Vec2] = []
    fills: list[Color] = []
    for note in notes:
        start = _visual_start(note)
        end = _rain_end(note)
        if time < start - LEAD_TIME - 0.02 or time > end + 0.02:
            continue
        center, size = note_rect(note, time)
        bottom = center.y - size.y * 0.5
        top = center.y + size.y * 0.5
        if bottom > TOP_EDGE + 0.3 or top < STRIKE_Y - 0.02:
            continue
        centers.append(center)
        sizes.append(size)
        alpha = round(150 + 105 * note.velocity / 127)
        fills.append(_pitch_color(note.pitch, alpha))
    if not centers:
        return RectSet((Vec2(0, TOP_EDGE + 2),), (Vec2(0.01, 0.01),), (TRANSPARENT,))
    return RectSet(tuple(centers), tuple(sizes), tuple(fills))


def _active_pitches(notes: tuple[MidiNote, ...], time: float) -> set[int]:
    return {note.pitch for note in notes if _visual_start(note) <= time < _visual_end(note)}


def _white_key_state(notes: tuple[MidiNote, ...], time: float) -> RectSet:
    active = _active_pitches(notes, time)
    centers: list[Vec2] = []
    sizes: list[Vec2] = []
    fills: list[Color] = []
    strokes: list[Color] = []
    widths: list[float] = []
    for pitch in WHITE_NOTES:
        pressed = pitch in active
        shift = -0.035 if pressed else 0.0
        centers.append(Vec2(_key_x(pitch), (STRIKE_Y + KEYBOARD_BOTTOM) * 0.5 + shift))
        sizes.append(Vec2(WHITE_KEY_WIDTH * 0.965, WHITE_KEY_HEIGHT - (0.035 if pressed else 0.0)))
        fills.append(_blend(WHITE_KEY, _pitch_color(pitch), 0.42) if pressed else WHITE_KEY)
        strokes.append(WHITE_KEY_STROKE)
        widths.append(0.012)
    return RectSet(tuple(centers), tuple(sizes), tuple(fills), tuple(strokes), tuple(widths))


def _black_key_state(notes: tuple[MidiNote, ...], time: float) -> RectSet:
    active = _active_pitches(notes, time)
    pitches = tuple(note for note in range(PIANO_LOW, PIANO_HIGH + 1) if _is_black(note))
    centers: list[Vec2] = []
    sizes: list[Vec2] = []
    fills: list[Color] = []
    strokes: list[Color] = []
    widths: list[float] = []
    for pitch in pitches:
        pressed = pitch in active
        shift = -0.045 if pressed else 0.0
        centers.append(Vec2(_key_x(pitch), STRIKE_Y - BLACK_KEY_HEIGHT * 0.5 + shift))
        sizes.append(Vec2(BLACK_KEY_WIDTH, BLACK_KEY_HEIGHT - (0.04 if pressed else 0.0)))
        fills.append(_blend(BLACK_KEY, _pitch_color(pitch), 0.82) if pressed else BLACK_KEY)
        strokes.append(BLACK_KEY_STROKE)
        widths.append(0.014)
    return RectSet(tuple(centers), tuple(sizes), tuple(fills), tuple(strokes), tuple(widths))


def _synth_note(note: MidiNote, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    duration = max(0.025, note.duration)
    count = max(1, round(duration * sample_rate))
    t = np.arange(count, dtype=np.float64) / sample_rate
    frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)

    signal = np.zeros(count, dtype=np.float64)
    for harmonic, strength in ((1, 1.0), (2, 0.38), (3, 0.19), (4, 0.10), (5, 0.055), (6, 0.03)):
        stretch = 1.0 + 0.00018 * harmonic * harmonic
        signal += strength * np.sin(2.0 * np.pi * frequency * harmonic * stretch * t)
    signal += 0.07 * np.sin(2.0 * np.pi * frequency * 8.03 * t) * np.exp(-22.0 * t)

    attack = min(0.006, duration * 0.15)
    release = min(0.055, duration * 0.22)
    envelope = np.minimum(1.0, t / max(attack, 1e-6))
    envelope *= 0.30 + 0.70 * np.exp(-2.2 * t / max(0.45, duration))
    envelope *= np.clip((duration - t) / max(release, 1e-6), 0.0, 1.0)
    signal *= envelope * (note.velocity / 127.0) ** 1.35

    pan = np.clip((note.pitch - 64.0) / 52.0, -0.55, 0.55)
    left_gain = np.sqrt((1.0 - pan) * 0.5)
    right_gain = np.sqrt((1.0 + pan) * 0.5)
    return signal * left_gain, signal * right_gain


def synthesize_song(song: MidiSong, path: str | Path, *, sample_rate: int = SAMPLE_RATE) -> Path:
    """Synthesize a deterministic, SoundFont-free piano-like stereo WAV."""
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    frame_count = max(1, round(song.duration * sample_rate))
    left = np.zeros(frame_count, dtype=np.float64)
    right = np.zeros(frame_count, dtype=np.float64)
    for note in song.notes:
        start = max(0, round(note.start * sample_rate))
        note_left, note_right = _synth_note(note, sample_rate)
        end = min(frame_count, start + len(note_left))
        if end <= start:
            continue
        count = end - start
        left[start:end] += note_left[:count]
        right[start:end] += note_right[:count]

    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    scale = 0.92 / max(1.0, peak)
    stereo = np.column_stack((left * scale, right * scale))
    pcm = np.clip(np.rint(stereo * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return output


def find_soundfont(explicit: str | Path | None = None) -> Path | None:
    """Find an optional General MIDI SoundFont, preferring FluidR3 when available."""
    if explicit is not None:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    configured = os.environ.get("ZANIM_SOUNDFONT")
    if configured:
        path = Path(configured).expanduser().resolve()
        if path.is_file():
            return path
    return next((path.resolve() for path in SOUNDFONT_CANDIDATES if path.is_file()), None)


def _fluidsynth_library() -> str | None:
    return ctypes.util.find_library("fluidsynth")


class _FluidSynth:
    """Small ctypes wrapper for offline SoundFont rendering without a Python dependency."""

    def __init__(self, soundfont: Path, sample_rate: int) -> None:
        library = _fluidsynth_library()
        if library is None:
            raise RuntimeError("libfluidsynth is not installed")
        self.lib = ctypes.CDLL(library)
        self._configure_api()
        self.settings = self.lib.new_fluid_settings()
        if not self.settings:
            raise RuntimeError("new_fluid_settings() failed")
        self.synth = None
        try:
            self._setting_num(b"synth.sample-rate", float(sample_rate))
            self._setting_num(b"synth.gain", 0.55)
            self._setting_int(b"synth.reverb.active", 1)
            self._setting_int(b"synth.chorus.active", 0)
            self.synth = self.lib.new_fluid_synth(self.settings)
            if not self.synth:
                raise RuntimeError("new_fluid_synth() failed")
            sfid = self.lib.fluid_synth_sfload(self.synth, str(soundfont).encode(), 1)
            if sfid < 0:
                raise RuntimeError(f"FluidSynth could not load SoundFont: {soundfont}")
            for channel in range(16):
                if self.lib.fluid_synth_program_select(self.synth, channel, sfid, 0, 0) != 0:
                    raise RuntimeError("FluidSynth could not select acoustic grand piano")
        except Exception:
            self.close()
            raise

    def _configure_api(self) -> None:
        lib = self.lib
        lib.new_fluid_settings.restype = ctypes.c_void_p
        lib.delete_fluid_settings.argtypes = (ctypes.c_void_p,)
        lib.fluid_settings_setnum.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_double)
        lib.fluid_settings_setnum.restype = ctypes.c_int
        lib.fluid_settings_setint.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int)
        lib.fluid_settings_setint.restype = ctypes.c_int
        lib.new_fluid_synth.argtypes = (ctypes.c_void_p,)
        lib.new_fluid_synth.restype = ctypes.c_void_p
        lib.delete_fluid_synth.argtypes = (ctypes.c_void_p,)
        lib.fluid_synth_sfload.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int)
        lib.fluid_synth_sfload.restype = ctypes.c_int
        lib.fluid_synth_program_select.argtypes = (
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        )
        lib.fluid_synth_program_select.restype = ctypes.c_int
        lib.fluid_synth_set_gen.argtypes = (
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_float,
        )
        lib.fluid_synth_set_gen.restype = ctypes.c_int
        lib.fluid_synth_noteon.argtypes = (
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        )
        lib.fluid_synth_noteon.restype = ctypes.c_int
        lib.fluid_synth_noteoff.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
        lib.fluid_synth_noteoff.restype = ctypes.c_int
        lib.fluid_synth_cc.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int)
        lib.fluid_synth_cc.restype = ctypes.c_int
        lib.fluid_synth_write_float.argtypes = (
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int,
            ctypes.c_int,
        )
        lib.fluid_synth_write_float.restype = ctypes.c_int

    def _setting_num(self, name: bytes, value: float) -> None:
        if self.lib.fluid_settings_setnum(self.settings, name, value) < 0:
            raise RuntimeError(f"FluidSynth rejected setting {name.decode()}")

    def _setting_int(self, name: bytes, value: int) -> None:
        if self.lib.fluid_settings_setint(self.settings, name, value) < 0:
            raise RuntimeError(f"FluidSynth rejected setting {name.decode()}")

    def note_on(self, note: MidiNote) -> None:
        if (
            self.lib.fluid_synth_noteon(self.synth, note.channel % 16, note.pitch, note.velocity)
            != 0
        ):
            raise RuntimeError("FluidSynth note-on failed")

    def note_off(self, note: MidiNote) -> None:
        if self.lib.fluid_synth_noteoff(self.synth, note.channel % 16, note.pitch) != 0:
            raise RuntimeError("FluidSynth note-off failed")

    def control(self, event: MidiControl) -> None:
        if (
            self.lib.fluid_synth_cc(self.synth, event.channel % 16, event.controller, event.value)
            != 0
        ):
            raise RuntimeError("FluidSynth control-change failed")

    def render_into(self, left: np.ndarray, right: np.ndarray) -> None:
        if len(left) != len(right):
            raise ValueError("stereo output buffers must have equal length")
        if not len(left):
            return
        lptr = left.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        rptr = right.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        if self.lib.fluid_synth_write_float(self.synth, len(left), lptr, 0, 1, rptr, 0, 1) != 0:
            raise RuntimeError("FluidSynth audio rendering failed")

    def close(self) -> None:
        synth = getattr(self, "synth", None)
        if synth:
            self.lib.delete_fluid_synth(synth)
            self.synth = None
        settings = getattr(self, "settings", None)
        if settings:
            self.lib.delete_fluid_settings(settings)
            self.settings = None

    def __enter__(self) -> "_FluidSynth":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def synthesize_song_soundfont(
    song: MidiSong,
    path: str | Path,
    *,
    soundfont: str | Path,
    sample_rate: int = SAMPLE_RATE,
    tail_seconds: float = SOUNDFONT_TAIL,
) -> Path:
    """Render acoustic grand piano with the SoundFont's natural release and room tail."""
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sf2 = Path(soundfont).expanduser().resolve()
    if not sf2.is_file():
        raise FileNotFoundError(sf2)
    if tail_seconds < 0:
        raise ValueError("tail_seconds must be >= 0")

    frame_count = max(1, round((song.duration + tail_seconds) * sample_rate))
    left = np.zeros(frame_count, dtype=np.float32)
    right = np.zeros(frame_count, dtype=np.float32)
    # Controller changes are part of the performance, not decoration. Sustain
    # pedal (CC64) in particular is essential for piano phrasing. At an equal
    # sample boundary apply controls first, then note-offs, then retriggers.
    events: list[tuple[int, int, str, MidiNote | MidiControl]] = []
    for control in song.controls:
        events.append((max(0, round(control.time * sample_rate)), 0, "control", control))
    for note in song.notes:
        events.append((min(frame_count, round(note.end * sample_rate)), 1, "off", note))
        events.append((max(0, round(note.start * sample_rate)), 2, "on", note))
    events.sort(key=lambda item: (item[0], item[1]))

    cursor = 0
    with _FluidSynth(sf2, sample_rate) as synth:
        index = 0
        while index < len(events):
            sample = min(frame_count, events[index][0])
            if sample > cursor:
                synth.render_into(left[cursor:sample], right[cursor:sample])
                cursor = sample
            while index < len(events) and events[index][0] == sample:
                _, _, kind, payload = events[index]
                if kind == "control":
                    assert isinstance(payload, MidiControl)
                    synth.control(payload)
                elif kind == "off":
                    assert isinstance(payload, MidiNote)
                    synth.note_off(payload)
                else:
                    assert isinstance(payload, MidiNote)
                    synth.note_on(payload)
                index += 1
        if cursor < frame_count:
            synth.render_into(left[cursor:], right[cursor:])

    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    scale = 0.94 / max(peak, 0.94)
    stereo = np.column_stack((left * scale, right * scale))
    pcm = np.clip(np.rint(stereo * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
    return output


def resolve_synth_backend(
    backend: str = "auto", soundfont: str | Path | None = None
) -> tuple[str, Path | None]:
    """Resolve ``auto`` to SoundFont when both libfluidsynth and an SF2 are available."""
    normalized = backend.casefold().strip()
    if normalized not in {"auto", "soundfont", "builtin"}:
        raise ValueError("synth backend must be auto, soundfont, or builtin")
    if normalized == "builtin":
        return "builtin", None
    sf2 = find_soundfont(soundfont)
    library = _fluidsynth_library()
    if sf2 is not None and library is not None:
        return "soundfont", sf2
    if normalized == "soundfont":
        missing = "libfluidsynth" if library is None else "a SoundFont (.sf2)"
        raise RuntimeError(f"soundfont backend requires {missing}")
    return "builtin", None


def _audio_cache_path(song: MidiSong, *, backend: str, soundfont: Path | None = None) -> Path:
    digest = hashlib.sha256()
    digest.update(f"synth={SYNTH_VERSION};backend={backend};sr={SAMPLE_RATE};".encode())
    if soundfont is not None:
        stat = soundfont.stat()
        digest.update(
            f"sf2={soundfont};size={stat.st_size};mtime={stat.st_mtime_ns};"
            f"sfver={SOUNDFONT_SYNTH_VERSION};".encode()
        )
    for note in song.notes:
        digest.update(
            f"{note.pitch},{note.velocity},{note.start:.9f},{note.end:.9f},{note.channel};".encode()
        )
    for control in song.controls:
        digest.update(
            f"cc,{control.time:.9f},{control.channel},{control.controller},{control.value};".encode()
        )
    return Path(tempfile.gettempdir()) / f"zanim-midi-piano-{digest.hexdigest()[:20]}.wav"


def _ensure_audio(
    song: MidiSong,
    *,
    backend: str = "auto",
    soundfont: str | Path | None = None,
) -> tuple[Path, str]:
    resolved, sf2 = resolve_synth_backend(backend, soundfont)
    path = _audio_cache_path(song, backend=resolved, soundfont=sf2)
    if not path.is_file():
        if resolved == "soundfont":
            assert sf2 is not None
            synthesize_song_soundfont(song, path, soundfont=sf2)
        else:
            synthesize_song(song, path)
    return path, resolved


def _note_name(pitch: int) -> str:
    names = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")
    return f"{names[pitch % 12]}{pitch // 12 - 1}"


def _validate_piano_range(song: MidiSong) -> None:
    outside = sorted(
        {note.pitch for note in song.notes if not PIANO_LOW <= note.pitch <= PIANO_HIGH}
    )
    if outside:
        raise ValueError(f"MIDI contains pitches outside the 88-key piano range 21..108: {outside}")


def _build_scene(
    midi_path: str | Path = DEFAULT_MIDI,
    *,
    gain: float = 0.82,
    synth: str = "auto",
    soundfont: str | Path | None = None,
) -> tuple[Scene, MidiSong]:
    song = parse_midi(midi_path)
    _validate_piano_range(song)
    if gain < 0:
        raise ValueError("gain must be >= 0")
    notes = song.notes
    audio_path, synth_backend = _ensure_audio(song, backend=synth, soundfont=soundfont)

    scene = Scene(canvas=Canvas(width=1280, height=960, unit_size=100), fps=60)
    rain = DynamicBatchObject2D(lambda time: _visible_note_state(notes, time), z_index=1)
    whites = DynamicBatchObject2D(lambda time: _white_key_state(notes, time), z_index=4)
    blacks = DynamicBatchObject2D(lambda time: _black_key_state(notes, time), z_index=5)
    strike = BatchObject2D(
        LineSet(
            (Vec2(KEYBOARD_LEFT, STRIKE_Y),),
            (Vec2(KEYBOARD_LEFT + KEYBOARD_WIDTH, STRIKE_Y),),
            (STRIKE_COLOR,),
            (0.025,),
        ),
        z_index=6,
    )
    title = Text("MIDI piano rain", font_size=34, color=WHITE, opacity=0, z_index=10)
    source_name = song.track_name or Path(midi_path).stem
    low = min(note.pitch for note in notes)
    high = max(note.pitch for note in notes)
    subtitle = Text(
        f"{source_name}   ·   {len(notes)} notes   ·   {_note_name(low)}–{_note_name(high)}   ·   {synth_backend}",
        font_size=18,
        color=MUTED,
        opacity=0,
        z_index=10,
    )
    title.move_to((0, 4.34))
    subtitle.move_to((0, 3.92))
    audio = Audio(audio_path, gain=gain)

    rain, whites, blacks, strike, title, subtitle, audio = scene.add(
        rain, whites, blacks, strike, title, subtitle, audio
    )
    with scene.parallel():
        title.fade_in(duration=0.45)
        subtitle.fade_in(duration=0.55, at=0.05)
        audio.media(duration=audio.raw.source.duration, at=LEAD_TIME)
    scene.wait(OUTRO)
    return scene, song


def build_scene() -> Scene:
    """Default scene used by ``zanim preview/render``."""
    scene, _ = _build_scene(DEFAULT_MIDI)
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description="Render MIDI notes falling onto an 88-key piano")
    parser.add_argument("midi", nargs="?", type=Path, default=DEFAULT_MIDI)
    parser.add_argument("--gain", type=float, default=0.82)
    parser.add_argument("--synth", choices=("auto", "soundfont", "builtin"), default="auto")
    parser.add_argument("--soundfont", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    resolved_synth, resolved_soundfont = resolve_synth_backend(args.synth, args.soundfont)
    scene, song = _build_scene(
        args.midi, gain=args.gain, synth=resolved_synth, soundfont=resolved_soundfont
    )
    output = scene.render_video(args.output, fps=60, workers=8, verify_random_access=True)
    print(output)
    print(
        f"duration={scene.duration:.2f}s midi_duration={song.duration:.2f}s "
        f"notes={len(song.notes)} lead={LEAD_TIME:.2f}s synth={resolved_synth} "
        "audio=ok random-access=ok"
    )


if __name__ == "__main__":
    main()
