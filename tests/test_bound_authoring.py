import math
import unittest

from zanim import (
    BoundGroup2D, BoundObject2D, Circle, Easing, Group2D, LOCAL, Object2D,
    PARENT, Scene, SE2, Square, Transform2D, Vec2, WORLD, affine2d, pose2d,
)


class BoundAuthoringTests(unittest.TestCase):
    def test_add_returns_stable_bound_handle_without_replacing_identity(self):
        raw = Object2D(Square(1), trim=0)
        scene = Scene()
        bound = scene.add(raw)

        self.assertIsInstance(bound, BoundObject2D)
        self.assertIs(bound.raw, raw)
        self.assertIs(scene.on(raw), bound)
        self.assertIs(scene.on(bound), bound)
        self.assertIs(scene.objects[0], raw)

    def test_add_many_returns_handles_in_order(self):
        a = Object2D(Square(1))
        b = Object2D(Circle(1))
        scene = Scene()
        ba, bb = scene.add(a, b)
        self.assertIs(ba.raw, a)
        self.assertIs(bb.raw, b)

    def test_bound_handle_owns_post_add_timeline_operations(self):
        raw = Object2D(Square(1), trim=0)
        scene = Scene()
        obj = scene.add(raw)
        obj.create(duration=1, easing=Easing.LINEAR)
        obj.move(to=(3, 2), duration=1, easing=Easing.LINEAR)

        self.assertEqual(obj.center, Vec2(3, 2))
        self.assertAlmostEqual(scene.evaluate(1.5).objects[0].snapshot.transform.tx, 1.5)
        self.assertAlmostEqual(scene.evaluate(1.5).objects[0].snapshot.transform.ty, 1.0)

    def test_pose_is_complete_absolute_se2_target(self):
        raw = Object2D(Square(1))
        scene = Scene()
        obj = scene.add(raw)
        obj.pose(to=(2, 1), rotation=math.pi / 2, duration=2, easing=Easing.LINEAR)

        expected = SE2(theta=math.pi / 2, translation=Vec2(2, 1)).as_affine()
        self.assertEqual(raw.transform, expected)
        mid = scene.evaluate(1).objects[0].snapshot.transform
        self.assertAlmostEqual(mid.tx, 1.0)
        self.assertAlmostEqual(mid.ty, .5)
        self.assertAlmostEqual(mid.determinant, 1.0)

    def test_affine_has_fixed_explicit_composition_order(self):
        raw = Object2D(Square(1))
        scene = Scene()
        obj = scene.add(raw)
        obj.affine(
            to=(2, -1), rotation=.3, scale=(2, .5), shear=(.2, -.1), duration=0
        )
        expected = (
            Transform2D.translation(2, -1)
            @ Transform2D.rotation(.3)
            @ Transform2D.shear(.2, -.1)
            @ Transform2D.scaling(2, .5)
        )
        self.assertEqual(raw.transform, expected)

    def test_relative_motion_still_requires_explicit_frame(self):
        scene = Scene()
        obj = scene.add(Object2D(Square(1)))
        with self.assertRaisesRegex(ValueError, "explicit frame"):
            obj.move(by=(1, 0))
        obj.move(by=(1, 0), frame=LOCAL, duration=0)
        self.assertEqual(obj.origin, Vec2(1, 0))

    def test_group_children_are_bound_to_same_scene(self):
        child = Object2D(Square(1))
        group = Group2D([child])
        scene = Scene()
        bound_group = scene.add(group)
        self.assertIsInstance(bound_group, BoundGroup2D)
        self.assertIs(bound_group.children[0], scene.on(child))


    def test_bound_handle_does_not_reexpose_pre_add_layout_mutators(self):
        scene = Scene()
        obj = scene.add(Object2D(Square(1)))
        self.assertFalse(hasattr(obj, "place"))
        self.assertFalse(hasattr(obj, "shift"))
        self.assertFalse(hasattr(obj, "move_to"))

    def test_pure_pose_and_affine_factories_match_bound_sugar(self):
        self.assertEqual(
            pose2d(to=(2, 1), rotation=.4),
            SE2(theta=.4, translation=Vec2(2, 1)),
        )
        self.assertEqual(
            affine2d(to=(2, 1), rotation=.4, scale=(2, .5), shear=(.1, -.2)),
            Transform2D.translation(2, 1)
            @ Transform2D.rotation(.4)
            @ Transform2D.shear(.1, -.2)
            @ Transform2D.scaling(2, .5),
        )

    def test_handle_cannot_cross_scene_ownership(self):
        scene_a = Scene()
        handle = scene_a.add(Object2D(Square(1)))
        with self.assertRaisesRegex(ValueError, "different Scene"):
            Scene().on(handle)

    def test_scene_relations_accept_bound_handles(self):
        scene = Scene()
        a, b = scene.add(Object2D(Square(1)), Object2D(Circle(1)))
        scene.interpolate(a, b, duration=.5)
        self.assertEqual(len(scene.evaluate(.25).transients), 1)

    def test_replace_returns_bound_target(self):
        scene = Scene()
        source = scene.add(Object2D(Square(1)))
        target_raw = Object2D(Circle(1))
        target = scene.replace(source, target_raw, duration=.5)
        self.assertIs(target.raw, target_raw)
        self.assertIs(scene.on(target_raw), target)
        self.assertEqual(scene.evaluate(.25).objects, ())
        self.assertEqual(len(scene.evaluate(.25).transients), 1)
        self.assertEqual(len(scene.evaluate(.5).objects), 1)


if __name__ == '__main__':
    unittest.main()
