import tempfile
import unittest
from pathlib import Path

from PIL import Image as PILImage

from zanim import (
    BatchObject2D,
    Circle,
    CircleSet,
    Color,
    Image,
    Object2D,
    Scene,
    Vec2,
    VectorDocument,
    VectorObject2D,
)
from zanim.render.wire import DRAW_BATCH, DRAW_OBJECT, DRAW_RASTER, DRAW_VECTOR, encode_snapshot


class RenderOrderTests(unittest.TestCase):
    def test_cross_type_scene_add_order_becomes_draw_order(self):
        vector = VectorObject2D(VectorDocument((), 1.0, 1.0, group_count=0))
        obj = Object2D(Circle(0.5))
        batch = BatchObject2D(CircleSet((Vec2(),), (0.2,), (Color(255, 255, 255),)))
        scene = Scene()
        scene.add(vector, obj, batch)
        encoded = encode_snapshot(scene.evaluate(0.0))
        self.assertEqual(
            [(item.kind, item.index) for item in encoded.draw_items],
            [(DRAW_VECTOR, 0), (DRAW_OBJECT, 0), (DRAW_BATCH, 0)],
        )

    def test_raster_uses_same_z_index_and_insertion_order(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pixel.png"
            PILImage.new("RGBA", (1, 1), (255, 0, 0, 255)).save(path)
            low = Object2D(Circle(0.5), z_index=-1)
            raster = Image(path, z_index=0)
            high = Object2D(Circle(0.2), z_index=1)
            scene = Scene()
            scene.add(high, raster, low)
            encoded = encode_snapshot(scene.evaluate(0.0))
            self.assertEqual(
                [item.kind for item in encoded.draw_items],
                [DRAW_OBJECT, DRAW_RASTER, DRAW_OBJECT],
            )


if __name__ == "__main__":
    unittest.main()
