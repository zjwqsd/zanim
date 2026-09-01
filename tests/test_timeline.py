import unittest

from zanim import (
    Circle,
    Easing,
    Scene,
    Square,
    Transform2D,
)
from zanim.timeline import Timeline


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
        obj = Square(2, transform=Transform2D.translation(1, 0))
        scene = Scene()
        scene.add(obj)
        target = Transform2D.translation(5, 2)

        scene.transform(obj, to=target, duration=2, easing=Easing.LINEAR)

        self.assertEqual(obj.transform, target)
        self.assertEqual(scene.evaluate(-1).objects, ())
        self.assertEqual(scene.evaluate(3).objects[0].snapshot.transform, target)
        mid = scene.evaluate(1).objects[0].snapshot.transform
        self.assertEqual(mid, Transform2D.translation(3, 1))

    def test_successive_transform_clips_are_seekable(self):
        obj = Square(2)
        scene = Scene()
        scene.add(obj)
        t1 = Transform2D.translation(2, 0)
        t2 = Transform2D.translation(2, 3)
        scene.transform(obj, to=t1, duration=1, easing=Easing.LINEAR)
        scene.transform(obj, to=t2, duration=2, easing=Easing.LINEAR)

        self.assertEqual(obj.transform, t2)
        self.assertEqual(scene.evaluate(0.5).objects[0].snapshot.transform.tx, 1)
        second = scene.evaluate(2).objects[0].snapshot.transform
        self.assertEqual(second.tx, 2)
        self.assertEqual(second.ty, 1.5)
        # Seek backwards after evaluating a later time.
        self.assertEqual(scene.evaluate(0.5).objects[0].snapshot.transform.tx, 1)

    def test_interpolation_is_transient_and_does_not_mutate_endpoints(self):
        a = Square(2, transform=Transform2D.translation(-2, 0))
        b = Circle(1, transform=Transform2D.translation(2, 0))
        scene = Scene()
        scene.add(a, b)
        a_before, b_before = a.transform, b.transform

        scene.interpolate(a, b, duration=2, easing=Easing.LINEAR)

        self.assertEqual(a.transform, a_before)
        self.assertEqual(b.transform, b_before)
        self.assertEqual(len(scene.evaluate(-0.1).transients), 0)
        middle = scene.evaluate(1)
        # interpolate() adds a third transient visual; both endpoint objects
        # remain alive and render with their own unchanged state.
        self.assertEqual(len(middle.objects), 2)
        self.assertEqual(len(middle.transients), 1)
        self.assertAlmostEqual(middle.transients[0].alpha, 0.5)
        self.assertEqual(len(scene.evaluate(2.1).transients), 0)

    def test_scene_requires_registered_objects(self):
        scene = Scene()
        obj = Square(1)
        with self.assertRaises(ValueError):
            scene.transform(obj, to=Transform2D.translation(1, 0))


if __name__ == "__main__":
    unittest.main()


class TimelineRandomAccessTests(unittest.TestCase):
    def test_evaluation_order_does_not_change_results(self):
        obj = Square(1)
        scene = Scene()
        scene.add(obj)
        scene.transform(obj, to=Transform2D.translation(2, 0), duration=1, easing=Easing.LINEAR)
        scene.transform(obj, to=Transform2D.translation(2, 4), duration=2, easing=Easing.LINEAR)
        times = [0.2, 1.4, 2.8, 0.7, 1.4]
        values = [scene.evaluate(t).objects[0].snapshot.transform for t in times]
        self.assertEqual(values[1], values[4])
        self.assertEqual(scene.evaluate(0.2).objects[0].snapshot.transform, values[0])


class ReplacementTimelineTests(unittest.TestCase):
    def test_replace_hands_off_lifetime_without_mutating_endpoints(self):
        source = Square(1, transform=Transform2D.translation(-2, 0))
        target = Circle(1, transform=Transform2D.translation(2, 0))
        source_before = source.transform
        target_before = target.transform
        scene = Scene()
        scene.add(source)
        scene.wait(0.5)
        target_handle = scene.replace(source, target, duration=1.0, easing=Easing.LINEAR)

        self.assertEqual(source.transform, source_before)
        self.assertEqual(target.transform, target_before)
        self.assertEqual(len(scene.evaluate(0.49).objects), 1)
        middle = scene.evaluate(1.0)
        self.assertEqual(middle.objects, ())
        self.assertEqual(len(middle.transients), 1)
        self.assertAlmostEqual(middle.transients[0].alpha, 0.5)
        end = scene.evaluate(1.5)
        self.assertEqual(len(end.objects), 1)
        self.assertEqual(end.objects[0].snapshot.transform, target_before)
        self.assertEqual(end.transients, ())
        self.assertIs(target_handle.raw, target)
        clip = scene._timeline.clips[-1]
        self.assertEqual(clip.span.start, 0.5)
        self.assertEqual(clip.span.end, 1.5)

    def test_replace_requires_unadded_target(self):
        a = Square(1)
        b = Circle(1)
        scene = Scene()
        scene.add(a, b)
        with self.assertRaisesRegex(ValueError, "must not already"):
            scene.replace(a, b)

    def test_replace_can_run_in_parallel_with_independent_handoff_durations(self):
        a0 = Square(1, transform=Transform2D.translation(-3, 1))
        a1 = Square(1, transform=Transform2D.translation(-3, -1))
        b0 = Circle(1, transform=Transform2D.translation(3, 1))
        b1 = Circle(1, transform=Transform2D.translation(3, -1))
        scene = Scene()
        scene.add(a0, a1)
        scene.wait(0.5)

        with scene.parallel():
            h0 = scene.replace(a0, b0, duration=1.0, easing=Easing.LINEAR)
            h1 = scene.replace(a1, b1, duration=2.0, easing=Easing.LINEAR)

        self.assertIs(h0.raw, b0)
        self.assertIs(h1.raw, b1)
        self.assertAlmostEqual(scene._timeline.cursor, 2.5)

        before = scene.evaluate(0.49)
        self.assertEqual(len(before.objects), 2)
        self.assertEqual(before.transients, ())

        middle = scene.evaluate(1.0)
        self.assertEqual(middle.objects, ())
        self.assertEqual(len(middle.transients), 2)
        self.assertAlmostEqual(middle.transients[0].alpha, 0.5)
        self.assertAlmostEqual(middle.transients[1].alpha, 0.25)

        first_done = scene.evaluate(1.5)
        self.assertEqual(len(first_done.objects), 1)
        self.assertEqual(first_done.objects[0].snapshot.transform, b0.transform)
        self.assertEqual(len(first_done.transients), 1)
        self.assertAlmostEqual(first_done.transients[0].alpha, 0.5)

        end = scene.evaluate(2.5)
        self.assertEqual(len(end.objects), 2)
        self.assertEqual(end.transients, ())
