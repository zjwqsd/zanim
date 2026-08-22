import unittest

from zanim import Canvas, Circle, Color, Scene, Style
from zanim.raster import AlphaMaskSource, SceneRasterSource


class OffscreenMaskTests(unittest.TestCase):
    def test_scene_raster_source_keeps_transparent_background(self):
        sub = Scene(canvas=Canvas(width=64, height=64, unit_size=20), fps=10)
        sub.add(Circle(1, style=Style(fill=Color(255, 0, 0), stroke=None)))
        sub.wait(1)
        frame = SceneRasterSource(sub).frame_at(0.5)
        center = (32 * 64 + 32) * 4
        self.assertGreater(frame.rgba[center + 3], 200)
        self.assertEqual(frame.rgba[3], 0)

    def test_alpha_mask_multiplies_content_alpha(self):
        canvas = Canvas(width=64, height=64, unit_size=20)
        content = Scene(canvas=canvas, fps=10)
        content.add(Circle(1.3, style=Style(fill=Color(255, 0, 0), stroke=None)))
        content.wait(1)
        mask = Scene(canvas=canvas, fps=10)
        mask.add(Circle(0.5, style=Style(fill=Color(255, 255, 255), stroke=None)))
        mask.wait(1)
        frame = AlphaMaskSource(SceneRasterSource(content), SceneRasterSource(mask)).frame_at(0.5)
        center = (32 * 64 + 32) * 4
        outside = (32 * 64 + 52) * 4
        self.assertGreater(frame.rgba[center + 3], 200)
        self.assertEqual(frame.rgba[outside + 3], 0)


if __name__ == "__main__":
    unittest.main()
