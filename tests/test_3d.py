import math
import unittest

from zanim import (
    SO3,
    Box3D,
    Camera3D,
    Canvas,
    Color,
    Cube3D,
    Easing,
    Scene,
    Surface3D,
    Transform3D,
    Vec3,
)


class Space3DTests(unittest.TestCase):
    def test_transform_composition(self):
        transform = Transform3D.translation(1, 2, 3) @ Transform3D.rotation_z(math.pi / 2)
        got = transform.apply(Vec3(1, 0, 0))
        self.assertAlmostEqual(got.x, 1.0, places=7)
        self.assertAlmostEqual(got.y, 3.0, places=7)
        self.assertAlmostEqual(got.z, 3.0, places=7)

    def test_axis_rotation_preserves_length(self):
        rotation = Transform3D.rotation_axis(Vec3(1, 2, 3), 0.73)
        before = Vec3(2, -1, 0.5)
        after = rotation.apply(before)
        self.assertAlmostEqual(before.length, after.length, places=7)

    def test_so3_slerp_stays_on_rotation_group(self):
        a = SO3.rotation_axis(Vec3(1, 2, -1), 0.4)
        b = SO3.rotation_axis(Vec3(-2, 1, 3), 2.1)
        for alpha in (0.0, 0.1, 0.5, 0.9, 1.0):
            r = a.slerp(b, alpha)
            self.assertAlmostEqual(r.determinant, 1.0, places=7)
            v = r.apply(Vec3(0.3, -0.7, 1.2))
            self.assertAlmostEqual(v.length, Vec3(0.3, -0.7, 1.2).length, places=7)

    def test_so3_quaternion_roundtrip(self):
        rotation = SO3.rotation_z(0.8) @ SO3.rotation_x(-0.35)
        restored = SO3.from_quaternion(*rotation.as_quaternion())
        for got, expected in zip(restored.as_rows(), rotation.as_rows()):
            for x, y in zip(got, expected):
                self.assertAlmostEqual(x, y, places=7)


class Mesh3DTests(unittest.TestCase):
    def test_box_dimensions_and_mesh_reuse(self):
        a = Box3D(Vec3(1.0, 2.0, 3.0))
        b = Box3D(Vec3(4.0, 5.0, 6.0))
        # All boxes share one canonical immutable mesh; dimensions live in
        # Transform3D so the renderer can instance differently sized boxes.
        self.assertIs(a.mesh, b.mesh)
        model = a.transform @ a.geometry_transform
        world = [model.apply(v) for v in a.mesh.vertices]
        xs = [v.x for v in world]
        ys = [v.y for v in world]
        zs = [v.z for v in world]
        self.assertAlmostEqual(max(xs) - min(xs), 1.0)
        self.assertAlmostEqual(max(ys) - min(ys), 2.0)
        self.assertAlmostEqual(max(zs) - min(zs), 3.0)

    def test_cube_is_indexed_flat_shaded_mesh(self):
        cube = Cube3D(2.0)
        self.assertEqual(len(cube.mesh.vertices), 24)
        self.assertEqual(len(cube.mesh.normals), 24)
        self.assertEqual(len(cube.mesh.indices), 36)

    def test_height_surface_topology_and_normals(self):
        surface = Surface3D(lambda x, y: x * x - y * y, resolution=(7, 5))
        self.assertEqual(len(surface.mesh.vertices), 35)
        self.assertEqual(len(surface.mesh.indices), 6 * 6 * 4)
        self.assertTrue(all(abs(n.length - 1.0) < 1e-6 for n in surface.mesh.normals))

    def test_scene_evaluates_3d_transform_random_access(self):
        scene = Scene(canvas=Canvas(320, 180, 25), fps=30)
        cube = Cube3D(color=Color(80, 160, 255))
        scene.add(cube)
        scene.transform_function(
            cube,
            lambda a: Transform3D.rotation_y(math.pi * a),
            duration=2.0,
            easing=Easing.LINEAR,
        )
        first = scene.evaluate(0.5).meshes3d[0].snapshot.transform
        later = scene.evaluate(1.5).meshes3d[0].snapshot.transform
        again = scene.evaluate(0.5).meshes3d[0].snapshot.transform
        self.assertEqual(first, again)
        self.assertNotEqual(first, later)
        self.assertTrue(scene.has_3d)
        self.assertIsInstance(scene.camera3d, Camera3D)

    def test_3d_and_2d_transform_channels_are_distinct_by_object(self):
        scene = Scene()
        cube = Cube3D()
        scene.add(cube)
        scene.transform(cube, to=Transform3D.translation(1, 0, 0), duration=1.0)
        got = scene.evaluate(0.5).meshes3d[0].snapshot.transform.apply(Vec3())
        self.assertGreater(got.x, 0.0)
        self.assertLess(got.x, 1.0)


if __name__ == "__main__":
    unittest.main()
