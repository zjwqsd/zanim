import unittest

from zanim import Color, CubicBezier, DynamicVectorObject2D, Scene, Vec2, VectorContour, VectorDocument, VectorPath
from zanim.vector import map_vector_document


class DynamicVectorTests(unittest.TestCase):
    def setUp(self):
        seg = CubicBezier(Vec2(0, 0), Vec2(1, 0), Vec2(1, 1), Vec2(2, 1))
        self.doc = VectorDocument(
            (VectorPath((VectorContour((seg,), False),), fill=None),),
            width=2.0,
            height=1.0,
            group_count=1,
        )

    def test_point_mapping_preserves_metadata_by_default(self):
        mapped = map_vector_document(self.doc, lambda p: Vec2(p.x * 3, p.y * 4))
        self.assertEqual((mapped.width, mapped.height), (2.0, 1.0))
        self.assertEqual(mapped.paths[0].contours[0].segments[0].p3, Vec2(6, 4))

    def test_point_mapping_can_recompute_intrinsic_size(self):
        mapped = map_vector_document(
            self.doc, lambda p: Vec2(p.x * 3, p.y * 4), update_size=True
        )
        self.assertAlmostEqual(mapped.width, 6.0)
        self.assertAlmostEqual(mapped.height, 4.0)

    def test_dynamic_vector_is_random_access(self):
        obj = DynamicVectorObject2D(
            lambda t: map_vector_document(self.doc, lambda p: Vec2(p.x + t, p.y))
        )
        scene = Scene()
        scene.add(obj)
        a = scene.evaluate(0.75).vectors[0].snapshot.document
        scene.evaluate(0.1)
        b = scene.evaluate(0.75).vectors[0].snapshot.document
        self.assertEqual(a, b)
        self.assertEqual(a.paths[0].contours[0].segments[0].p0, Vec2(0.75, 0))


if __name__ == '__main__':
    unittest.main()
