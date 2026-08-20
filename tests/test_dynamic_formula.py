import unittest

from zanim import (
    Canvas, Circle, Color, DynamicNumber, FormulaLiteral, FormulaTemplate,
    MatrixSlot, NumberFormat, NumberSlot, Object2D, ObjectSlot, Scene,
    Style, Transform2D,
)


class DynamicNumberTests(unittest.TestCase):
    def test_fixed_width_and_random_access(self):
        fmt = NumberFormat(width=3, sign="space")
        number = DynamicNumber(lambda t: int(t * 10) - 4, number_format=fmt, font_size=24)
        d0 = number.document_at(0.0)
        d1 = number.document_at(0.7)
        d0_again = number.document_at(0.0)
        self.assertEqual(d0.width, d1.width)
        self.assertIs(d0, d0_again)
        self.assertEqual(number.value_at(0.7), 3)

    def test_overflow_rejected(self):
        fmt = NumberFormat(width=2)
        with self.assertRaises(ValueError):
            fmt.format(123)


class FormulaTemplateTests(unittest.TestCase):
    def test_matrix_layout_is_fixed_while_values_change(self):
        fmt = NumberFormat(width=2, sign="negative")
        template = FormulaTemplate(
            MatrixSlot("A", 2, 2, fmt, font_size=22),
            FormulaLiteral("=", font_size=30),
            MatrixSlot("B", 2, 2, fmt, font_size=22),
        )
        scene = Scene(canvas=Canvas(width=640, height=360, unit_size=80))
        instance = template.mount(
            scene,
            {
                "A": lambda t: ((1 + int(t), 2), (3, 4)),
                "B": lambda t: ((5, 6), (7, 8 + int(t))),
            },
        )
        self.assertGreater(template.width, 0)
        self.assertEqual(instance.width, template.width)
        a_numbers = [obj for obj in instance.slots["A"] if isinstance(obj, DynamicNumber)]
        self.assertEqual(len(a_numbers), 4)
        transforms = tuple(obj.transform for obj in a_numbers)
        scene.evaluate(0.0)
        scene.evaluate(3.0)
        self.assertEqual(transforms, tuple(obj.transform for obj in a_numbers))

    def test_object_slot_accepts_geometry_without_reflow(self):
        slot = ObjectSlot("shape", 1.4, 1.0)
        template = FormulaTemplate(FormulaLiteral("x", font_size=28), slot, FormulaLiteral("=", font_size=28))
        width = template.width
        circle = Object2D(Circle(1.0), style=Style(fill=Color(100, 180, 255), stroke=None))
        scene = Scene(canvas=Canvas(width=640, height=360, unit_size=80))
        instance = template.mount(scene, {"shape": circle})
        self.assertEqual(template.width, width)
        self.assertIn(circle, instance.slots["shape"])
        self.assertNotEqual(circle.transform, Transform2D())


if __name__ == "__main__":
    unittest.main()
