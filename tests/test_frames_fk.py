import math
import unittest

from zanim import (
    LOCAL, PARENT, WORLD, Easing, Group2D, Line, Object2D, ORIGIN, RIGHT,
    SE2, Scene, Style, Transform2D, Vec2,
)


class TransformFrameTests(unittest.TestCase):
    def test_by_requires_explicit_frame(self):
        obj = Object2D(Line(ORIGIN, RIGHT))
        scene = Scene()
        scene.add(obj)
        with self.assertRaisesRegex(ValueError, "explicit frame"):
            scene.transform(obj, by=SE2(theta=.2))
        with self.assertRaisesRegex(ValueError, "explicit frame"):
            scene.move(obj, by=RIGHT)

    def test_parent_left_multiply_and_local_right_multiply(self):
        base = SE2(theta=math.pi / 2, translation=Vec2(2, 0)).as_affine()

        parent_obj = Object2D(Line(ORIGIN, RIGHT), transform=base)
        parent_scene = Scene()
        parent_scene.add(parent_obj)
        parent_scene.move(parent_obj, by=RIGHT, frame=PARENT, duration=0)
        self.assertAlmostEqual(parent_obj.transform.tx, 3.0)
        self.assertAlmostEqual(parent_obj.transform.ty, 0.0)

        local_obj = Object2D(Line(ORIGIN, RIGHT), transform=base)
        local_scene = Scene()
        local_scene.add(local_obj)
        local_scene.move(local_obj, by=RIGHT, frame=LOCAL, duration=0)
        self.assertAlmostEqual(local_obj.transform.tx, 2.0)
        self.assertAlmostEqual(local_obj.transform.ty, 1.0)

    def test_world_delta_is_conjugated_through_parent(self):
        child = Object2D(Line(ORIGIN, RIGHT), transform=Transform2D.translation(2, 0))
        parent = Group2D([child], transform=SE2(theta=math.pi / 2).as_affine())
        scene = Scene()
        scene.add(parent)
        scene.move(child, by=RIGHT, frame=WORLD, duration=0)
        world = scene.world_transform(child)
        self.assertAlmostEqual(world.tx, 1.0)
        self.assertAlmostEqual(world.ty, 2.0)

    def test_move_to_is_absolute_world_anchor_even_for_nested_child(self):
        child = Object2D(Line(Vec2(-.5, 0), Vec2(.5, 0)), transform=Transform2D.translation(2, 0))
        parent = Group2D([child], transform=SE2(theta=math.pi / 2).as_affine())
        scene = Scene()
        scene.add(parent)
        scene.move(child, to=Vec2(3, 4), duration=0)
        world_center = scene.world_transform(child).apply(ORIGIN)
        self.assertAlmostEqual(world_center.x, 3.0)
        self.assertAlmostEqual(world_center.y, 4.0)

    def test_se2_interpolation_stays_rigid(self):
        obj = Object2D(Line(ORIGIN, RIGHT))
        scene = Scene()
        scene.add(obj)
        scene.transform(
            obj, to=SE2(theta=math.pi / 2, translation=Vec2(2, 0)),
            duration=2, easing=Easing.LINEAR,
        )
        T = scene.world_transform(obj, time=1)
        rigid = SE2.from_affine(T)
        self.assertAlmostEqual(rigid.translation.x, 1.0)
        self.assertAlmostEqual(rigid.theta, math.pi / 4)
        self.assertAlmostEqual(T.determinant, 1.0)


class ForwardKinematicsTests(unittest.TestCase):
    def test_nested_groups_are_open_chain_forward_kinematics(self):
        l1, l2, l3 = 2.0, 1.5, 1.0
        link3 = Object2D(Line(ORIGIN, Vec2(l3, 0)), style=Style())
        joint3 = Group2D([link3], transform=Transform2D.translation(l2, 0))
        link2 = Object2D(Line(ORIGIN, Vec2(l2, 0)), style=Style())
        joint2 = Group2D([link2, joint3], transform=Transform2D.translation(l1, 0))
        link1 = Object2D(Line(ORIGIN, Vec2(l1, 0)), style=Style())
        joint1 = Group2D([link1, joint2])
        scene = Scene()
        scene.add(joint1)

        q1, q2, q3 = .3, -.5, .7
        scene.transform(joint1, by=SE2(theta=q1), frame=LOCAL, duration=0)
        scene.transform(joint2, by=SE2(theta=q2), frame=LOCAL, duration=0)
        scene.transform(joint3, by=SE2(theta=q3), frame=LOCAL, duration=0)

        expected = (
            SE2(theta=q1).as_affine()
            @ Transform2D.translation(l1, 0)
            @ SE2(theta=q2).as_affine()
            @ Transform2D.translation(l2, 0)
            @ SE2(theta=q3).as_affine()
        )
        actual = scene.world_transform(joint3)
        for a, b in zip((actual.xx, actual.xy, actual.yx, actual.yy, actual.tx, actual.ty),
                        (expected.xx, expected.xy, expected.yx, expected.yy, expected.tx, expected.ty)):
            self.assertAlmostEqual(a, b)

    def test_prismatic_joint_is_local_translation(self):
        slider = Group2D([], transform=SE2(theta=math.pi / 2, translation=Vec2(1, 0)).as_affine())
        scene = Scene()
        scene.add(slider)
        scene.move(slider, by=2 * RIGHT, frame=LOCAL, duration=0)
        p = scene.world_point(slider)
        self.assertAlmostEqual(p.x, 1.0)
        self.assertAlmostEqual(p.y, 2.0)


if __name__ == "__main__":
    unittest.main()

class WorldFrameConcurrencyTests(unittest.TestCase):
    def test_nested_world_transform_rejects_moving_parent_in_either_schedule_order(self):
        child = Object2D(Line(ORIGIN, RIGHT))
        parent = Group2D([child])
        scene = Scene()
        scene.add(parent)
        with self.assertRaisesRegex(ValueError, "ancestors"):
            with scene.parallel():
                scene.transform(parent, by=SE2(theta=.5), frame=LOCAL, duration=1)
                scene.move(child, by=RIGHT, frame=WORLD, duration=1)

        child2 = Object2D(Line(ORIGIN, RIGHT))
        parent2 = Group2D([child2])
        scene2 = Scene()
        scene2.add(parent2)
        with self.assertRaisesRegex(ValueError, "ancestor transform overlaps"):
            with scene2.parallel():
                scene2.move(child2, by=RIGHT, frame=WORLD, duration=1)
                scene2.transform(parent2, by=SE2(theta=.5), frame=LOCAL, duration=1)

class RelativeRigidPathTests(unittest.TestCase):
    def test_relative_se2_preserves_full_turn_winding(self):
        obj = Object2D(Line(ORIGIN, RIGHT))
        scene = Scene()
        scene.add(obj)
        scene.transform(obj, by=SE2(theta=2 * math.pi), frame=LOCAL, duration=2, easing=Easing.LINEAR)
        mid = scene.world_transform(obj, time=1).apply(RIGHT)
        self.assertAlmostEqual(mid.x, -1.0, places=6)
        self.assertAlmostEqual(mid.y, 0.0, places=6)

    def test_rotate_about_world_pivot_preserves_radius_mid_clip(self):
        obj = Object2D(Line(ORIGIN, RIGHT), transform=SE2(translation=Vec2(2, 0)))
        scene = Scene()
        scene.add(obj)
        scene.rotate(obj, by=math.pi, about=ORIGIN, duration=2, easing=Easing.LINEAR)
        mid_origin = scene.world_point(obj, ORIGIN, time=1)
        self.assertAlmostEqual(mid_origin.x, 0.0, places=6)
        self.assertAlmostEqual(mid_origin.y, 2.0, places=6)
        self.assertAlmostEqual(mid_origin.length, 2.0, places=6)
