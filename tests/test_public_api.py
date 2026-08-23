import unittest

import zanim
from zanim import Circle, Group, Scene, Square, Vec2
from zanim.geometry import CircleGeometry, Object2D


class PublicApiTests(unittest.TestCase):
    def test_public_shapes_are_renderable_scene_objects(self):
        circle = Circle(1, fill=zanim.Color(80, 150, 255))
        self.assertIsInstance(circle, Object2D)
        self.assertIsInstance(circle.geometry, CircleGeometry)
        scene = Scene()
        bound = scene.add(circle)
        self.assertIs(bound.raw, circle)

    def test_representation_types_are_not_root_exports(self):
        for name in (
            "Object2D",
            "BatchObject2D",
            "VectorDocument",
            "RasterObject2D",
            "TriangleMesh",
            "Timeline",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(zanim, name))

    def test_group_children_are_read_only_and_hierarchy_freezes_after_add(self):
        child = Square(1)
        group = Group([child])
        self.assertIsInstance(group.children, tuple)
        self.assertEqual(group.children, (child,))
        with self.assertRaises(AttributeError):
            group.children.append(Circle(1))

        scene = Scene()
        scene.add(group)
        with self.assertRaises(RuntimeError):
            group.add(Circle(1))

    def test_scene_scheduler_is_not_public_mutable_state(self):
        scene = Scene()
        self.assertFalse(hasattr(scene, "timeline"))
        self.assertEqual(scene.duration, 0.0)

    def test_authoring_points_accept_plain_pairs_consistently(self):
        square = Square(1)
        square.place(anchor=zanim.CENTER, at=(1, 2))
        self.assertEqual(square.center, Vec2(1, 2))

        scene = Scene()
        bound = scene.add(square)
        bound.move(to=(-2, 3), duration=0)
        self.assertEqual(bound.center, Vec2(-2, 3))


if __name__ == "__main__":
    unittest.main()

class InfinitePublicApiTests(unittest.TestCase):
    def test_native_unbounded_types_are_public(self):
        self.assertTrue(hasattr(zanim, "InfiniteLine"))
        self.assertTrue(hasattr(zanim, "InfiniteGrid"))
        self.assertTrue(hasattr(zanim, "ComplexMappedGrid"))
