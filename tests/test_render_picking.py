import unittest

from zanim import Canvas, Circle, Color, Rectangle, Scene, Style, Transform2D
from zanim.render.frame import pick_snapshot_object


class RenderPickingTests(unittest.TestCase):
    def test_topmost_real_raster_wins(self):
        scene = Scene(canvas=Canvas(200, 120, 12), fps=10)
        scene.add(Rectangle(6, 4, style=Style(fill=Color(50, 100, 200))))
        scene.add(
            Circle(1, style=Style(fill=Color(240, 80, 80)), transform=Transform2D.translation(1, 0))
        )
        snapshot = scene.evaluate(0)
        self.assertEqual(pick_snapshot_object(snapshot, scene.canvas, 100, 60), 2)

    def test_empty_or_non_rendering_pixels_are_not_pickable(self):
        scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
        scene.add(Circle(1))  # no fill or stroke
        snapshot = scene.evaluate(0)
        self.assertIsNone(pick_snapshot_object(snapshot, scene.canvas, 40, 24))
        self.assertIsNone(pick_snapshot_object(snapshot, scene.canvas, 0, 0))

    def test_out_of_bounds_pick_is_rejected(self):
        scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
        snapshot = scene.evaluate(0)
        with self.assertRaises(ValueError):
            pick_snapshot_object(snapshot, scene.canvas, 80, 24)


if __name__ == "__main__":
    unittest.main()
