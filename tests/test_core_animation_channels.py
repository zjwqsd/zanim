import unittest

from zanim import Color, Object2D, Scene, Square, StrokeStyle, Style
from zanim.value import ScalarValue


class CoreAnimationChannelTests(unittest.TestCase):
    def test_opacity_is_universal_and_seekable(self):
        obj = Object2D(Square(1), opacity=0.8)
        scene = Scene()
        scene.add(obj)
        scene.wait(0.5)
        scene.fade_out(obj, duration=1.0)
        self.assertAlmostEqual(scene.evaluate(0.25).objects[0].snapshot.opacity, 0.8)
        self.assertAlmostEqual(scene.evaluate(1.0).objects[0].snapshot.opacity, 0.4)
        self.assertAlmostEqual(scene.evaluate(1.6).objects[0].snapshot.opacity, 0.0)
        self.assertAlmostEqual(scene.evaluate(0.25).objects[0].snapshot.opacity, 0.8)

    def test_style_clip(self):
        before = Style(fill=Color(0, 0, 255), stroke=None)
        after = Style(fill=Color(255, 0, 0), stroke=StrokeStyle(Color(255,255,255), .1))
        obj = Object2D(Square(1), style=before)
        scene = Scene()
        scene.add(obj)
        scene.style(obj, to=after, duration=2)
        mid = scene.evaluate(1).objects[0].snapshot.style
        self.assertGreater(mid.fill.r, 0)
        self.assertGreater(mid.fill.b, 0)
        self.assertIsNotNone(mid.stroke)

    def test_create_trims_geometry(self):
        obj = Object2D(Square(2), style=Style(fill=Color(100,100,255), stroke=StrokeStyle()), trim=0)
        scene = Scene()
        scene.add(obj)
        scene.create(obj, duration=2)
        start = scene.evaluate(0).objects[0].snapshot
        mid = scene.evaluate(1).objects[0].snapshot
        end = scene.evaluate(2).objects[0].snapshot
        self.assertEqual(type(start.geometry).__name__, 'Line')
        self.assertEqual(type(mid.geometry).__name__, 'Polyline')
        self.assertEqual(type(end.geometry).__name__, 'Square')
        self.assertIsNone(mid.style.fill)
        self.assertIsNotNone(end.style.fill)

    def test_scalar_value_random_access(self):
        value = ScalarValue(2)
        scene = Scene()
        scene.add(value)
        scene.value(value, to=10, duration=2)
        self.assertAlmostEqual(value.value_at(1), 6)
        self.assertAlmostEqual(value.value_at(2.5), 10)
        self.assertAlmostEqual(value.value_at(1), 6)

    def test_fade_in_requires_explicit_transparent_state(self):
        opaque = Object2D(Square(1))
        scene = Scene()
        scene.add(opaque)
        scene.wait(1)
        with self.assertRaisesRegex(ValueError, "current opacity to be 0"):
            scene.fade_in(opaque)

        hidden = Object2D(Square(1), opacity=0)
        scene2 = Scene()
        scene2.add(hidden)
        scene2.wait(1)
        scene2.fade_in(hidden, duration=1)
        self.assertEqual(scene2.evaluate(.5).objects[0].snapshot.opacity, 0)
        self.assertAlmostEqual(scene2.evaluate(1.5).objects[0].snapshot.opacity, .5)

    def test_fade_out_then_fade_in_restores_visibility(self):
        obj = Object2D(Square(1))
        scene = Scene()
        scene.add(obj)
        scene.fade_out(obj, duration=1)
        scene.fade_in(obj, duration=1)
        self.assertAlmostEqual(scene.evaluate(.5).objects[0].snapshot.opacity, .5)
        self.assertAlmostEqual(scene.evaluate(1.5).objects[0].snapshot.opacity, .5)
        self.assertAlmostEqual(scene.evaluate(2.1).objects[0].snapshot.opacity, 1.0)


if __name__ == '__main__': unittest.main()
