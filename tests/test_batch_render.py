import unittest

from zanim import (
    BatchObject2D, Canvas, Color, Object2D, RectSet, Rectangle, Scene,
    Transform2D, Vec2,
)
from zanim.render.frame import render_snapshot_rgb0


class BatchRenderTests(unittest.TestCase):
    @staticmethod
    def _pixels(scene: Scene) -> bytes:
        buffer = bytearray(scene.width * scene.height * 4)
        render_snapshot_rgb0(buffer, scene.evaluate(0.0), scene.canvas)
        return bytes(buffer)

    def test_axis_aligned_fill_rect_fast_path_matches_object_rectangle(self):
        canvas = Canvas(320, 240, 50)
        color = Color(120, 190, 240, 173)

        batch_scene = Scene(canvas=canvas)
        batch_scene.add(BatchObject2D(
            RectSet((Vec2(),), (Vec2(1, 1),), (color,))
        ))

        object_scene = Scene(canvas=canvas)
        object_scene.add(Object2D(Rectangle(1, 1), fill=color))

        self.assertEqual(self._pixels(batch_scene), self._pixels(object_scene))

    def test_rotated_rect_batch_falls_back_without_changing_render_semantics(self):
        canvas = Canvas(320, 240, 50)
        color = Color(220, 120, 170, 201)
        transform = Transform2D.rotation(0.37)

        batch_scene = Scene(canvas=canvas)
        batch_scene.add(BatchObject2D(
            RectSet((Vec2(),), (Vec2(1.2, 0.7),), (color,)),
            transform=transform,
        ))

        object_scene = Scene(canvas=canvas)
        object_scene.add(Object2D(
            Rectangle(1.2, 0.7), transform=transform, fill=color
        ))

        self.assertEqual(self._pixels(batch_scene), self._pixels(object_scene))


if __name__ == "__main__":
    unittest.main()
