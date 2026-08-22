import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zanim import Canvas, Circle, Object2D, Scene, Transform2D


class RenderSelectionTests(unittest.TestCase):
    def test_static_scene_render_selects_frame_zero(self):
        scene = Scene()
        scene.add(Object2D(Circle(1)))
        target = Path("static.png")
        with patch.object(Scene, "render_frame", return_value=target) as frame, patch.object(
            Scene, "render_video"
        ) as video:
            self.assertEqual(scene.render(target), target)
            frame.assert_called_once_with(target, 0.0)
            video.assert_not_called()

    def test_animated_scene_render_selects_absolute_frame(self):
        scene = Scene()
        scene.wait(5)
        target = Path("frame.png")
        with patch.object(Scene, "render_frame", return_value=target) as frame:
            self.assertEqual(scene.render(target, time=3.25), target)
            frame.assert_called_once_with(target, 3.25)

    def test_animated_scene_render_selects_range(self):
        scene = Scene()
        scene.wait(5)
        target = Path("slice.mp4")
        with patch.object(Scene, "render_video", return_value=target) as video:
            self.assertEqual(scene.render(target, start=2, end=4, workers=3), target)
            video.assert_called_once_with(target, start=2.0, end=4, workers=3)

    def test_render_rejects_ambiguous_selectors(self):
        scene = Scene()
        scene.wait(5)
        with self.assertRaisesRegex(ValueError, "time cannot be combined"):
            scene.render("x.png", time=2, start=1)

    def test_segment_video_evaluates_only_requested_times(self):
        scene = Scene(canvas=Canvas(64, 64, 10), fps=10)
        circle = Object2D(Circle(1))
        scene.add(circle)
        scene.transform(circle, to=Transform2D.translation(2, 0), duration=2)

        evaluated: list[float] = []
        original = Scene.evaluate

        def record(scene_self, time):
            evaluated.append(float(time))
            return original(scene_self, time)

        with tempfile.TemporaryDirectory() as td, patch.object(Scene, "evaluate", record):
            output = Path(td) / "slice.mp4"
            scene.render_video(output, start=0.7, end=1.2, workers=2)
            self.assertTrue(output.is_file())
            proc = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=nw=1:nk=1", str(output),
                ],
                check=True, capture_output=True, text=True,
            )
            self.assertAlmostEqual(float(proc.stdout.strip()), 0.5, places=2)

        self.assertEqual(len(evaluated), 5)
        self.assertGreaterEqual(min(evaluated), 0.7 - 1e-12)
        self.assertLess(max(evaluated), 1.2)


if __name__ == "__main__":
    unittest.main()
