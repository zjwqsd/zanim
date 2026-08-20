import unittest

from zanim import Canvas, Color, FormulaLiteral, FormulaTemplate, NumberFormat, NumberSlot, Scene, ScriptSlots


class ScriptSlotsTests(unittest.TestCase):
    def test_integral_limits_are_fixed_typst_scripts(self):
        fmt = NumberFormat(width=4, decimals=1, sign="space")
        limits = ScriptSlots(
            "integral",
            sub=NumberSlot("a", fmt, font_size=24, align="center"),
            sup=NumberSlot("b", fmt, font_size=24, align="center"),
        )
        template = FormulaTemplate(limits, FormulaLiteral("f(x) dif x", font_size=36), font_size=36)
        scene = Scene(canvas=Canvas(width=640, height=360, unit_size=75))
        instance = template.mount(scene, {"a": lambda t: -2 + 0.1*t, "b": lambda t: 1 + 0.2*t})
        self.assertIn("a", instance.slots)
        self.assertIn("b", instance.slots)
        a = instance.slots["a"][0]
        b = instance.slots["b"][0]
        ta, tb = a.transform, b.transform
        scene.evaluate(0.0)
        scene.evaluate(2.0)
        self.assertEqual(a.transform, ta)
        self.assertEqual(b.transform, tb)
        self.assertLess(a.transform.ty, b.transform.ty)

    def test_script_slot_names_must_be_unique(self):
        fmt = NumberFormat(width=3, decimals=1)
        with self.assertRaises(ValueError):
            ScriptSlots("integral", NumberSlot("x", fmt), NumberSlot("x", fmt))


if __name__ == '__main__':
    unittest.main()
