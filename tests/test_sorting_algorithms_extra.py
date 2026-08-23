import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "extras" / "sorting_algorithms.py"
SPEC = importlib.util.spec_from_file_location("zanim_sorting_algorithms_extra", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SortingAlgorithmsExtraTests(unittest.TestCase):
    def test_random_permutation_is_reproducible_and_contains_1_through_n(self):
        a = MODULE.random_permutation(14, 23)
        b = MODULE.random_permutation(14, 23)
        self.assertEqual(a, b)
        self.assertEqual(tuple(sorted(a)), tuple(range(1, 15)))
        self.assertNotEqual(a, tuple(range(1, 15)))

    def test_every_algorithm_finishes_sorted_and_preserves_identity(self):
        initial = MODULE.random_permutation(12, 17)
        expected = tuple(range(1, 13))
        for _, factory in MODULE.ALGORITHMS:
            trace = factory(initial)
            self.assertTrue(trace.steps)
            self.assertEqual(trace.steps[-1].values, expected, trace.name)
            for step in trace.steps:
                self.assertEqual(tuple(sorted(step.values)), expected, (trace.name, step.kind))

    def test_traces_expose_comparisons_and_moves(self):
        initial = MODULE.random_permutation(12, 19)
        for _, factory in MODULE.ALGORITHMS:
            trace = factory(initial)
            kinds = {step.kind for step in trace.steps}
            self.assertIn("compare", kinds, trace.name)
            self.assertIn("move", kinds, trace.name)
            self.assertEqual(trace.steps[-1].kind, "done")

    def test_line_state_keeps_length_identity_while_positions_change(self):
        a = MODULE.SortStep("initial", (3, 1, 2))
        b = MODULE.SortStep("move", (1, 3, 2), active=(1, 3))
        state_a = MODULE._line_state(a, 3)
        state_b = MODULE._line_state(b, 3)
        for value in range(1, 4):
            index = value - 1
            length_a = state_a.ends[index].y - state_a.starts[index].y
            length_b = state_b.ends[index].y - state_b.starts[index].y
            self.assertAlmostEqual(length_a, length_b)
        self.assertNotEqual(state_a.starts[0].x, state_b.starts[0].x)
        self.assertNotEqual(state_a.starts[2].x, state_b.starts[2].x)

    def test_single_algorithm_scene_builds_and_evaluates_random_access(self):
        scene, initial, traces = MODULE._build_scene(n=8, seed=7, algorithm="quick")
        self.assertEqual(len(initial), 8)
        self.assertEqual(len(traces), 1)
        self.assertGreater(scene.duration, 0)
        scene.evaluate(0.0)
        scene.evaluate(scene.duration / 2)
        scene.evaluate(scene.duration)


if __name__ == "__main__":
    unittest.main()
