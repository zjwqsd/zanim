import math
import unittest

from zanim import SE2, Circle, Polygon, Transform2D, Vec2
from zanim.space import Linear2D


class TransformCompositionTests(unittest.TestCase):
    def test_local_linear_keeps_translation_fixed(self):
        transform = Transform2D.translation(2, 3) @ Linear2D.scaling(2, 1).as_affine()
        self.assertEqual(transform.apply(Vec2(0, 0)), Vec2(2, 3))
        self.assertEqual(transform.apply(Vec2(1, 0)), Vec2(4, 3))

    def test_world_linear_transforms_translation_too(self):
        transform = Linear2D.scaling(2, 1).as_affine() @ Transform2D.translation(2, 3)
        self.assertEqual(transform.apply(Vec2(0, 0)), Vec2(4, 3))
        self.assertEqual(transform.apply(Vec2(1, 0)), Vec2(6, 3))

    def test_arbitrary_linear_map_is_supported(self):
        linear = Linear2D(1.2, -0.4, 0.7, 0.9)
        point = Vec2(2, -1)
        self.assertEqual(linear.as_affine().apply(point), linear.apply(point))

    def test_se2_local_and_world_composition_differ(self):
        base = Transform2D.rotation(math.pi / 2)
        delta = SE2(translation=Vec2(1, 0)).as_affine()
        local = base @ delta
        world = delta @ base
        self.assertAlmostEqual(local.apply(Vec2()).x, 0)
        self.assertAlmostEqual(local.apply(Vec2()).y, 1)
        self.assertAlmostEqual(world.apply(Vec2()).x, 1)
        self.assertAlmostEqual(world.apply(Vec2()).y, 0)

    def test_se2_group_has_rigid_semantics(self):
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
