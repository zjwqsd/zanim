import unittest
from zanim import BatchObject2D, CircleSet, Color, DynamicBatchObject2D, RectSet, Scene, Vec2


class BatchTimelineTests(unittest.TestCase):
    def test_batch_clip_advances_authoring_state_but_keeps_history(self):
        before = RectSet((Vec2(0, 0),), (Vec2(1, 1),), (Color(10, 10, 10),))
        after = RectSet((Vec2(2, 0),), (Vec2(1, 1),), (Color(240, 240, 240),))
        obj = BatchObject2D(before)
        scene = Scene()
        scene.add(obj)
        scene.batch(obj, to=after, duration=2.0)
        self.assertIs(obj.batch, after)
        start = scene.evaluate(0.0).batches[0]
        mid = scene.evaluate(1.0).batches[0]
        end = scene.evaluate(2.0).batches[0]
        self.assertIs(start.snapshot.batch, before)
        self.assertIs(mid.target.batch, after)
        self.assertAlmostEqual(mid.alpha, 0.5)
        self.assertIs(end.snapshot.batch, after)
        self.assertIsNone(end.target)

    def test_batch_clip_requires_compatible_batch_shape(self):
        obj = BatchObject2D(RectSet((Vec2(),), (Vec2(1,1),), (Color(0,0,0),)))
        target = CircleSet((Vec2(),), (1.0,), (Color(0,0,0),))
        scene = Scene()
        scene.add(obj)
        with self.assertRaises(ValueError):
            scene.batch(obj, to=target)

    def test_dynamic_batch_is_absolute_time_and_random_access(self):
        def provider(time):
            return RectSet(
                (Vec2(float(time), 0),),
                (Vec2(1, 1),),
                (Color(round(10 + 20 * float(time)), 20, 30),),
            )

        obj = DynamicBatchObject2D(provider)
        scene = Scene()
        scene.add(obj)
        a = scene.evaluate(2.0).batches[0].snapshot.batch
        _ = scene.evaluate(0.25)
        b = scene.evaluate(2.0).batches[0].snapshot.batch
        self.assertEqual(a, b)
        self.assertEqual(a.centers[0], Vec2(2.0, 0))

    def test_dynamic_batch_rejects_batch_clips(self):
        initial = RectSet((Vec2(),), (Vec2(1, 1),), (Color(0, 0, 0),))
        obj = DynamicBatchObject2D(lambda _t: initial)
        scene = Scene()
        scene.add(obj)
        with self.assertRaises(TypeError):
            scene.batch(obj, to=initial)


if __name__ == '__main__': unittest.main()
