import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "extras" / "de_casteljau.py"
SPEC = importlib.util.spec_from_file_location("zanim_de_casteljau_extra", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DeCasteljauExtraTests(unittest.TestCase):
    def test_endpoints_match_first_and_last_control_points(self):
        controls = MODULE.CONTROL_POINTS
        self.assertEqual(MODULE.cubic_bezier_point(controls, 0.0), controls[0])
        self.assertEqual(MODULE.cubic_bezier_point(controls, 1.0), controls[-1])

    def test_de_casteljau_matches_bernstein_form(self):
        controls = MODULE.CONTROL_POINTS
        for step in range(21):
            t = step / 20
            _, first, second, final_level, final = MODULE.de_casteljau_levels(controls, t)
            bernstein = MODULE.cubic_bezier_point(controls, t)
            self.assertEqual(len(first), 3)
            self.assertEqual(len(second), 2)
            self.assertEqual(len(final_level), 1)
            self.assertAlmostEqual(final.x, bernstein.x, places=12)
            self.assertAlmostEqual(final.y, bernstein.y, places=12)
            self.assertEqual(final_level[0], final)

    def test_each_level_is_linear_interpolation_of_previous_level(self):
        controls = MODULE.CONTROL_POINTS
        t = 0.37
        _, first, second, final_level, _ = MODULE.de_casteljau_levels(controls, t)
        expected_first = tuple(MODULE.lerp_point(a, b, t) for a, b in zip(controls, controls[1:]))
        expected_second = tuple(MODULE.lerp_point(a, b, t) for a, b in zip(first, first[1:]))
        self.assertEqual(first, expected_first)
        self.assertEqual(second, expected_second)
        self.assertEqual(final_level[0], MODULE.lerp_point(second[0], second[1], t))

    def test_trace_has_constant_segment_count_and_reaches_current_point(self):
        controls = MODULE.CONTROL_POINTS
        for t in (0.0, 0.25, 0.5, 1.0):
            trace = MODULE.curve_trace(controls, t, segments=40)
            self.assertEqual(len(trace.starts), 40)
            self.assertEqual(len(trace.ends), 40)
            current = MODULE.cubic_bezier_point(controls, t)
            self.assertAlmostEqual(trace.ends[-1].x, current.x, places=12)
            self.assertAlmostEqual(trace.ends[-1].y, current.y, places=12)

    def test_scene_builds_and_evaluates_random_access(self):
        scene = MODULE._build_scene(duration=0.25)
        self.assertGreater(scene.duration, 0)
        for t in (0.0, scene.duration * 0.2, scene.duration * 0.7, scene.duration):
            scene.evaluate(t)


if __name__ == "__main__":
    unittest.main()
