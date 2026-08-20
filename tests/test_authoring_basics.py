import unittest

from zanim import (
    Arrow, Canvas, Color, Dot, DOWN, DynamicNumber, LEFT, NumberFormat,
    NumberLine, Object2D, RIGHT, Scene, ScalarValue, Square, UP, Vec2,
)
from zanim.render.wire import encode_snapshot


class AuthoringBasicsTests(unittest.TestCase):
    def test_to_edge(self):
        obj = Object2D(Square(1))
        canvas = Canvas(width=800, height=600, unit_size=100)
        obj.to_edge(canvas, RIGHT, buff=.25)
        self.assertAlmostEqual(obj.bounds().right, 3.75)
        obj.to_edge(canvas, UP, buff=.5)
        self.assertAlmostEqual(obj.bounds().top, 2.5)

    def test_common_shapes(self):
        dot = Dot(Vec2(1, 2))
        self.assertAlmostEqual(dot.bounds().center.x, 1)
        arrow = Arrow(Vec2(0,0), Vec2(2,1))
        self.assertEqual(len(arrow.children), 2)
        line = NumberLine((-2, 2), length=8)
        self.assertAlmostEqual(line.n2p(1).x, 2)
        labeled = NumberLine((-1, 1), length=4, include_numbers=True, label_font_size=12)
        self.assertGreater(len(labeled.children), 2)

    def test_scalar_value_binds_directly_to_dynamic_number(self):
        value = ScalarValue(1)
        scene = Scene().add(value)
        number = DynamicNumber(value, number_format=NumberFormat(width=3), font_size=20)
        scene.add(number)
        scene.play_value(value, 5, duration=1)
        self.assertAlmostEqual(value.value_at(.5), 3)
        self.assertIsNot(number._document_at(.5, number.document), number._document_at(0, number.document))

    def test_z_index_precedes_insertion_order(self):
        back = Object2D(Square(2), z_index=-1)
        front = Object2D(Square(1), z_index=5)
        scene = Scene().add(front, back)
        encoded = encode_snapshot(scene.evaluate(0))
        # back was inserted second but must be first in the draw stream.
        self.assertEqual(encoded.draw_items[0].index, 1)
        self.assertEqual(encoded.draw_items[1].index, 0)


if __name__ == '__main__': unittest.main()
