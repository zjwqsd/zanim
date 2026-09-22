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

    def test_common_authoring_types_are_root_exports(self):
        for name in (
            "BatchObject2D",
            "DynamicBatchObject2D",
            "CircleSet",
            "LineSet",
            "RectSet",
            "VectorObject2D",
            "DynamicVectorObject2D",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(zanim, name))

    def test_internal_representation_types_are_not_root_exports(self):
        for name in (
            "Object2D",
            "VectorDocument",
            "RasterObject2D",
            "TriangleMesh",
            "Timeline",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(zanim, name))

    def test_constructor_transform_sugar_is_consistent(self):
        text = zanim.Text("x", position=(1, 2), rotation=0.2, scale=1.1)
        self.assertAlmostEqual(text.transform.tx, 1)
        self.assertAlmostEqual(text.transform.ty, 2)

        number = zanim.DynamicNumber(
            lambda t: t,
            number_format=zanim.NumberFormat(width=4, decimals=1),
            position=(-1, 0.5),
        )
        self.assertAlmostEqual(number.transform.tx, -1)
        self.assertAlmostEqual(number.transform.ty, 0.5)

        batch = zanim.BatchObject2D(
            zanim.CircleSet((Vec2(),), (0.1,), (zanim.BLUE,)),
            position=(2, -1),
        )
        self.assertAlmostEqual(batch.transform.tx, 2)
        self.assertAlmostEqual(batch.transform.ty, -1)

        image = zanim.ArrayImage([[0, 255], [255, 0]], position=(0.5, -0.25))
        self.assertAlmostEqual(image.transform.tx, 0.5)
        self.assertAlmostEqual(image.transform.ty, -0.25)

        grid = zanim.InfiniteGrid(0.5, position=(3, 1))
        self.assertAlmostEqual(grid.transform.tx, 3)
        self.assertAlmostEqual(grid.transform.ty, 1)

        with self.assertRaisesRegex(ValueError, "either transform="):
            zanim.Text("x", transform=zanim.Transform2D(), position=(1, 2))

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
