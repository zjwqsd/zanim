import unittest

from zanim import Camera2D, Easing, Scene, Square, Transform2D, Vec2


class DynamicCameraTests(unittest.TestCase):
    def test_provider_drives_absolute_time_view(self):
        camera = Camera2D(
            transform_provider=lambda t: Transform2D.scaling(2.0) @ Transform2D.translation(-t, 0)
        )
        obj = Square(1)
        scene = Scene(camera=camera)
        scene.add(obj)

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
            scene.transform(camera, to=Transform2D.translation(1, 0))

    def test_provider_must_return_transform(self):
        scene = Scene(camera=Camera2D(transform_provider=lambda _t: None))
        scene.add(Square(1))
        with self.assertRaises(TypeError):
            scene.evaluate(0.0)


if __name__ == "__main__":
    unittest.main()


class BoundCameraSugarTests(unittest.TestCase):
    def test_scene_camera_affine_is_complete_world_to_view_target(self):
        scene = Scene()
        obj = Square(1)
        scene.add(obj)
        scene.camera.affine(position=(-0.3, -0.08), scale=1.15, duration=1.3)
        expected = Transform2D.translation(-0.3, -0.08) @ Transform2D.scaling(1.15)
        self.assertEqual(scene.camera.transform, expected)
        self.assertEqual(scene.evaluate(1.3).objects[0].snapshot.transform, expected)

    def test_camera_pose_uses_rigid_interpolation(self):
        import math

        scene = Scene()
        scene.add(Square(1))
        scene.camera.pose(position=(2, 1), rotation=math.pi / 2, duration=2)
        mid = scene.evaluate(1).objects[0].snapshot.transform
        x_axis = mid.apply(Vec2(1, 0)) - mid.apply(Vec2())
        self.assertAlmostEqual(x_axis.x * x_axis.x + x_axis.y * x_axis.y, 1.0)

    def test_camera_pan_is_world_camera_motion(self):
        scene = Scene()
        scene.camera.affine(position=(0, 0), scale=2, duration=0)
        scene.camera.pan(by=(1, 0), duration=1, easing=Easing.LINEAR)
        # V' = V @ T(-d), so one world unit becomes two view units at zoom 2.
        self.assertAlmostEqual(scene.camera.transform.tx, -2.0)
        self.assertAlmostEqual(scene.camera.transform.xx, 2.0)

    def test_camera_rotate_view_preserves_radius_mid_clip(self):
        import math

        scene = Scene()
        scene.add(Square(1))
        scene.camera.rotate_view(by=math.pi, duration=2, easing=Easing.LINEAR)
        mid = scene.evaluate(1).objects[0].snapshot.transform
        p = mid.apply(Vec2(1, 0))
        self.assertAlmostEqual(p.x * p.x + p.y * p.y, 1.0)

    def test_dynamic_camera_rejects_bound_sugar(self):
        scene = Scene(camera=Camera2D(transform_provider=lambda _t: Transform2D()))
        with self.assertRaises(TypeError):
            scene.camera.affine(position=(1, 0))
