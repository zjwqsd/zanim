import unittest

from zanim import Canvas, JuliaSet, MandelbrotSet, Scene
from zanim.render.frame import pick_snapshot_object, render_snapshot_rgba


class FractalFieldTests(unittest.TestCase):
    def test_mandelbrot_is_native_unbounded_field(self):
        scene = Scene(canvas=Canvas(160, 90, 40))
        scene.add(MandelbrotSet(max_iter=80))
        snapshot = scene.evaluate(0.0)
        self.assertEqual(len(snapshot.batches), 0)
        self.assertEqual(len(snapshot.rasters), 0)
        self.assertEqual(len(snapshot.infinite2d), 1)
        native = snapshot.infinite2d[0].snapshot
        self.assertEqual(native.kind, 3)
        self.assertEqual(native.map_kind, 1)
        self.assertEqual(native.p0, 80.0)

    def test_julia_parameter_reaches_native_snapshot(self):
        scene = Scene(canvas=Canvas(160, 90, 40))
        scene.add(JuliaSet(-0.8 + 0.156j, max_iter=90))
        native = scene.evaluate(0.0).infinite2d[0].snapshot
        self.assertEqual(native.kind, 3)
        self.assertEqual(native.map_kind, 2)
        self.assertAlmostEqual(native.p2, -0.8)
        self.assertAlmostEqual(native.p3, 0.156)

    def test_fractal_has_no_finite_bounds(self):
        with self.assertRaises(TypeError):
            MandelbrotSet().bounds()
        with self.assertRaises(TypeError):
            JuliaSet(0j).bounds()

    def test_native_rgba_and_picking_cover_viewport(self):
        scene = Scene(canvas=Canvas(96, 64, 32))
        fractal = MandelbrotSet(max_iter=40)
        scene.add(fractal)
        snapshot = scene.evaluate(0.0)
        buffer = bytearray(96 * 64 * 4)
        render_snapshot_rgba(buffer, snapshot, scene.canvas)
        self.assertTrue(any(buffer))
        self.assertEqual(pick_snapshot_object(snapshot, scene.canvas, 48, 32), 1)

    def test_validation(self):
        with self.assertRaises(ValueError):
            MandelbrotSet(max_iter=0)
        with self.assertRaises(ValueError):
            JuliaSet(0j, escape_radius=1.5)
        with self.assertRaises(ValueError):
            MandelbrotSet(color_scale=0)


if __name__ == "__main__":
    unittest.main()
