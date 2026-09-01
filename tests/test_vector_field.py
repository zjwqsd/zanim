from __future__ import annotations

import unittest

from zanim import Group, Scene, Vec2, VectorField, scene_from_ir, scene_to_ir
from zanim.batch import CircleSet, LineSet


class VectorFieldTests(unittest.TestCase):
    def test_sampled_points_and_arrows_are_batched(self):
        field = VectorField(
            lambda p: Vec2(1.0, 0.0),
            x_range=(-1.0, 1.0),
            y_range=(-1.0, 1.0),
            step=1.0,
            vector_length=0.4,
        )
        self.assertEqual(len(field.samples), 9)
        self.assertIsNotNone(field.points)
        self.assertIsNotNone(field.arrows)
        assert field.points is not None and field.arrows is not None
        self.assertIsInstance(field.points.batch, CircleSet)
        self.assertIsInstance(field.arrows.batch, LineSet)
        self.assertEqual(len(field.arrows.batch), 27)  # shaft + two head segments
        self.assertAlmostEqual(field.arrows.batch.ends[0].x - field.arrows.batch.starts[0].x, 0.4)
        self.assertAlmostEqual(field.arrows.batch.ends[0].y - field.arrows.batch.starts[0].y, 0.0)

    def test_zero_vectors_keep_points_but_skip_arrows(self):
        field = VectorField(
            lambda _p: Vec2(),
            x_range=(-1.0, 1.0),
            y_range=(-1.0, 1.0),
            step=1.0,
        )
        self.assertIsNotNone(field.points)
        self.assertIsNone(field.arrows)

    def test_constant_field_streamline_is_horizontal_and_seek_independent(self):
        field = VectorField(
            lambda _p: Vec2(2.0, 0.0),
            x_range=(-1.0, 1.0),
            y_range=(-1.0, 1.0),
            step=1.0,
            show_points=False,
        )
        points = field.trace_streamline((0.0, 0.25), direction="both", step=0.1, max_steps=50)
        self.assertGreater(len(points), 10)
        self.assertTrue(all(abs(point.y - 0.25) < 1e-12 for point in points))
        self.assertTrue(all(a.x < b.x for a, b in zip(points, points[1:])))
        self.assertGreaterEqual(points[0].x, -1.0)
        self.assertLessEqual(points[-1].x, 1.0)

    def test_field_reuses_existing_scene_ir_primitives(self):
        field = VectorField(
            lambda _p: Vec2(1.0, 0.0),
            x_range=(-1.0, 1.0),
            y_range=(-1.0, 1.0),
            step=1.0,
        )
        scene = Scene()
        scene.add(field)
        ir = scene_to_ir(scene)
        kinds = [record["kind"] for record in ir["objects"]]
        self.assertIn("group", kinds)
        self.assertEqual(kinds.count("batch2d"), 2)
        rebuilt = scene_from_ir(ir)
        self.assertEqual(len(rebuilt.objects), 2)

    def test_streamlines_returns_group_of_polylines(self):
        field = VectorField(
            lambda p: Vec2(-p.y, p.x),
            x_range=(-2.0, 2.0),
            y_range=(-2.0, 2.0),
            step=1.0,
        )
        lines = field.streamlines(((1.0, 0.0), (1.5, 0.0)), step=0.05, max_steps=20)
        self.assertIsInstance(lines, Group)
        self.assertEqual(len(lines.children), 2)


if __name__ == "__main__":
    unittest.main()
