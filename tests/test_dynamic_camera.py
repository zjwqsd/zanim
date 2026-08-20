import unittest

from zanim import Camera2D, Object2D, Scene, Square, Transform2D


class DynamicCameraTests(unittest.TestCase):
    def test_provider_drives_absolute_time_view(self):
        camera = Camera2D(
            transform_provider=lambda t: Transform2D.scaling(2.0) @ Transform2D.translation(-t, 0)
        )
        obj = Object2D(Square(1))
        scene = Scene(camera=camera).add(obj)

        a = scene.evaluate(0.25).objects[0].snapshot.transform
        b = scene.evaluate(0.75).objects[0].snapshot.transform
        again = scene.evaluate(0.25).objects[0].snapshot.transform
        self.assertEqual(a, again)
        self.assertNotEqual(a, b)
        self.assertAlmostEqual(a.tx, -0.5)
        self.assertAlmostEqual(b.tx, -1.5)

    def test_dynamic_camera_rejects_transform_clip(self):
        camera = Camera2D(transform_provider=lambda _t: Transform2D())
        scene = Scene(camera=camera)
        with self.assertRaises(TypeError):
            scene.play_transform(camera, Transform2D.translation(1, 0))

    def test_provider_must_return_transform(self):
        scene = Scene(camera=Camera2D(transform_provider=lambda _t: None))
        scene.add(Object2D(Square(1)))
        with self.assertRaises(TypeError):
            scene.evaluate(0.0)


if __name__ == '__main__':
    unittest.main()
