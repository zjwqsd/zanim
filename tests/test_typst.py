import unittest

from zanim import Math, Text


class TypstIntegrationTests(unittest.TestCase):
    def test_text_compiles_to_one_group_per_visible_glyph(self):
        text = Text('Hi 神经', font_size=24, font='Noto Sans CJK SC')
        self.assertEqual(text.document.group_count, 4)
        self.assertEqual(len(text.document.paths), 4)

    def test_math_uses_same_vector_document(self):
        math = Math('y = W x + b', font_size=24)
        self.assertGreaterEqual(math.document.group_count, 6)
        self.assertGreater(len(math.document.paths), 0)


if __name__ == '__main__':
    unittest.main()

class MathConstructTests(unittest.TestCase):
    def test_math_supports_subscript_greek_hat_and_functions(self):
        formulas = (
            Math('z_1 = x W_1 + b_1', font_size=24),
            Math('h = sigma(z_1)', font_size=24),
            Math('hat(y) = "softmax"(z_2)', font_size=24),
        )
        for formula in formulas:
            self.assertGreater(formula.document.group_count, 0)
            self.assertGreater(len(formula.document.paths), 0)
