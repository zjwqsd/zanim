import unittest
from zanim import BatchObject2D, CircleSet, Color, RectSet, Scene, Vec2


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


if __name__ == '__main__': unittest.main()
