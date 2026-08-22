import math
import unittest

import zanim
from zanim import (
    BLACK,
    BLUE,
    CYAN,
    DEGREES,
    DOWN,
    GRAY,
    GREEN,
    LEFT,
    MUTED,
    ORANGE,
    ORIGIN,
    PI,
    PINK,
    PURPLE,
    RED,
    RIGHT,
    TAU,
    TRANSPARENT,
    UP,
    WHITE,
    YELLOW,
    Color,
    Vec2,
)


class CommonConstantsTests(unittest.TestCase):
    def test_requested_default_palette(self):
        self.assertEqual(BLUE, Color(96, 166, 255))
        self.assertEqual(GREEN, Color(82, 205, 150))
        self.assertEqual(RED, Color(245, 92, 105))

    def test_palette_is_convenience_not_a_color_restriction(self):
        custom = Color(12, 34, 56, 78)
        self.assertEqual(custom, Color(12, 34, 56, 78))
        self.assertNotEqual(custom, BLUE)

    def test_common_palette_exports(self):
        expected = {
            "BLACK": BLACK,
            "BLUE": BLUE,
            "CYAN": CYAN,
            "GRAY": GRAY,
            "GREEN": GREEN,
            "MUTED": MUTED,
            "ORANGE": ORANGE,
            "PINK": PINK,
            "PURPLE": PURPLE,
            "RED": RED,
            "TRANSPARENT": TRANSPARENT,
            "WHITE": WHITE,
            "YELLOW": YELLOW,
        }
        for name, value in expected.items():
            with self.subTest(name=name):
                self.assertIs(getattr(zanim, name), value)
        self.assertEqual(TRANSPARENT.a, 0)
        self.assertIs(MUTED, GRAY)

    def test_common_geometry_and_angle_constants(self):
        self.assertEqual(ORIGIN, Vec2(0, 0))
        self.assertEqual(RIGHT, Vec2(1, 0))
        self.assertEqual(LEFT, Vec2(-1, 0))
        self.assertEqual(UP, Vec2(0, 1))
        self.assertEqual(DOWN, Vec2(0, -1))
        self.assertEqual(PI, math.pi)
        self.assertEqual(TAU, math.tau)
        self.assertEqual(180 * DEGREES, math.pi)


if __name__ == "__main__":
    unittest.main()
