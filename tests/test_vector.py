import unittest

from zanim import Color, CubicBezier, Transform2D, Vec2
from zanim.vector import VectorContour, VectorDocument, VectorObject2D, VectorPath


class VectorTests(unittest.TestCase):
    def test_document_preserves_multi_contour_path(self):
        seg = CubicBezier(Vec2(0, 0), Vec2(1, 0), Vec2(1, 1), Vec2(0, 1))
        path = VectorPath(
            contours=(VectorContour((seg,)), VectorContour((seg,))),
            fill=Color(255, 255, 255),
            group=2,
        )
        doc = VectorDocument((path,), 3, 2, group_count=3)
        self.assertEqual(len(doc.paths[0].contours), 2)
        self.assertEqual(doc.group_count, 3)

    def test_vector_object_transform_is_real_state(self):
        seg = CubicBezier(Vec2(), Vec2(), Vec2(), Vec2(1, 0))
        obj = VectorObject2D(
            VectorDocument((VectorPath((VectorContour((seg,)),)),), 1, 1),
            transform=Transform2D.translation(2, 3),
        )
        before = obj.transform
        obj.transform = obj.transform.rotate(0.5)
        self.assertNotEqual(obj.transform, before)

    def test_reveal_is_bounded(self):
        doc = VectorDocument((), 1, 1, group_count=0)
        with self.assertRaises(ValueError):
            VectorObject2D(doc, reveal=1.1)


if __name__ == "__main__":
    unittest.main()
