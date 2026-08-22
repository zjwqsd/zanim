import math
import unittest

from zanim import (
    Circle,
    Color,
    Group,
    Scene,
    Style,
    Transform2D,
    Vec2,
    affine2d,
)

WHITE = Color(240, 240, 240)
RED = Color(220, 60, 70)


class ConstructorSugarTests(unittest.TestCase):
    def test_color_with_alpha_preserves_rgb(self):
        self.assertEqual(RED.with_alpha(128), Color(220, 60, 70, 128))
        with self.assertRaises(ValueError):
            RED.with_alpha(300)
        with self.assertRaises(TypeError):
            RED.with_alpha(128.5)

    def test_object_style_sugar_is_explicit(self):
        outline = Circle(1, stroke=WHITE, stroke_width=0.045)
        self.assertEqual(outline.style, Style.outline(WHITE, 0.045))

        fill = Circle(1, fill=RED.with_alpha(128))
        self.assertEqual(fill.style, Style.solid(RED.with_alpha(128)))

        painted = Circle(1, fill=RED.with_alpha(128), stroke=WHITE, stroke_width=0.05)
        self.assertEqual(painted.style, Style.paint(RED.with_alpha(128), WHITE, 0.05))

    def test_style_and_style_sugar_cannot_mix(self):
        with self.assertRaisesRegex(ValueError, "either style="):
            Circle(1, style=Style.solid(RED), stroke=WHITE)
        with self.assertRaisesRegex(ValueError, "stroke_width requires"):
            Circle(1, fill=RED, stroke_width=0.04)

    def test_object_transform_sugar_uses_fixed_affine_order(self):
        obj = Circle(1, position=(2, -1), rotation=0.3, scale=(2, 0.5), shear=(0.1, -0.2))
        self.assertEqual(
            obj.transform,
            affine2d(position=(2, -1), rotation=0.3, scale=(2, 0.5), shear=(0.1, -0.2)),
        )

    def test_transform_and_transform_sugar_cannot_mix(self):
        with self.assertRaisesRegex(ValueError, "either transform="):
            Circle(1, transform=Transform2D.translation(1, 0), scale=2)

    def test_group_transform_sugar_is_parent_relative(self):
        child = Circle(0.2)
        group = Group([child], position=(2, 1), rotation=math.pi / 2)
        expected = affine2d(position=(2, 1), rotation=math.pi / 2)
        self.assertEqual(group.transform, expected)

        scene = Scene()
        group = scene.add(group)
        self.assertEqual(group.world_point(), Vec2(2, 1))

    def test_bound_style_sugar_is_only_timeline_sugar(self):
        obj = Circle(1, stroke=WHITE)
        scene = Scene()
        obj = scene.add(obj)

        obj.paint(fill=RED.with_alpha(128), stroke=RED, stroke_width=0.045)
        self.assertEqual(obj.raw.style, Style.paint(RED.with_alpha(128), RED, 0.045))
        self.assertEqual(len(scene._timeline.clips), 1)

        obj.outline(WHITE, width=0.02)
        self.assertEqual(obj.raw.style, Style.outline(WHITE, 0.02))

        obj.fill(RED)
        self.assertEqual(obj.raw.style, Style.solid(RED))


if __name__ == "__main__":
    unittest.main()
