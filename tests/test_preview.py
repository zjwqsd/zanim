from __future__ import annotations

import json
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from zanim import Canvas, Circle, Scene
from zanim.batch import DynamicBatchObject2D, LineSet
from zanim.geometry import Color
from zanim.preview import PreviewServer
from zanim.space import Vec2


class WebPreviewTests(unittest.TestCase):
    def _server(self, scene: Scene) -> PreviewServer:
        return PreviewServer(scene, host="127.0.0.1", port=0).start(open_browser=False)

    def test_preview_serves_web_ir_instead_of_frames(self):
        scene = Scene(canvas=Canvas(160, 90, 20), fps=30)
        circle = scene.add(Circle(1))
        circle.opacity(to=0.25, duration=1.5)
        server = self._server(scene)
        try:
            with urlopen(server.url) as response:
                html = response.read()
            self.assertIn(b"Zanim Web Preview", html)
            self.assertIn(b"/preview/main.js", html)
            self.assertNotIn(b"api/frame/raw", html)

            with urlopen(server.url + "api/meta") as response:
                meta = json.loads(response.read())
            self.assertEqual(meta["renderer"], "web-ir")
            self.assertTrue(meta["ir_available"])
            self.assertEqual(meta["fps"], 30)

            with urlopen(server.url + "api/ir") as response:
                ir = json.loads(response.read())
            self.assertEqual(ir["format"], "zanim.scene")
            self.assertEqual(ir["duration"], 1.5)
            self.assertEqual(ir["meta"]["preview_revision"], 1)

            with self.assertRaises(HTTPError) as caught:
                urlopen(server.url + "api/frame/raw?t=0")
            self.assertEqual(caught.exception.code, 404)
        finally:
            server.close()

    def test_preview_serves_shared_runtime_and_wasm(self):
        scene = Scene(canvas=Canvas(160, 90, 20))
        scene.add(Circle(1))
        server = self._server(scene)
        try:
            for relative, expected_type in (
                ("web/src/zanim.js", "javascript"),
                ("web/src/ir.js", "javascript"),
                ("web/dist/zanim_web_core.wasm", "application/wasm"),
            ):
                with urlopen(server.url + relative) as response:
                    payload = response.read()
                    content_type = response.headers.get_content_type()
                self.assertTrue(payload)
                if expected_type == "javascript":
                    self.assertIn("javascript", content_type)
                else:
                    self.assertEqual(content_type, expected_type)
        finally:
            server.close()

    def test_dynamic_provider_is_baked_for_web_preview(self):
        dynamic = DynamicBatchObject2D(
            lambda t: LineSet(
                (Vec2(0, 0),),
                (Vec2(1 + t, 0),),
                (Color(255, 255, 255),),
                (0.03,),
            )
        )
        scene = Scene(canvas=Canvas(160, 90, 20), fps=30)
        scene.add(dynamic)
        scene.wait(1.0)
        server = self._server(scene)
        try:
            with urlopen(server.url + "api/ir") as response:
                ir = json.loads(response.read())
            sampled = next(obj for obj in ir["objects"] if obj["kind"] == "sampled_batch2d")
            self.assertEqual(sampled["state"]["sample_rate"], 30)
            self.assertEqual(len(sampled["state"]["samples"]), 31)
            self.assertEqual(ir["meta"]["sampled_dynamic_objects"], 1)
            with urlopen(server.url + "api/meta") as response:
                meta = json.loads(response.read())
            self.assertTrue(meta["ir_available"])
        finally:
            server.close()

    def test_close_without_start_is_safe(self):
        scene = Scene(canvas=Canvas(80, 48, 12))
        server = PreviewServer(scene, host="127.0.0.1", port=0)
        server.close()


if __name__ == "__main__":
    unittest.main()
