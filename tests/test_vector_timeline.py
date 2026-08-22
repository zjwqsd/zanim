import unittest

from zanim import Easing, Scene
from zanim.vector import VectorDocument, VectorObject2D


class VectorTimelineTests(unittest.TestCase):
    def test_reveal_requires_explicit_zero_state(self):
        obj = VectorObject2D(VectorDocument((), 2, 1, group_count=0))
        scene = Scene()
        scene.add(obj)
        with self.assertRaisesRegex(ValueError, "current reveal to be 0"):
            scene.reveal(obj)

    def test_reveal_is_hidden_before_clip_and_random_access(self):
        obj = VectorObject2D(VectorDocument((), 2, 1, group_count=0), reveal=0)
        scene = Scene()
        scene.add(obj)
        scene.wait(1.0)
        clip = scene.reveal(obj, duration=2.0, easing=Easing.LINEAR)
        self.assertEqual(scene.evaluate(0.5).vectors[0].snapshot.reveal, 0.0)
        self.assertAlmostEqual(scene.evaluate(2.0).vectors[0].snapshot.reveal, 0.5)
        self.assertEqual(scene.evaluate(3.5).vectors[0].snapshot.reveal, 1.0)
        self.assertEqual(scene.evaluate(0.5).vectors[0].snapshot.reveal, 0.0)
        self.assertEqual(obj.reveal, 1.0)
        self.assertEqual(clip.span.start, 1.0)


if __name__ == "__main__":
    unittest.main()
