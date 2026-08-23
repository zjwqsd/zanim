import importlib.util
import unittest
from pathlib import Path

from zanim import Vec2

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "extras" / "hilbert_curve.py"
SPEC = importlib.util.spec_from_file_location("zanim_hilbert_extra", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HilbertExtraTests(unittest.TestCase):
    def test_orders_have_expected_vertex_count_and_axis_steps(self):
        for order in range(1, 6):
            points = MODULE.hilbert_points(order, side=2.0)
            self.assertEqual(len(points), 4**order)
            step = 2.0 / ((1 << order) - 1)
            for a, b in zip(points, points[1:]):
                dx = abs(b.x - a.x)
                dy = abs(b.y - a.y)
                self.assertAlmostEqual(dx + dy, step, places=12)
                self.assertTrue(dx < 1e-12 or dy < 1e-12)

    def test_first_order_is_one_continuous_u_shape(self):
        self.assertEqual(
            MODULE.hilbert_points(1, side=2.0),
            (
                Vec2(-1.0, -1.0),
                Vec2(-1.0, 1.0),
                Vec2(1.0, 1.0),
                Vec2(1.0, -1.0),
            ),
        )

    def test_default_scene_reaches_requested_order(self):
        scene = MODULE._build_scene(max_order=4, transition_duration=0.05, hold=0.0)
        self.assertGreater(scene.duration, 0)
        final = scene.evaluate(scene.duration)
        curves = [obj for obj in final.objects if hasattr(obj.snapshot.geometry, "points")]
        self.assertTrue(any(len(obj.snapshot.geometry.points) == 4**4 for obj in curves))


if __name__ == "__main__":
    unittest.main()
