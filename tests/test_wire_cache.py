import gc
import unittest

from zanim import CubicBezier, DynamicVectorObject2D, Scene, Vec2, VectorContour, VectorDocument, VectorPath
from zanim.render import wire
from zanim.render.wire import encode_snapshot
from zanim.vector import map_vector_document


class WireCacheLifetimeTests(unittest.TestCase):
    def test_dynamic_vector_documents_do_not_accumulate_in_wire_cache(self):
        wire._VECTOR_STORAGE.clear()
        seg = CubicBezier(Vec2(), Vec2(0.2, 0), Vec2(0.8, 1), Vec2(1, 1))
        doc = VectorDocument((VectorPath((VectorContour((seg,), False),), fill=None),), 1, 1, 1)
        obj = DynamicVectorObject2D(
            lambda t: map_vector_document(doc, lambda p: Vec2(p.x + t, p.y))
        )
        scene = Scene()
        scene.add(obj)
        for i in range(40):
            encoded = encode_snapshot(scene.evaluate(i / 30))
        del encoded
        gc.collect()
        # The source document is still alive; transient mapped documents are not.
        self.assertLessEqual(len(wire._VECTOR_STORAGE), 1)

    def test_static_vector_document_still_reuses_encoding(self):
        wire._VECTOR_STORAGE.clear()
        seg = CubicBezier(Vec2(), Vec2(0.2, 0), Vec2(0.8, 1), Vec2(1, 1))
        doc = VectorDocument((VectorPath((VectorContour((seg,), False),), fill=None),), 1, 1, 1)
        obj = DynamicVectorObject2D(lambda _t: doc)
        scene = Scene()
        scene.add(obj)
        encode_snapshot(scene.evaluate(0))
        encode_snapshot(scene.evaluate(1))
        self.assertEqual(len(wire._VECTOR_STORAGE), 1)


if __name__ == '__main__':
    unittest.main()
