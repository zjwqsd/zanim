import unittest

from zanim import Circle, Color, Object2D, Scene, Square, Style, Transform2D, Vec2
from zanim.group import Group2D


class BoundsAndGroupTests(unittest.TestCase):
    def test_bounds_follow_affine_transform(self):
        obj = Object2D(Square(2), transform=Transform2D.translation(3, 1).scale(2, 1))
        b = obj.bounds()
        self.assertAlmostEqual(b.center.x, 3)
        self.assertAlmostEqual(b.center.y, 1)
        self.assertAlmostEqual(b.width, 4)
        self.assertAlmostEqual(b.height, 2)

    def test_next_to_and_arrange(self):
        a = Object2D(Square(1))
        b = Object2D(Circle(0.5))
        b.next_to(a, Vec2(1, 0), 0.4)
        self.assertAlmostEqual(b.bounds().left - a.bounds().right, 0.4)

        c = Object2D(Square(2))
        group = Group2D([a, b, c]).arrange(Vec2(1, 0), buff=0.2)
        self.assertEqual(len(group), 3)
        self.assertAlmostEqual(group[1].bounds().left - group[0].bounds().right, 0.2)
        self.assertAlmostEqual(group[2].bounds().left - group[1].bounds().right, 0.2)

    def test_group_transform_is_composed_at_evaluation(self):
        child = Object2D(Square(1), transform=Transform2D.translation(1, 0))
        group = Group2D([child], transform=Transform2D.translation(2, 0))
        scene = Scene()
        scene.add(group)
        self.assertEqual(len(scene.objects), 1)
        self.assertAlmostEqual(scene.evaluate(0).objects[0].snapshot.transform.tx, 3)
        scene.transform(group, to=Transform2D.translation(5, 0), duration=1)
        self.assertAlmostEqual(scene.evaluate(1).objects[0].snapshot.transform.tx, 6)

    def test_camera_is_same_transform_channel(self):
        obj = Object2D(Square(1), transform=Transform2D.translation(2, 0))
        scene = Scene()
        scene.add(obj)
        scene.transform(scene.camera, to=Transform2D.scaling(2), duration=1)
        snap = scene.evaluate(1).objects[0].snapshot
        self.assertAlmostEqual(snap.transform.tx, 4)
        self.assertAlmostEqual(snap.transform.xx, 2)

    def test_group_z_and_opacity_compose(self):
        child = Object2D(Square(1), opacity=0.5, z_index=2)
        group = Group2D([child], opacity=0.4, z_index=3)
        scene = Scene()
        scene.add(group)
        snap = scene.evaluate(0).objects[0].snapshot
        self.assertAlmostEqual(snap.opacity, 0.2)
        self.assertEqual(snap.z_index, 5)

    def test_group_opacity_clip_affects_children(self):
        child = Object2D(Square(1), opacity=.8)
        group = Group2D([child], opacity=.5)
        scene = Scene()
        scene.add(group)
        scene.fade_out(group, duration=2)
        self.assertAlmostEqual(scene.evaluate(0).objects[0].snapshot.opacity, .4)
        self.assertAlmostEqual(scene.evaluate(1).objects[0].snapshot.opacity, .2)
        self.assertAlmostEqual(scene.evaluate(2).objects[0].snapshot.opacity, 0)


if __name__ == '__main__':
    unittest.main()
