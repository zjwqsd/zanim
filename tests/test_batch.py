import unittest

from zanim import Color, Transform2D, Vec2
from zanim.batch import BatchObject2D, CircleSet, LineSet, RectSet
from zanim.space import Linear2D


class BatchGeometryTests(unittest.TestCase):
    def test_line_set_validates_lengths(self):
        with self.assertRaises(ValueError):
            LineSet((Vec2(),), (), (Color(1, 2, 3),), (0.1,))

    def test_circle_and_rect_set_validate_per_element_style(self):
        circles = CircleSet(
            centers=(Vec2(-1, 0), Vec2(1, 0)),
            radii=(0.2, 0.4),
            fills=(Color(10, 20, 30), Color(40, 50, 60)),
        )
        rects = RectSet(centers=(Vec2(),), sizes=(Vec2(1, 2),), fills=(Color(1, 2, 3),))
        self.assertEqual(len(circles), 2)
        self.assertEqual(len(rects), 1)

    def test_batch_object_uses_same_transform_semantics(self):
        batch = BatchObject2D(
            CircleSet((Vec2(),), (0.2,), (Color(255, 255, 255),)),
            transform=Transform2D.translation(2, 3),
        )
        batch.apply_linear_local(Linear2D.scaling(2, 1))
        self.assertEqual(batch.transform.tx, 2)
        self.assertEqual(batch.transform.ty, 3)
        self.assertEqual(batch.transform.xx, 2)


if __name__ == "__main__":
    unittest.main()
