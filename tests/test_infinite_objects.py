import math
import unittest

from zanim import Canvas, Color, InfiniteGrid, InfiniteLine, Scene, Transform2D
from zanim.render.wire import encode_snapshot


class InfiniteObjectTests(unittest.TestCase):
    def test_line_stays_native_and_unbounded(self):
        line = InfiniteLine((0, 0), (1, 0.25))
        scene = Scene(canvas=Canvas(1280, 960, 100))
        scene.add(line)
        snapshot = scene.evaluate(0.0)
        self.assertEqual(len(snapshot.infinite2d), 1)
        self.assertEqual(len(snapshot.batches), 0)
        encoded = encode_snapshot(snapshot)
        self.assertEqual(len(encoded.infinite2d), 1)
        self.assertEqual(len(encoded.batches), 0)
        with self.assertRaises(TypeError):
            line.bounds()

    def test_grid_stays_one_native_object_at_extreme_zoom(self):
        scene = Scene(canvas=Canvas(1280, 960, 100))
        scene.add(InfiniteGrid(0.5))
        scene.camera.affine(position=(0, 0), scale=0.0001, duration=1.0)
        snapshot = scene.evaluate(1.0)
        self.assertEqual(len(snapshot.infinite2d), 1)
        self.assertEqual(len(snapshot.batches), 0)
        encoded = encode_snapshot(snapshot)
        self.assertEqual(len(encoded.infinite2d), 1)

    def test_camera_and_object_transform_are_composed_without_tessellation(self):
        scene = Scene(canvas=Canvas(1280, 960, 100))
        line = InfiniteLine(transform=Transform2D.rotation(math.pi / 4))
        scene.add(line)
        scene.camera.affine(position=(0.5, -0.2), scale=2.0, duration=1.0)
        rendered = scene.evaluate(1.0).infinite2d[0].snapshot
        expected = scene.camera.transform @ line.transform
        self.assertAlmostEqual(rendered.transform.xx, expected.xx)
        self.assertAlmostEqual(rendered.transform.xy, expected.xy)
        self.assertAlmostEqual(rendered.transform.tx, expected.tx)

    def test_native_line_reaches_canvas_edges(self):
        scene = Scene(canvas=Canvas(320, 200, 50))
        scene.add(InfiniteLine((0, 0), (1, 0), color=Color(255, 255, 255), stroke_width=0.04))
        buffer = bytearray(320 * 200 * 4)
        from zanim.render.frame import render_snapshot_rgba

        render_snapshot_rgba(buffer, scene.evaluate(0.0), scene.canvas)
        # RGBA bytes: sample a small neighborhood at both horizontal edges.
        def edge_has_alpha(x):
            for y in range(97, 104):
                if buffer[(y * 320 + x) * 4 + 3] != 0:
                    return True
            return False

        self.assertTrue(edge_has_alpha(0))
        self.assertTrue(edge_has_alpha(319))


if __name__ == "__main__":
    unittest.main()

class ComplexMappedGridTests(unittest.TestCase):
    def test_native_square_grid_stays_out_of_python_batches(self):
        from zanim import ComplexMappedGrid
        scene = Scene(canvas=Canvas(640, 480, 80))
        scene.add(ComplexMappedGrid("square", step=0.5))
        snapshot = scene.evaluate(0.0)
        self.assertEqual(len(snapshot.batches), 0)
        self.assertEqual(len(snapshot.infinite2d), 1)
        self.assertEqual(snapshot.infinite2d[0].snapshot.kind, 2)
        self.assertEqual(snapshot.infinite2d[0].snapshot.map_kind, 1)

    def test_scalar_progress_reaches_zig_snapshot(self):
        from zanim import ComplexMappedGrid
        from zanim.value import ScalarValue
        scene = Scene(canvas=Canvas(640, 480, 80))
        progress = ScalarValue(0.0)
        progress, grid = scene.add(progress, ComplexMappedGrid("reciprocal", progress=progress))
        progress.value(to=1.0, duration=1.0)
        self.assertAlmostEqual(scene.evaluate(0.0).infinite2d[0].snapshot.progress, 0.0)
        self.assertAlmostEqual(scene.evaluate(1.0).infinite2d[0].snapshot.progress, 1.0)

    def test_exp_requires_periodic_imaginary_spacing(self):
        from zanim import ComplexMappedGrid
        with self.assertRaises(ValueError):
            ComplexMappedGrid("exp", step=0.5)
        grid = ComplexMappedGrid("exp", step=(0.5, 2.0 * math.pi / 12.0))
        self.assertIsNotNone(grid)

    def test_exp_and_mobius_accept_scalar_progress(self):
        from zanim import ComplexMappedGrid
        from zanim.value import ScalarValue
        p1 = ScalarValue(0.0)
        exp = ComplexMappedGrid("exp", step=(0.5, 2.0 * math.pi / 12.0), progress=p1)
        self.assertIs(exp.progress, p1)
        p2 = ScalarValue(0.0)
        mobius = ComplexMappedGrid(
            "mobius", progress=p2,
            mobius=(1.1 + 0.1j, 0.4 - 0.2j, 0.15 + 0.05j, 1.0 + 0j),
        )
        self.assertIs(mobius.progress, p2)
