import unittest
from math import pi

from zanim import Circle, Scene, Transform2D


class TransformFunctionTests(unittest.TestCase):
    def test_random_access_function_transform(self):
        obj = Circle(1)
        scene = Scene()
        scene.add(obj)
        scene.transform_function(
            obj,
            lambda a: Transform2D.translation(4 * a, 2 * a).rotate(pi * a),
            duration=2,
        )
        mid = scene.evaluate(1).objects[0].snapshot.transform
        self.assertAlmostEqual(mid.tx, 2.0)
        self.assertAlmostEqual(mid.ty, 1.0)
        # Seek backwards and get exactly the same state.
        again = scene.evaluate(1).objects[0].snapshot.transform
        self.assertEqual(mid, again)

    def test_function_and_linear_transform_share_channel(self):
        obj = Circle(1)
        scene = Scene()
        scene.add(obj)
        scene.transform_function(obj, lambda a: Transform2D.translation(a, 0), duration=2)
        with self.assertRaises(ValueError):
            scene._timeline.add_transform(
                1, Transform2D(), Transform2D.translation(1, 0), duration=1, at=-1.5
            )


if __name__ == "__main__":
    unittest.main()
