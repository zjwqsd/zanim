import unittest

from zanim import Canvas, Color, Scene, Style
from zanim.plot import Axes, DynamicGeometryObject2D


class AxesTests(unittest.TestCase):
    def test_coordinate_round_trip(self):
        axes = Axes((-4, 4), (-2, 4), width=8, height=6)
        p = axes.c2p(1.25, -0.5)
        c = axes.p2c(p)
        self.assertAlmostEqual(c.x, 1.25)
        self.assertAlmostEqual(c.y, -0.5)

    def test_area_tracks_bounds(self):
        axes = Axes((-4, 4), (-1, 4), width=8, height=5)

        def f(x):
            return 1.0 + 0.2 * x * x

        poly = axes.area_polygon(f, -1.0, 2.0, samples=10)
        self.assertEqual(len(poly.points), 12)
        self.assertEqual(axes.p2c(poly.points[0]).x, -1.0)
        self.assertEqual(axes.p2c(poly.points[-1]).x, 2.0)

    def test_integral_value_uses_trapezoid_sampling(self):
        axes = Axes((-4, 4), (-2, 4), width=8, height=6)

        # Trapezoidal integration is exact for a linear function.
        def f(x):
            return 2.0 * x + 1.0

        self.assertAlmostEqual(axes.integral_value(f, 0.0, 3.0, samples=8), 12.0)
        self.assertAlmostEqual(axes.integral_value(f, 3.0, 0.0, samples=8), -12.0)
        self.assertEqual(axes.integral_value(f, 1.0, 1.0, samples=8), 0.0)

    def test_dynamic_geometry_is_random_access(self):
        axes = Axes((-3, 3), (-1, 3), width=6, height=4)
        obj = DynamicGeometryObject2D(
            lambda t: axes.area_polygon(lambda x: 1 + x * x * 0.1, -2 + t, 1 + t * 0.1),
            style=Style(fill=Color(100, 150, 255, 120), stroke=None),
        )
        scene = Scene(canvas=Canvas(width=640, height=360, unit_size=70))
        scene.add(obj)
        a = scene.evaluate(0.5).objects[0].snapshot.geometry
        scene.evaluate(1.0)
        b = scene.evaluate(0.5).objects[0].snapshot.geometry
        self.assertEqual(a, b)

    def test_axis_labels_are_regular_group_objects(self):
        axes = Axes((-2, 2), (-1, 2), width=4, height=3)
        labels = axes.axis_labels("x", "y", font_size=12)
        self.assertEqual(len(labels.children), 2)
        self.assertGreater(labels.bounds().width, 0)


if __name__ == "__main__":
    unittest.main()


class DynamicGeometryCoverageTests(unittest.TestCase):
    def test_dynamic_geometry_accepts_all_core_geometry_types(self):
        from zanim.geometry import CircleGeometry, RectangleGeometry
        from zanim.plot import DynamicGeometryObject2D

        c = DynamicGeometryObject2D(lambda t: CircleGeometry(1 + t))
        r = DynamicGeometryObject2D(lambda t: RectangleGeometry(1 + t, 2))
        self.assertIsInstance(c.geometry_at(0.5), CircleGeometry)
        self.assertIsInstance(r.geometry_at(0.5), RectangleGeometry)
