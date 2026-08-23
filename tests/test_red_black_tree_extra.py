import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "extras" / "red_black_tree.py"
SPEC = importlib.util.spec_from_file_location("zanim_red_black_tree_extra", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RedBlackTreeExtraTests(unittest.TestCase):
    def test_random_values_are_unique_and_reproducible(self):
        a = MODULE.random_values(17, 12)
        b = MODULE.random_values(17, 12)
        self.assertEqual(a, b)
        self.assertEqual(len(a), len(set(a)))

    def test_tree_is_valid_after_every_completed_insertion(self):
        values = (41, 18, 65, 12, 30, 52, 79, 10, 15, 25, 34, 60)
        tree = MODULE.RedBlackTree()
        for value in values:
            tree.insert(value)
            self.assertGreaterEqual(tree.validate(), 1)

    def test_trace_contains_insert_recolor_and_rotation_steps(self):
        kinds = {step.kind for step in MODULE.build_trace((10, 20, 30, 15, 25, 5, 1))}
        self.assertIn("insert", kinds)
        self.assertIn("recolor", kinds)
        self.assertTrue("rotate_left" in kinds or "rotate_right" in kinds)

    def test_snapshot_positions_preserve_bst_horizontal_order(self):
        values = (41, 18, 65, 12, 30, 52, 79)
        trace = MODULE.build_trace(values)
        for step in trace:
            positions = MODULE._position_map(step, values)
            present = sorted(state.value for state in step.nodes)
            xs = [positions[value].x for value in present]
            self.assertEqual(xs, sorted(xs))

    def test_scene_builds_and_evaluates_random_access(self):
        scene, info = MODULE._build_scene(seed=3, count=7)
        self.assertEqual(info["count"], 7)
        self.assertGreater(scene.duration, 0)
        for time in (scene.duration, 0.0, scene.duration * 0.57, scene.duration * 0.21):
            scene.evaluate(time)


if __name__ == "__main__":
    unittest.main()
