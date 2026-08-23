from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zanim import Canvas, Circle, MediaError, Scene, ZanimError
from zanim.cli import _load_scene, main as cli_main
from zanim.preview import PreviewServer
from zanim.render.abi import ABI_VERSION, load_library
from zanim.runtime import ffmpeg_path, require_ffmpeg
from zanim.source import get_preview_source, preview_source, reload_preview_scene


@preview_source
def _source_scene() -> Scene:
    scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
    obj = scene.add(Circle(1))
    obj.move(to=(1, 0), duration=1)
    return scene


class ProductRuntimeTests(unittest.TestCase):
    def test_official_extras_expose_uniform_scene_builder(self):
        import inspect

        from examples.extras import fourier_draw, mnist_training, neural_network

        for module in (fourier_draw, neural_network, mnist_training):
            with self.subTest(module=module.__name__):
                self.assertEqual(len(inspect.signature(module.build_scene).parameters), 0)

    def test_native_abi_matches_python_package(self):
        lib = load_library()
        self.assertEqual(int(lib.zanim_abi_version()), ABI_VERSION)

    def test_cli_info_reports_renderer(self):
        output = StringIO()
        with redirect_stdout(output):
            status = cli_main(["info"])
        self.assertEqual(status, 0)
        text = output.getvalue()
        self.assertIn("Renderer   OK", text)
        self.assertIn(f"ABI      {ABI_VERSION}", text)

    def test_bare_script_tracks_names_sources_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bare.py"
            source.write_text(
                "from zanim import Canvas, Circle, Scene\n"
                "scene = Scene(canvas=Canvas(80, 48, 12), fps=10)\n"
                "marker = scene.add(Circle(1))\n"
                "marker.move(\n"
                "    to=(1, 0),\n"
                "    duration=1,\n"
                ")\n",
                encoding="utf-8",
            )
            scene = _load_scene(source)
            info = get_preview_source(scene)
            self.assertIsNotNone(info)
            assert info is not None
            marker = scene._require_registered(scene.items[0])
            self.assertEqual(info.primary_name(marker.object_id), "marker")
            span = info.clip_source(scene._timeline.clips[0])
            self.assertIsNotNone(span)
            assert span is not None
            self.assertEqual((span.start_line, span.end_line), (4, 7))

            reloaded = reload_preview_scene(scene)
            reloaded_info = get_preview_source(reloaded)
            self.assertIsNotNone(reloaded_info)
            assert reloaded_info is not None
            reloaded_marker = reloaded._require_registered(reloaded.items[0])
            self.assertEqual(reloaded_info.primary_name(reloaded_marker.object_id), "marker")
            self.assertIsNotNone(reloaded_info.clip_source(reloaded._timeline.clips[0]))

    def test_cli_renders_scene_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "hello.py"
            output = root / "frame.png"
            source.write_text(
                "from zanim import Canvas, Circle, Scene\n"
                "scene = Scene(canvas=Canvas(80, 48, 12), fps=10)\n"
                "item = scene.add(Circle(1))\n"
                "item.move(to=(1, 0), duration=1)\n",
                encoding="utf-8",
            )
            with redirect_stdout(StringIO()):
                status = cli_main(["render", str(source), "--time", "0.5", "-o", str(output)])
            self.assertEqual(status, 0)
            self.assertTrue(output.is_file())

    def test_cli_scene_can_import_sibling_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "helper.py").write_text("RADIUS = 0.6\n", encoding="utf-8")
            source = root / "scene_file.py"
            output = root / "sibling.png"
            source.write_text(
                "from helper import RADIUS\n"
                "from zanim import Canvas, Circle, Scene\n"
                "def build_scene():\n"
                "    scene = Scene(canvas=Canvas(80, 48, 12))\n"
                "    scene.add(Circle(RADIUS))\n"
                "    return scene\n",
                encoding="utf-8",
            )
            with redirect_stdout(StringIO()):
                status = cli_main(["render", str(source), "-o", str(output)])
            self.assertEqual(status, 0)
            self.assertTrue(output.is_file())

    def test_cli_scene_can_use_package_relative_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "lesson"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "helper.py").write_text("RADIUS = 0.55\n", encoding="utf-8")
            source = package / "scene_file.py"
            output = root / "package.png"
            source.write_text(
                "from .helper import RADIUS\n"
                "from zanim import Canvas, Circle, Scene\n"
                "def build_scene():\n"
                "    scene = Scene(canvas=Canvas(80, 48, 12))\n"
                "    scene.add(Circle(RADIUS))\n"
                "    return scene\n",
                encoding="utf-8",
            )
            with redirect_stdout(StringIO()):
                status = cli_main(["render", str(source), "-o", str(output)])
            self.assertEqual(status, 0)
            self.assertTrue(output.is_file())

    def test_missing_typst_has_product_error(self):
        from zanim import typst as typst_module

        with patch.object(typst_module, "_ROOT", Path("/definitely/missing")):
            with patch("zanim.typst.shutil.which", return_value=None):
                with self.assertRaisesRegex(ZanimError, "Typst is required"):
                    typst_module._typst_executable()

    def test_missing_ffmpeg_has_product_error(self):
        ffmpeg_path.cache_clear()
        try:
            with patch("zanim.runtime.shutil.which", return_value=None):
                with self.assertRaisesRegex(MediaError, "FFmpeg was not found"):
                    require_ffmpeg()
        finally:
            ffmpeg_path.cache_clear()

    def test_remote_preview_disables_reload_by_default(self):
        server = PreviewServer(
            _source_scene(),
            host="0.0.0.0",
            port=0,
        ).start(open_browser=False)
        base = f"http://127.0.0.1:{server.port}/"
        try:
            with urlopen(base + "api/meta") as response:
                meta = json.loads(response.read())
            self.assertTrue(meta["source_available"])
            self.assertFalse(meta["reload_available"])

            request = Request(base + "api/reload?t=0.5", method="POST")
            with self.assertRaises(HTTPError) as caught:
                urlopen(request)
            self.assertEqual(caught.exception.code, 403)
            payload = json.loads(caught.exception.read())
            self.assertFalse(payload["ok"])
        finally:
            server.close()

    def test_remote_reload_requires_explicit_opt_in(self):
        server = PreviewServer(
            _source_scene(),
            host="0.0.0.0",
            port=0,
            allow_remote_reload=True,
        )
        try:
            self.assertTrue(server.reload_allowed)
        finally:
            server.close()


if __name__ == "__main__":
    unittest.main()
