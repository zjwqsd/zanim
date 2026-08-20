import unittest

from zanim import (
    Circle,
    Linear2D,
    Object2D,
    ObjectInterpolation,
    Square,
    Transform2D,
    Vec2,
)


class ObjectInterpolationLifetimeTests(unittest.TestCase):
    def test_interpolation_snapshots_two_distinct_objects(self):
        source = Object2D(
            Square(2),
            transform=Transform2D.translation(-2, 0),
        )
        target = Object2D(
            Circle(1),
            transform=Transform2D.translation(3, 1),
        )

        transition = ObjectInterpolation.from_objects(source, target)

        self.assertIsNot(source, target)
        self.assertEqual(transition.source.geometry, Square(2))
        self.assertEqual(transition.target.geometry, Circle(1))
        self.assertEqual(transition.source.transform, Transform2D.translation(-2, 0))
        self.assertEqual(transition.target.transform, Transform2D.translation(3, 1))

    def test_later_real_transform_does_not_rewrite_interpolation_snapshot(self):
        source = Object2D(
            Square(2),
            transform=Transform2D.translation(2, 3),
        )
        target = Object2D(Circle(1))
        transition = ObjectInterpolation.from_objects(source, target)
        frozen_source_transform = transition.source.transform

        # This is a real state change on the persistent source object.
        source.apply_linear_local(Linear2D.scaling(2, 1))

        self.assertNotEqual(source.transform, frozen_source_transform)
        self.assertEqual(transition.source.transform, frozen_source_transform)
        self.assertEqual(source.local_to_world(Vec2()), Vec2(2, 3))


if __name__ == "__main__":
    unittest.main()
