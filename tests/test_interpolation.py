import unittest

from zanim import Circle, Square, Transform2D, Vec2
from zanim.geometry import CircleGeometry, SquareGeometry
from zanim.interpolation import ObjectInterpolation
from zanim.space import Linear2D


class ObjectInterpolationLifetimeTests(unittest.TestCase):
    def test_interpolation_snapshots_two_distinct_objects(self):
        source = Square(2, transform=Transform2D.translation(-2, 0))
        target = Circle(1, transform=Transform2D.translation(3, 1))

        transition = ObjectInterpolation.from_objects(source, target)

        self.assertIsNot(source, target)
        self.assertEqual(transition.source.geometry, SquareGeometry(2))
        self.assertEqual(transition.target.geometry, CircleGeometry(1))
        self.assertEqual(transition.source.transform, Transform2D.translation(-2, 0))
        self.assertEqual(transition.target.transform, Transform2D.translation(3, 1))

    def test_later_real_transform_does_not_rewrite_interpolation_snapshot(self):
        source = Square(2, transform=Transform2D.translation(2, 3))
        target = Circle(1)
        transition = ObjectInterpolation.from_objects(source, target)
        frozen_source_transform = transition.source.transform

        # This is a real state change on the persistent source object.
        source.apply_linear_local(Linear2D.scaling(2, 1))

        self.assertNotEqual(source.transform, frozen_source_transform)
        self.assertEqual(transition.source.transform, frozen_source_transform)
        self.assertEqual(source.local_to_world(Vec2()), Vec2(2, 3))


if __name__ == "__main__":
    unittest.main()
