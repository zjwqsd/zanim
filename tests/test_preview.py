from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zanim import Audio, Canvas, Circle, Image, Scene, Video
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
            self.assertIn(b">Timeline<", html)
            self.assertNotIn(b"Scene IR Inspector", html)
            self.assertNotIn(b"sourceCode", html)
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

    def test_preview_exposes_media_as_nonportable_external_resources(self):
        root = Path(__file__).resolve().parents[1]
        image_path = root / "tests/assets/media_demo/image.png"
        scene = Scene(canvas=Canvas(320, 180, 40), fps=30)
        scene.add(Image(image_path, width=2.5))
        server = self._server(scene)
        try:
            with urlopen(server.url + "api/ir") as response:
                ir = json.loads(response.read())
            media = next(obj for obj in ir["objects"] if obj["kind"] == "media2d")
            resource = next(r for r in ir["resources"] if r["id"] == media["state"]["resource"])
            self.assertEqual(resource["kind"], "external_media")
            self.assertEqual(resource["data"]["media_kind"], "image")
            self.assertFalse(ir["meta"]["portable"])
            with urlopen(server.url.rstrip("/") + resource["data"]["url"]) as response:
                payload = response.read()
            self.assertEqual(payload, image_path.read_bytes())
        finally:
            server.close()

    def test_preview_video_supports_range_requests_and_playback_ir(self):
        root = Path(__file__).resolve().parents[1]
        video_path = root / "tests/assets/media_demo/clip.mp4"
        scene = Scene(canvas=Canvas(320, 180, 40), fps=30)
        video = scene.add(Video(video_path, width=3.0))
        video.media(duration=3.0, source_start=0.25, speed=1.25, loop=True)
        server = self._server(scene)
        try:
            with urlopen(server.url + "api/ir") as response:
                ir = json.loads(response.read())
            playback = next(clip for clip in ir["clips"] if clip["kind"] == "media_playback")
            self.assertEqual(playback["source_start"], 0.25)
            self.assertEqual(playback["speed"], 1.25)
            self.assertTrue(playback["loop"])
            resource = next(r for r in ir["resources"] if r["kind"] == "external_media")
            request = Request(
                server.url.rstrip("/") + resource["data"]["url"], headers={"Range": "bytes=0-15"}
            )
            with urlopen(request) as response:
                payload = response.read()
                self.assertEqual(response.status, 206)
                self.assertEqual(
                    response.headers["Content-Range"], f"bytes 0-15/{video_path.stat().st_size}"
                )
            self.assertEqual(payload, video_path.read_bytes()[:16])
        finally:
            server.close()

    def test_preview_audio_uses_external_media_and_playback_channel(self):
        root = Path(__file__).resolve().parents[1]
        audio_path = root / "tests/assets/media_demo/tone.wav"
        scene = Scene(canvas=Canvas(160, 90, 20), fps=30)
        audio = scene.add(Audio(audio_path, gain=0.25))
        audio.media(duration=1.5, loop=True)
        server = self._server(scene)
        try:
            with urlopen(server.url + "api/ir") as response:
                ir = json.loads(response.read())
            record = next(obj for obj in ir["objects"] if obj["kind"] == "audio")
            self.assertEqual(record["state"]["gain"], 0.25)
            self.assertEqual(
                next(r for r in ir["resources"] if r["id"] == record["state"]["resource"])["data"][
                    "media_kind"
                ],
                "audio",
            )
            self.assertEqual(
                next(c for c in ir["clips"] if c["kind"] == "media_playback")["duration"], 1.5
            )
        finally:
            server.close()

    def test_preview_typst_endpoint_returns_vector_document(self):
        scene = Scene(canvas=Canvas(160, 90, 20))
        server = self._server(scene)
        try:
            request = Request(
                server.url + "api/typst",
                data=json.dumps(
                    {"kind": "math", "source": "x^2 + y^2", "font_size": 28, "color": "#60a6ff"}
                ).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                result = json.loads(response.read())
            self.assertTrue(result["ok"])
            self.assertGreater(result["document"]["width"], 0)
            self.assertTrue(result["document"]["paths"])
        finally:
            server.close()

    def test_close_without_start_is_safe(self):
        scene = Scene(canvas=Canvas(80, 48, 12))
        server = PreviewServer(scene, host="127.0.0.1", port=0)
        server.close()


if __name__ == "__main__":
    unittest.main()
