import unittest

from zanim import (
    TOP,
    TOP_LEFT,
    Canvas,
    Circle,
    Column,
    Grid,
    Group,
    Rectangle,
    Row,
    Scene,
    Square,
    Vec2,
)


class LayoutTests(unittest.TestCase):
    def test_frame_exposes_visual_points(self):
        scene = Scene(canvas=Canvas(800, 600, 100))
        self.assertEqual(scene.frame.top, Vec2(0, 3))
        self.assertEqual(scene.frame.right, Vec2(4, 0))
        self.assertEqual(scene.frame.top_left, Vec2(-4, 3))
        self.assertEqual(scene.frame.inset(0.5).center, Vec2())

    def test_place_names_object_anchor_and_world_target(self):
        obj = Rectangle(2, 1)
        obj.place(anchor=TOP_LEFT, at=Vec2(-3, 2))
        self.assertEqual(obj.anchor(TOP_LEFT), Vec2(-3, 2))
        self.assertEqual(obj.center, Vec2(-2, 1.5))

    def test_row_is_a_pure_layout_spec_until_place(self):
        a = Square(1)
        b = Rectangle(2, 1)
        layout = Row(gap=0.5, at=Vec2(1, 2))
        targets = layout.targets(a, b)
        self.assertEqual(a.center, Vec2())
        self.assertEqual(b.center, Vec2())
        self.assertNotEqual(targets[0], a.transform)
        layout.place(a, b)
        self.assertAlmostEqual(b.bounds().left - a.bounds().right, 0.5)
        self.assertAlmostEqual((a.bounds().left + b.bounds().right) * 0.5, 1.0)

    def test_column_can_align_left_edges(self):
        a = Square(1)
        b = Rectangle(2, 1)
        Column(gap=0.4, align=Vec2(-1, 0), anchor=TOP, at=Vec2(3, 2)).place(a, b)
        self.assertAlmostEqual(a.bounds().left, b.bounds().left)
        self.assertAlmostEqual(max(a.bounds().top, b.bounds().top), 2)

    def test_scene_layout_animates_group_children_independently(self):
        items = [Circle(0.3) for _ in range(4)]
        Row(gap=0.4, at=Vec2(0, 1.5)).place(*items)
        group = Group(items)
        scene = Scene()
        scene.add(group)
        scene.layout(group, to=Grid(rows=2, cols=2, gap=0.6, at=Vec2()), duration=2)
        self.assertEqual(len(scene._timeline.clips), 4)
        self.assertEqual(scene._timeline.cursor, 2)
        end_centers = [obj.center for obj in items]
        self.assertEqual(len({(round(p.x, 6), round(p.y, 6)) for p in end_centers}), 4)
        mid = scene.evaluate(1)
        self.assertEqual(len(mid.objects), 4)

    def test_layout_can_participate_in_outer_parallel_block(self):
        a = Square(1)
        b = Square(1)
        group = Group([a, b])
        scene = Scene()
        scene.add(group)
        with scene.parallel():
            clips = scene.layout(group, to=Row(gap=0.5), duration=2)
        self.assertEqual(len(clips), 2)
        self.assertEqual(scene._timeline.cursor, 2)

    def test_place_is_initial_layout_only(self):
        obj = Square(1)
        scene = Scene()
        scene.add(obj)
        with self.assertRaises(RuntimeError):
            Row().place(obj)


if __name__ == "__main__":
    unittest.main()
