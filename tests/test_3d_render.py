import hashlib
import unittest
from concurrent.futures import ThreadPoolExecutor

from zanim import Canvas, Color, Cube3D, Scene, Square, Style
from zanim.render.frame import render_snapshot_rgba


class Integrated3DRenderTests(unittest.TestCase):
    def test_opaque_and_transparent_3d_share_scene_rgba_surface(self):
        scene = Scene(canvas=Canvas(160, 90, 30))
        opaque = Cube3D(0.7)
        translucent = Cube3D(0.7, color=Color(180, 210, 255))
        translucent.transform = translucent.transform.translate(1.0, 0.0, 0.0)
        translucent.opacity = 0.35
        opaque.transform = opaque.transform.translate(-1.0, 0.0, 0.0)
        scene.add(opaque, translucent)

        rgba = bytearray(scene.width * scene.height * 4)
        render_snapshot_rgba(rgba, scene.evaluate(0.0), scene.canvas)
        alpha = rgba[3::4]
        self.assertTrue(any(0 < value < 255 for value in alpha))
        self.assertTrue(any(value == 255 for value in alpha))

    def test_3d_layer_participates_in_normal_z_order(self):
        scene = Scene(canvas=Canvas(200, 120, 30))
        cube = Cube3D(2.0, color=Color(70, 150, 245))
        overlay = Square(1.1, style=Style(fill=Color(245, 70, 70), stroke=None), z_index=1)
        scene.add(cube, overlay)

        def center_rgb() -> tuple[int, int, int]:
            rgba = bytearray(scene.width * scene.height * 4)
            render_snapshot_rgba(rgba, scene.evaluate(0.0), scene.canvas)
            base = ((scene.height // 2) * scene.width + scene.width // 2) * 4
            return tuple(rgba[base : base + 3])

        scene.camera3d.layer_z_index = 0
        above = center_rgb()
        self.assertGreater(above[0], above[2])  # red 2D square above 3D

        scene.camera3d.layer_z_index = 2
        below = center_rgb()
        self.assertGreater(below[2], below[0])  # blue cube above 2D square

    def test_parallel_frames_are_deterministic(self):
        scene = Scene(canvas=Canvas(240, 135, 36))
        scene.add(Cube3D(1.6, color=Color(80, 165, 250)))
        snapshot = scene.evaluate(0.0)

        def render_hash(_: int) -> str:
            rgba = bytearray(scene.width * scene.height * 4)
            render_snapshot_rgba(rgba, snapshot, scene.canvas)
            return hashlib.sha256(rgba).hexdigest()

        with ThreadPoolExecutor(max_workers=8) as pool:
            hashes = list(pool.map(render_hash, range(16)))
        self.assertEqual(len(set(hashes)), 1)


if __name__ == "__main__":
    unittest.main()
