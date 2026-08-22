import unittest

from zanim import Circle, Scene, Square, Transform2D


class ParallelTimelineTests(unittest.TestCase):
    def test_parallel_clips_share_base_time_and_cursor_uses_latest_end(self):
        a = Square(1)
        b = Circle(1)
        scene = Scene()
        scene.add(a, b)
        with scene.parallel():
            ca = scene.transform(a, to=Transform2D.translation(1, 0), duration=1.0)
            cb = scene.transform(b, to=Transform2D.translation(0, 1), duration=0.8, at=0.2)
        self.assertEqual(ca.span.start, 0.0)
        self.assertEqual(cb.span.start, 0.2)
        self.assertEqual(scene._timeline.cursor, 1.0)

    def test_parallel_transform_evaluation_is_random_access(self):
        a = Square(1)
        b = Circle(1)
        scene = Scene()
        scene.add(a, b)
        with scene.parallel():
            scene.transform(a, to=Transform2D.translation(2, 0), duration=2.0)
            scene.transform(b, to=Transform2D.translation(0, 3), duration=2.0)
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


class ParallelDurationDefaultTests(unittest.TestCase):
    def test_parallel_duration_is_default_for_omitted_clip_durations(self):
        a = Square(1)
        b = Circle(1)
        scene = Scene()
        a, b = scene.add(a, b)

        with scene.parallel(duration=1.6):
            ca = a.move(by=(1, 0), frame=__import__("zanim").WORLD)
            cb = b.opacity(to=0.5, at=0.2)

        self.assertEqual(ca.span.duration, 1.6)
        self.assertEqual(cb.span.duration, 1.6)
        self.assertEqual(ca.span.start, 0.0)
        self.assertEqual(cb.span.start, 0.2)
        self.assertAlmostEqual(scene._timeline.cursor, 1.8)

    def test_explicit_clip_duration_overrides_parallel_default(self):
        a = Square(1)
        b = Circle(1)
        scene = Scene()
        a, b = scene.add(a, b)

        with scene.parallel(duration=1.6):
            ca = a.opacity(to=0.5)
            cb = b.opacity(to=0.5, duration=0.4, at=0.3)

        self.assertEqual(ca.span.duration, 1.6)
        self.assertEqual(cb.span.duration, 0.4)
        self.assertEqual(scene._timeline.cursor, 1.6)

    def test_parallel_default_does_not_leak_outside_block(self):
        obj = Scene().add(Square(1))
        scene = obj.scene
        with scene.parallel(duration=2.5):
            first = obj.opacity(to=0.5)
        second = obj.opacity(to=0.25)
        self.assertEqual(first.span.duration, 2.5)
        self.assertEqual(second.span.duration, 1.0)

    def test_negative_parallel_default_is_rejected(self):
        scene = Scene()
        with self.assertRaisesRegex(ValueError, "parallel duration"):
            with scene.parallel(duration=-1):
                pass
