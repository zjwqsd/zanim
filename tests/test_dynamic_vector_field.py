import unittest

from zanim import DynamicVectorField, Scene, Vec2
from zanim.batch import DynamicBatchObject2D
from zanim.ir import scene_to_ir


class DynamicVectorFieldTests(unittest.TestCase):
    def test_arrows_are_absolute_time_dependent(self):
        field = DynamicVectorField(
            lambda p, t: Vec2(1.0 + t, p.x),
            x_range=(-1, 1),
            y_range=(-1, 1),
            step=1.0,
            show_points=False,
        )
        self.assertIsInstance(field.arrows, DynamicBatchObject2D)
        a = field.arrows.batch_at(0.0)
        b = field.arrows.batch_at(1.0)
        self.assertNotEqual(a, b)
        self.assertEqual(field.arrows.batch_at(1.0), b)

    def test_instantaneous_streamline_changes_with_time(self):
        field = DynamicVectorField(
            lambda _p, t: Vec2(1.0, t),
            x_range=(-2, 2),
            y_range=(-2, 2),
            step=1.0,
            show_points=False,
        )
        at_zero = field.trace_streamline((0, 0), 0.0, direction="forward", step=0.1, max_steps=5)
        at_one = field.trace_streamline((0, 0), 1.0, direction="forward", step=0.1, max_steps=5)
        self.assertAlmostEqual(at_zero[-1].y, 0.0)
        self.assertGreater(at_one[-1].y, 0.2)

    def test_dynamic_streamlines_are_one_dynamic_batch(self):
        field = DynamicVectorField(
            lambda p, t: Vec2(1.0, 0.2 * t - 0.05 * p.y),
            x_range=(-2, 2),
            y_range=(-2, 2),
            step=1.0,
        )
        lines = field.streamlines([(0, 0), (0, 0.5)], max_steps=12)
        self.assertIsInstance(lines, DynamicBatchObject2D)
        self.assertNotEqual(lines.batch_at(0.0), lines.batch_at(1.0))

    def test_scene_ir_bakes_dynamic_arrow_child(self):
        field = DynamicVectorField(
            lambda p, t: Vec2(1.0, p.x + t),
            x_range=(-1, 1),
            y_range=(-1, 1),
            step=1.0,
        )
        scene = Scene(fps=10)
        scene.add(field)
        scene.wait(0.2)
        ir = scene_to_ir(scene, sample_dynamic_providers=True)
        self.assertTrue(any(obj["kind"] == "sampled_batch2d" for obj in ir["objects"]))


if __name__ == "__main__":
    unittest.main()
