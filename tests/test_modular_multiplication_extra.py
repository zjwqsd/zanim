import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "extras" / "modular_multiplication.py"
SPEC = importlib.util.spec_from_file_location("zanim_modular_multiplication_extra", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ModularMultiplicationExtraTests(unittest.TestCase):
    def test_points_stay_on_circle(self):
        radius = 2.75
        for index in (-3.5, 0, 1.25, 17, 53.75):
            point = MODULE.point_on_circle(index, 32, radius=radius)
            self.assertAlmostEqual(math.hypot(point.x, point.y), radius, places=12)

    def test_integer_multiplier_matches_modular_index(self):
        count = 17
        multiplier = 5
        state = MODULE.modular_lines(count, multiplier)
        for i, end in enumerate(state.ends):
            expected = MODULE.point_on_circle((multiplier * i) % count, count)
            self.assertAlmostEqual(end.x, expected.x, places=12)
            self.assertAlmostEqual(end.y, expected.y, places=12)

    def test_fractional_multiplier_is_continuous_across_wrap(self):
        count = 64
        i = 51
        a = MODULE.modular_lines(count, 1.9999).ends[i]
        b = MODULE.modular_lines(count, 2.0001).ends[i]
        self.assertLess(math.hypot(a.x - b.x, a.y - b.y), 0.01)

    def test_batch_sizes_match_point_count(self):
        for count in (16, 64, 240):
            self.assertEqual(len(MODULE.modular_lines(count, 2.0)), count)
            self.assertEqual(len(MODULE.circle_dots(count)), count)

    def test_scene_builds_and_evaluates_random_access(self):
        scene = MODULE._build_scene(points=48, start=1.0, end=3.0, duration=0.6)
        self.assertGreater(scene.duration, 0)
        for time in (0.0, scene.duration * 0.25, scene.duration * 0.75, scene.duration):
            scene.evaluate(time)


if __name__ == "__main__":
    unittest.main()
