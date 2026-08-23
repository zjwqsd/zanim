import importlib.util
import struct
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "extras" / "midi_piano.py"
SPEC = importlib.util.spec_from_file_location("zanim_midi_piano_extra", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _vlq(value: int) -> bytes:
    parts = [value & 0x7F]
    value >>= 7
    while value:
        parts.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(parts))


def _track(events):
    events = sorted(events, key=lambda item: (item[0], item[1]))
    payload = bytearray()
    previous = 0
    for tick, _, event in events:
        payload += _vlq(tick - previous)
        payload += event
        previous = tick
    payload += b"\x00\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(payload)) + payload


class MidiPianoExtraTests(unittest.TestCase):
    def test_demo_midi_parses_into_complete_piano_notes(self):
        song = MODULE.parse_midi(MODULE.DEFAULT_MIDI)
        self.assertEqual(len(song.notes), 96)
        self.assertGreater(song.duration, 10.0)
        self.assertTrue(all(note.end > note.start for note in song.notes))
        self.assertTrue(
            all(MODULE.PIANO_LOW <= note.pitch <= MODULE.PIANO_HIGH for note in song.notes)
        )
        self.assertEqual(song.track_name, "Original piano rain demo")

    def test_format_one_tempo_map_changes_absolute_note_duration(self):
        tpq = 480
        header = b"MThd" + struct.pack(">IHHH", 6, 1, 2, tpq)
        tempo = _track(
            [
                (0, 0, b"\xff\x51\x03" + (500_000).to_bytes(3, "big")),
                (480, 0, b"\xff\x51\x03" + (1_000_000).to_bytes(3, "big")),
            ]
        )
        notes = _track(
            [
                (0, 1, bytes((0x90, 60, 100))),
                (480, 1, bytes((0x90, 64, 90))),
                (960, 0, bytes((0x80, 60, 0))),
                (960, 0, bytes((0x80, 64, 0))),
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tempo.mid"
            path.write_bytes(header + tempo + notes)
            song = MODULE.parse_midi(path)
        by_pitch = {note.pitch: note for note in song.notes}
        self.assertAlmostEqual(by_pitch[60].duration, 1.5, places=9)
        self.assertAlmostEqual(by_pitch[64].start, 0.5, places=9)
        self.assertAlmostEqual(by_pitch[64].duration, 1.0, places=9)

    def test_sustain_controller_is_parsed_and_preserves_pre_note_state(self):
        tpq = 480
        header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpq)
        track = _track(
            [
                (0, 0, bytes((0xB0, 64, 127))),
                (120, 1, bytes((0x90, 60, 100))),
                (360, 0, bytes((0x80, 60, 0))),
                (480, 0, bytes((0xB0, 64, 0))),
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pedal.mid"
            path.write_bytes(header + track)
            song = MODULE.parse_midi(path)
        self.assertEqual(
            song.controls,
            (
                MODULE.MidiControl(0.0, 0, 64, 127),
                MODULE.MidiControl(0.375, 0, 64, 0),
            ),
        )

    def test_note_geometry_hits_and_leaves_the_strike_line_exactly(self):
        note = MODULE.MidiNote(60, 100, 0.75, 1.9)
        start_center, start_size = MODULE.note_rect(note, MODULE._visual_start(note))
        end_center, end_size = MODULE.note_rect(note, MODULE._rain_end(note))
        self.assertAlmostEqual(start_center.y - start_size.y / 2, MODULE.STRIKE_Y, places=12)
        self.assertAlmostEqual(end_center.y + end_size.y / 2, MODULE.STRIKE_Y, places=12)
        self.assertAlmostEqual(
            start_size.y, MODULE.visual_note_duration(note.duration) * MODULE.FALL_SPEED, places=12
        )

    def test_long_visual_note_durations_are_logarithmically_compressed(self):
        self.assertAlmostEqual(MODULE.visual_note_duration(0.25), 0.25)
        self.assertAlmostEqual(MODULE.visual_note_duration(1.0), 1.0)
        self.assertAlmostEqual(MODULE.visual_note_duration(2.0), 1.5)
        self.assertAlmostEqual(MODULE.visual_note_duration(4.0), 2.0)
        self.assertAlmostEqual(MODULE.visual_note_duration(6.0), 1.0 + 0.5 * 2.584962500721156)

    def test_key_press_still_uses_uncompressed_midi_note_duration(self):
        note = MODULE.MidiNote(60, 100, 0.0, 6.0)
        notes = (note,)
        self.assertIn(60, MODULE._active_pitches(notes, MODULE.LEAD_TIME + 5.5))
        self.assertNotIn(60, MODULE._active_pitches(notes, MODULE.LEAD_TIME + 6.0))
        self.assertLess(MODULE._rain_end(note), MODULE._visual_end(note))

    def test_synthesized_audio_is_stereo_and_matches_song_duration(self):
        song = MODULE.MidiSong(
            (
                MODULE.MidiNote(60, 100, 0.0, 0.25),
                MODULE.MidiNote(67, 90, 0.10, 0.40),
            ),
            0.40,
            480,
            "test",
        )
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "synth.wav"
            MODULE.synthesize_song(song, output, sample_rate=8_000)
            with wave.open(str(output), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 2)
                self.assertEqual(wav.getframerate(), 8_000)
                self.assertEqual(wav.getnframes(), 3_200)
                frames = wav.readframes(wav.getnframes())
        self.assertNotEqual(frames, bytes(len(frames)))

    def test_explicit_builtin_backend_never_requires_soundfont(self):
        backend, soundfont = MODULE.resolve_synth_backend("builtin")
        self.assertEqual(backend, "builtin")
        self.assertIsNone(soundfont)

    def test_soundfont_backend_preserves_natural_release_tail(self):
        soundfont = MODULE.find_soundfont()
        if soundfont is None or MODULE._fluidsynth_library() is None:
            self.skipTest("libfluidsynth + SoundFont are not installed")
        song = MODULE.MidiSong(
            (MODULE.MidiNote(60, 110, 0.0, 0.20),),
            0.20,
            480,
            "soundfont-test",
        )
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "soundfont.wav"
            MODULE.synthesize_song_soundfont(
                song, output, soundfont=soundfont, sample_rate=8_000, tail_seconds=0.30
            )
            with wave.open(str(output), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 2)
                self.assertEqual(wav.getframerate(), 8_000)
                self.assertEqual(wav.getnframes(), 4_000)
                frames = wav.readframes(wav.getnframes())
        sounding = frames[: round(0.20 * 8_000) * 4]
        tail = frames[round(0.20 * 8_000) * 4 :]
        self.assertNotEqual(sounding, bytes(len(sounding)))
        self.assertNotEqual(tail, bytes(len(tail)))

    def test_default_scene_builds_and_evaluates_random_access(self):
        scene, song = MODULE._build_scene()
        self.assertGreater(scene.duration, MODULE.LEAD_TIME + song.duration)
        for time in (0.0, MODULE.LEAD_TIME, scene.duration / 2, scene.duration):
            snapshot = scene.evaluate(time)
            self.assertGreaterEqual(len(snapshot.batches), 4)


if __name__ == "__main__":
    unittest.main()
