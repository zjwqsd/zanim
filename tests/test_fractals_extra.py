import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "extras" / "fractals.py"
SPEC = importlib.util.spec_from_file_location("zanim_fractals_extra", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FractalsExtraTests(unittest.TestCase):
    def test_koch_segment_count(self):
        for order in range(5):
            points = MODULE.koch_snowflake_points(order)
            self.assertEqual(len(points) - 1, 3 * 4**order)
            self.assertAlmostEqual(points[0].x, points[-1].x)
            self.assertAlmostEqual(points[0].y, points[-1].y)

    def test_sierpinski_arrowhead_segment_count(self):
        for order in range(6):
            points = MODULE.sierpinski_arrowhead_points(order)
            self.assertEqual(len(points) - 1, 3**order)

    def test_dragon_and_levy_double_every_order(self):
        for order in range(8):
            self.assertEqual(len(MODULE.dragon_curve_points(order)) - 1, 2**order)
            self.assertEqual(len(MODULE.levy_c_points(order)) - 1, 2**order)

    def test_sierpinski_and_dragon_keep_canonical_orientation(self):
        for generator, orders in (
            (MODULE.sierpinski_arrowhead_points, range(1, 7)),
            (MODULE.dragon_curve_points, range(1, 10)),
        ):
            for order in orders:
                points = generator(order, side=2.0)
                self.assertAlmostEqual(points[0].y, points[-1].y, places=12)
                self.assertGreater(points[-1].x, points[0].x)

        # The Sierpiński traversal chord stays on the lower edge rather than
        # alternating between a horizontal and a -60° global pose.
        for order in range(1, 7):
            points = MODULE.sierpinski_arrowhead_points(order, side=2.0)
            self.assertGreater(max(point.y for point in points), points[0].y)

    def test_every_generator_fits_requested_side(self):
        for generator in (
            MODULE.koch_snowflake_points,
            MODULE.sierpinski_arrowhead_points,
            MODULE.dragon_curve_points,
            MODULE.levy_c_points,
        ):
            points = generator(3, side=5.0)
            width = max(p.x for p in points) - min(p.x for p in points)
            height = max(p.y for p in points) - min(p.y for p in points)
            self.assertAlmostEqual(max(width, height), 5.0, places=12)

    def test_single_section_scene_builds_and_evaluates(self):
        scene = MODULE._build_scene(section="koch")
        self.assertGreater(scene.duration, 0)
        scene.evaluate(0.0)
        scene.evaluate(scene.duration / 2)
        scene.evaluate(scene.duration)


if __name__ == "__main__":
    unittest.main()
