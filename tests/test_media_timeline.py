import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image as PILImage
from zanim import GIF, Audio, Image, Scene, Video
from zanim.render.audio import render_audio_mix
from zanim.timeline import PlaybackClip, TimeSpan

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "tests/assets/media_demo"


class PlaybackTests(unittest.TestCase):
    def test_source_time_mapping_and_loop(self):
        clip = PlaybackClip(1, TimeSpan(2, 4), 1, 2, True, 5)
        self.assertAlmostEqual(clip.source_time(2.5), 2.0)
        self.assertAlmostEqual(clip.source_time(4.5), 2.0)

    def test_non_looping_playback_cannot_overrun_source(self):
        video = Video(MEDIA / "clip.mp4")
        scene = Scene()
        scene.add(video)
        with self.assertRaises(ValueError):
            scene.media(video, duration=3.0)

    def test_static_image_can_be_scheduled(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.png"
            PILImage.new("RGBA", (4, 2), (255, 0, 0, 255)).save(path)
            image = Image(path)
            scene = Scene()
            scene
            scene.add(image)
            scene.media(image, duration=2)
            self.assertEqual(len(scene.evaluate(1).rasters), 1)
            self.assertEqual(len(scene.evaluate(3).rasters), 0)

    def test_gif_uses_variable_frame_durations(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.gif"
            frames = [
                PILImage.new("RGBA", (2, 2), c)
                for c in ((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255))
            ]
            frames[0].save(
                path,
                save_all=True,
                append_images=frames[1:],
                duration=[100, 300, 200],
                loop=0,
            )
            gif = GIF(path)
            self.assertEqual(gif.source.frame_at(0.05).rgba[:4], bytes((255, 0, 0, 255)))
            self.assertEqual(gif.source.frame_at(0.20).rgba[:4], bytes((0, 255, 0, 255)))
            self.assertEqual(gif.source.frame_at(0.50).rgba[:4], bytes((0, 0, 255, 255)))

    def test_video_source_is_random_access(self):
        video = Video(MEDIA / "clip.mp4")
        first = bytes(video.source.frame_at(0.0).rgba)
        late = bytes(video.source.frame_at(1.5).rgba)
        again = bytes(video.source.frame_at(0.0).rgba)
        self.assertEqual(first, again)
        self.assertNotEqual(first, late)
        self.assertGreater(video.source.frame_count, 1)
        decoder = video.source._decoder
        video.source.close()
        self.assertIsNone(video.source._decoder)
        if decoder is not None:
            self.assertIsNotNone(decoder.poll())

    def test_audio_mix_is_finite_and_timeline_aligned(self):
        audio = Audio(MEDIA / "tone.wav", gain=0.2)
        scene = Scene()
        scene.add(audio)
        scene.media(audio, duration=2.0, loop=True, at=0.25)
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "mix.wav"
            render_audio_mix(scene, output, scene.duration)
            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=nw=1:nk=1",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertAlmostEqual(float(proc.stdout.strip()), 2.25, places=2)
            self.assertLess(output.stat().st_size, 2_000_000)


if __name__ == "__main__":
    unittest.main()
