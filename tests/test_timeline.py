import unittest

from zanim import (
    Circle,
    Easing,
    Object2D,
    Scene,
    Square,
    Timeline,
    Transform2D,
)


class TimelineTests(unittest.TestCase):
    def test_wait_only_advances_cursor(self):
        timeline = Timeline()
        span = timeline.wait(1.25)
        self.assertEqual(span.start, 0.0)
        self.assertEqual(span.end, 1.25)
        self.assertEqual(timeline.cursor, 1.25)
        self.assertEqual(timeline.clips, [])

    def test_easing_is_clamped_and_random_access(self):
        self.assertEqual(Easing.LINEAR.apply(-1), 0)
        self.assertEqual(Easing.LINEAR.apply(2), 1)
        self.assertAlmostEqual(Easing.SMOOTHSTEP.apply(0.5), 0.5)


class SceneTimelineTests(unittest.TestCase):
    def test_transform_clip_mutates_authoring_object_but_history_is_reconstructed(self):
        obj = Object2D(Square(2), transform=Transform2D.translation(1, 0))
        scene = Scene().add(obj)
        target = Transform2D.translation(5, 2)

        scene.play_transform(obj, target, duration=2, easing=Easing.LINEAR)

        self.assertEqual(obj.transform, target)
        self.assertEqual(scene.evaluate(-1).objects[0].snapshot.transform, Transform2D.translation(1, 0))
        self.assertEqual(scene.evaluate(3).objects[0].snapshot.transform, target)
        mid = scene.evaluate(1).objects[0].snapshot.transform
        self.assertEqual(mid, Transform2D.translation(3, 1))

    def test_successive_transform_clips_are_seekable(self):
        obj = Object2D(Square(2))
        scene = Scene().add(obj)
        t1 = Transform2D.translation(2, 0)
        t2 = Transform2D.translation(2, 3)
        scene.play_transform(obj, t1, duration=1, easing=Easing.LINEAR)
        scene.play_transform(obj, t2, duration=2, easing=Easing.LINEAR)

        self.assertEqual(obj.transform, t2)
        self.assertEqual(scene.evaluate(0.5).objects[0].snapshot.transform.tx, 1)
        second = scene.evaluate(2).objects[0].snapshot.transform
        self.assertEqual(second.tx, 2)
        self.assertEqual(second.ty, 1.5)
        # Seek backwards after evaluating a later time.
        self.assertEqual(scene.evaluate(0.5).objects[0].snapshot.transform.tx, 1)

    def test_interpolation_is_transient_and_does_not_mutate_endpoints(self):
        a = Object2D(Square(2), transform=Transform2D.translation(-2, 0))
        b = Object2D(Circle(1), transform=Transform2D.translation(2, 0))
        scene = Scene().add(a, b)
        a_before, b_before = a.transform, b.transform

        scene.play_interpolation(a, b, duration=2, easing=Easing.LINEAR)

        self.assertEqual(a.transform, a_before)
        self.assertEqual(b.transform, b_before)
        self.assertEqual(len(scene.evaluate(-0.1).transients), 0)
        middle = scene.evaluate(1)
        self.assertEqual(len(middle.transients), 1)
        self.assertAlmostEqual(middle.transients[0].alpha, 0.5)
        self.assertEqual(len(scene.evaluate(2.1).transients), 0)

    def test_scene_requires_registered_objects(self):
        scene = Scene()
        obj = Object2D(Square(1))
        with self.assertRaises(ValueError):
            scene.play_transform(obj, Transform2D.translation(1, 0))


if __name__ == "__main__":
    unittest.main()

class TimelineRandomAccessTests(unittest.TestCase):
    def test_evaluation_order_does_not_change_results(self):
        obj = Object2D(Square(1))
        scene = Scene().add(obj)
        scene.play_transform(obj, Transform2D.translation(2, 0), duration=1, easing=Easing.LINEAR)
        scene.play_transform(obj, Transform2D.translation(2, 4), duration=2, easing=Easing.LINEAR)
        times = [0.2, 1.4, 2.8, 0.7, 1.4]
        values = [scene.evaluate(t).objects[0].snapshot.transform for t in times]
        self.assertEqual(values[1], values[4])
        self.assertEqual(scene.evaluate(0.2).objects[0].snapshot.transform, values[0])
