import math
import unittest

from zanim import Circle, Linear2D, Object2D, Polygon, Rectangle, SE2, Transform2D, Vec2


class LinearObjectTransformTests(unittest.TestCase):
    def test_local_linear_keeps_world_origin_fixed(self):
        obj = Object2D(
            geometry=Rectangle(2, 1),
            transform=Transform2D.translation(2, 3),
        )
        obj.apply_linear_local(Linear2D.scaling(2, 1))
        self.assertEqual(obj.local_to_world(Vec2(0, 0)), Vec2(2, 3))
        self.assertEqual(obj.local_to_world(Vec2(1, 0)), Vec2(4, 3))

    def test_world_linear_transforms_object_position_too(self):
        obj = Object2D(
            geometry=Rectangle(2, 1),
            transform=Transform2D.translation(2, 3),
        )
        obj.apply_linear_world(Linear2D.scaling(2, 1))
        self.assertEqual(obj.local_to_world(Vec2(0, 0)), Vec2(4, 3))
        self.assertEqual(obj.local_to_world(Vec2(1, 0)), Vec2(6, 3))

    def test_arbitrary_linear_map_is_supported(self):
        obj = Object2D(Circle(1))
        linear = Linear2D(1.2, -0.4, 0.7, 0.9)
        obj.apply_linear_local(linear)
        expected = linear.apply(Vec2(2, -1))
        actual = obj.local_to_world(Vec2(2, -1))
        self.assertAlmostEqual(actual.x, expected.x)
        self.assertAlmostEqual(actual.y, expected.y)


class SE2ObjectTransformTests(unittest.TestCase):
    def test_local_se2_translation_uses_object_axes(self):
        obj = Object2D(
            geometry=Rectangle(2, 1),
            transform=Transform2D.rotation(math.pi / 2),
        )
        obj.apply_se2_local(SE2(translation=Vec2(1, 0)))
        p = obj.local_to_world(Vec2())
        self.assertAlmostEqual(p.x, 0)
        self.assertAlmostEqual(p.y, 1)

    def test_world_se2_translation_uses_world_axes(self):
        obj = Object2D(
            geometry=Rectangle(2, 1),
            transform=Transform2D.rotation(math.pi / 2),
        )
        obj.apply_se2_world(SE2(translation=Vec2(1, 0)))
        p = obj.local_to_world(Vec2())
        self.assertAlmostEqual(p.x, 1)
        self.assertAlmostEqual(p.y, 0)

    def test_se2_group_still_has_rigid_semantics(self):
        a = SE2(theta=0.7, translation=Vec2(1, -2))
        b = SE2(theta=-0.2, translation=Vec2(3, 4))
        p = Vec2(-1.5, 2.25)
        composed = (a @ b).apply(p)
        sequential = a.apply(b.apply(p))
        self.assertAlmostEqual(composed.x, sequential.x)
        self.assertAlmostEqual(composed.y, sequential.y)
        back = a.inverse().apply(a.apply(p))
        self.assertAlmostEqual(back.x, p.x)
        self.assertAlmostEqual(back.y, p.y)


class GeometryTests(unittest.TestCase):
    def test_shape_validation(self):
        with self.assertRaises(ValueError):
            Circle(0)
        with self.assertRaises(ValueError):
            Polygon((Vec2(0, 0), Vec2(1, 0)))


if __name__ == "__main__":
    unittest.main()
