import unittest

from zanim import Circle, Object2D, Scene, Transform2D


class TimelineIndexTests(unittest.TestCase):
    def test_same_channel_reverse_time_authoring_is_rejected(self):
        obj = Object2D(Circle(1))
        scene = Scene().add(obj)
        with self.assertRaisesRegex(ValueError, "chronological order"):
            with scene.parallel():
                scene.play_transform(obj, Transform2D.translation(3, 0), duration=1, at=2)
                scene.play_transform(obj, Transform2D.translation(1, 0), duration=1, at=0)

    def test_different_objects_may_use_arbitrary_at_offsets(self):
        a, b = Object2D(Circle(1)), Object2D(Circle(1))
        scene = Scene().add(a, b)
        with scene.parallel():
            scene.play_transform(a, Transform2D.translation(3, 0), duration=1, at=2)
            scene.play_transform(b, Transform2D.translation(1, 0), duration=1, at=0)
        self.assertAlmostEqual(scene.evaluate(0.5).objects[1].snapshot.transform.tx, 0.5)
        self.assertAlmostEqual(scene.evaluate(2.5).objects[0].snapshot.transform.tx, 1.5)


if __name__ == '__main__':
    unittest.main()
