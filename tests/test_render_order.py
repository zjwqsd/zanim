import unittest

from zanim import (
    BatchObject2D,
    Circle,
    CircleSet,
    Color,
    Object2D,
    Scene,
    Vec2,
    VectorDocument,
    VectorObject2D,
)
from zanim.render.wire import DRAW_BATCH, DRAW_OBJECT, DRAW_VECTOR, encode_snapshot


class RenderOrderTests(unittest.TestCase):
    def test_cross_type_scene_add_order_becomes_draw_order(self):
        vector = VectorObject2D(VectorDocument((), 1.0, 1.0, group_count=0))
        obj = Object2D(Circle(0.5))
        batch = BatchObject2D(CircleSet((Vec2(),), (0.2,), (Color(255, 255, 255),)))
        scene = Scene().add(vector, obj, batch)
        encoded = encode_snapshot(scene.evaluate(0.0))
        self.assertEqual(
            [(item.kind, item.index) for item in encoded.draw_items],
            [(DRAW_VECTOR, 0), (DRAW_OBJECT, 0), (DRAW_BATCH, 0)],
        )


if __name__ == "__main__":
    unittest.main()
