import unittest

from zanim import Circle, Object2D, Scene, Square, Transform2D


class ParallelTimelineTests(unittest.TestCase):
    def test_parallel_clips_share_base_time_and_cursor_uses_latest_end(self):
        a = Object2D(Square(1))
        b = Object2D(Circle(1))
        scene = Scene().add(a, b)
        with scene.parallel():
            ca = scene.play_transform(a, Transform2D.translation(1, 0), duration=1.0)
            cb = scene.play_transform(b, Transform2D.translation(0, 1), duration=0.8, at=0.2)
        self.assertEqual(ca.span.start, 0.0)
        self.assertEqual(cb.span.start, 0.2)
        self.assertEqual(scene.timeline.cursor, 1.0)

    def test_parallel_transform_evaluation_is_random_access(self):
        a = Object2D(Square(1))
        b = Object2D(Circle(1))
        scene = Scene().add(a, b)
        with scene.parallel():
            scene.play_transform(a, Transform2D.translation(2, 0), duration=2.0)
            scene.play_transform(b, Transform2D.translation(0, 3), duration=2.0)
        mid = scene.evaluate(1.0)
        self.assertAlmostEqual(mid.objects[0].snapshot.transform.tx, 1.0)
        self.assertAlmostEqual(mid.objects[1].snapshot.transform.ty, 1.5)

    def test_wait_inside_parallel_is_rejected(self):
        scene = Scene()
        with self.assertRaises(ValueError):
            with scene.parallel():
                scene.wait(1.0)


if __name__ == "__main__":
    unittest.main()
