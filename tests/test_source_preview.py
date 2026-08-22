from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zanim import Canvas, Circle, Color, Object2D, Scene, Style, Transform2D, preview_source
from zanim.preview import PreviewServer, PreviewSession
from zanim.source import get_preview_source, reload_preview_source




def _write_reload_module(path: Path, *, duration: float) -> None:
    source = (
        "from zanim import Canvas, Circle, Color, Object2D, Scene, Style, Transform2D, preview_source\n\n"
        "@preview_source\n"
        "def build_scene() -> Scene:\n"
        "    scene = Scene(canvas=Canvas(80, 48, 12), fps=10)\n"
        "    marker = Object2D(Circle(1), style=Style(fill=Color(230, 90, 90)))\n"
        "    marker = scene.add(marker)\n"
        f"    marker.transform(to=Transform2D.translation(1, 0), duration={duration!r})\n"
        "    return scene\n"
    )
    path.write_text(source, encoding="utf-8")


@preview_source
def build_source_scene() -> Scene:
    scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
    marker = Object2D(Circle(1), style=Style(fill=Color(230, 90, 90)))
    marker = scene.add(marker)
    marker.transform(to=Transform2D.translation(1, 0), duration=1.0)
    return scene


class PreviewSourceTests(unittest.TestCase):
    def test_decorator_captures_object_name_and_clip_source(self):
        scene = build_source_scene()
        source = get_preview_source(scene)
        self.assertIsNotNone(source)
        assert source is not None
        marker_id = scene.items[0]
        registered = scene._require_registered(marker_id)
        self.assertEqual(source.primary_name(registered.object_id), "marker")

        clip = scene.timeline.clips[0]
        span = source.clip_source(clip)
        self.assertIsNotNone(span)
        assert span is not None
        lines = source.text.splitlines()
        block = "\n".join(lines[span.start_line - 1:span.end_line])
        self.assertIn("marker.transform", block)

    def test_reload_supports_builder_defined_as_main_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.py"
            _write_reload_module(path, duration=1.0)
            namespace = {
                "__name__": "__main__",
                "__file__": str(path),
                "__package__": "",
            }
            exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
            scene = namespace["build_scene"]()
            source = get_preview_source(scene)
            self.assertIsNotNone(source)
            assert source is not None
            self.assertEqual(source.module_name, "__main__")

            _write_reload_module(path, duration=2.0)
            reloaded = reload_preview_source(scene)
            self.assertAlmostEqual(reloaded.duration, 2.0)
            reloaded_source = get_preview_source(reloaded)
            self.assertIsNotNone(reloaded_source)
            assert reloaded_source is not None
            self.assertNotEqual(reloaded_source.module_name, "__main__")

    def test_preview_inspector_exposes_source_without_changing_clip(self):
        scene = build_source_scene()
        session = PreviewSession(scene, hot_cache_mb=1, prefetch_workers=1)
        try:
            info = session.inspect_time(0.5)
            marker = next(item for item in info["objects"] if item["name"] == "marker")
            self.assertEqual(marker["type"], "Object2D")
            self.assertEqual(len(marker["active_clips"]), 1)
            source = marker["active_clips"][0]["source"]
            self.assertIsNotNone(source)
            self.assertEqual(len(info["active_sources"]), 1)
            self.assertEqual(info["active_sources"][0]["name"], "marker")
            self.assertTrue(session.source_document()["available"])
        finally:
            session.close()

    def test_reload_reads_saved_source_and_restores_module_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = "zanim_reload_fixture"
            path = root / f"{name}.py"
            _write_reload_module(path, duration=1.0)
            sys.path.insert(0, str(root))
            try:
                module = importlib.import_module(name)
                scene = module.build_scene()
                self.assertAlmostEqual(scene.duration, 1.0)

                _write_reload_module(path, duration=2.0)
                reloaded = reload_preview_source(scene)
                self.assertAlmostEqual(reloaded.duration, 2.0)
                self.assertIs(sys.modules[name], module)

                path.write_text("def broken(:\n", encoding="utf-8")
                with self.assertRaises(SyntaxError):
                    reload_preview_source(reloaded)
                self.assertIs(sys.modules[name], module)
                self.assertAlmostEqual(reloaded.duration, 2.0)
            finally:
                sys.modules.pop(name, None)
                sys.path.remove(str(root))

    def test_manual_reload_http_preserves_time_and_failure_keeps_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = "zanim_reload_http_fixture"
            path = root / f"{name}.py"
            _write_reload_module(path, duration=1.0)
            sys.path.insert(0, str(root))
            server = None
            try:
                module = importlib.import_module(name)
                server = PreviewServer(
                    module.build_scene(), host="127.0.0.1", port=0,
                    hot_cache_mb=1, cold_cache_mb=1, prefetch_workers=1,
                ).start(open_browser=False)
                old_tempdir = Path(server.session._tempdir.name)
                server.session.raw_time(0.0)
                self.assertTrue(old_tempdir.is_dir())

                _write_reload_module(path, duration=2.0)
                request = Request(server.url + "api/reload?t=0.75", method="POST")
                with urlopen(request) as response:
                    result = json.loads(response.read())
                self.assertTrue(result["ok"])
                self.assertAlmostEqual(result["time"], 0.75)
                self.assertAlmostEqual(server.session.duration, 2.0)
                self.assertFalse(old_tempdir.exists())

                _write_reload_module(path, duration=0.25)
                request = Request(server.url + "api/reload?t=0.75", method="POST")
                with urlopen(request) as response:
                    result = json.loads(response.read())
                self.assertTrue(result["ok"])
                self.assertAlmostEqual(result["time"], 0.25)
                self.assertAlmostEqual(server.session.duration, 0.25)

                path.write_text("def broken(:\n", encoding="utf-8")
                request = Request(server.url + "api/reload?t=0.75", method="POST")
                with self.assertRaises(HTTPError) as caught:
                    urlopen(request)
                payload = json.loads(caught.exception.read())
                self.assertFalse(payload["ok"])
                self.assertIn("SyntaxError", payload["traceback"])
                self.assertAlmostEqual(server.session.duration, 0.25)
            finally:
                if server is not None:
                    server.close()
                sys.modules.pop(name, None)
                sys.path.remove(str(root))

    def test_reload_preserves_package_context_for_relative_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "reload_pkg"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "helper.py").write_text("DURATION = 1.25\n", encoding="utf-8")
            demo = package / "demo.py"
            demo.write_text(
                "from .helper import DURATION\n"
                "from zanim import Canvas, Circle, Object2D, Scene, preview_source\n\n"
                "@preview_source\n"
                "def build_scene():\n"
                "    scene = Scene(canvas=Canvas(80, 48, 12), fps=10)\n"
                "    marker = scene.add(Object2D(Circle(1)))\n"
                "    marker.opacity(to=0.5, duration=DURATION)\n"
                "    return scene\n",
                encoding="utf-8",
            )
            sys.path.insert(0, str(root))
            try:
                module = importlib.import_module("reload_pkg.demo")
                scene = module.build_scene()
                self.assertAlmostEqual(scene.duration, 1.25)
                reloaded = reload_preview_source(scene)
                self.assertAlmostEqual(reloaded.duration, 1.25)
                source = get_preview_source(reloaded)
                self.assertIsNotNone(source)
                assert source is not None
                self.assertEqual(source.package_name, "reload_pkg")
                self.assertIs(sys.modules["reload_pkg.demo"], module)
            finally:
                for name in ("reload_pkg.demo", "reload_pkg.helper", "reload_pkg"):
                    sys.modules.pop(name, None)
                sys.path.remove(str(root))

    def test_reload_rejects_removed_decorator_and_keeps_old_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = "zanim_reload_decorator_fixture"
            path = root / f"{name}.py"
            _write_reload_module(path, duration=1.0)
            sys.path.insert(0, str(root))
            try:
                module = importlib.import_module(name)
                scene = module.build_scene()
                source = path.read_text(encoding="utf-8").replace("@preview_source\n", "")
                path.write_text(source, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "must remain decorated"):
                    reload_preview_source(scene)
                self.assertAlmostEqual(scene.duration, 1.0)
                self.assertIsNotNone(get_preview_source(scene))
            finally:
                sys.modules.pop(name, None)
                sys.path.remove(str(root))

    def test_undecorated_scene_has_no_source_metadata(self):
        scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
        scene.add(Object2D(Circle(1), style=Style(fill=Color(230, 90, 90))))
        session = PreviewSession(scene, hot_cache_mb=1, prefetch_workers=1)
        try:
            self.assertFalse(session.metadata()["source_available"])
            self.assertEqual(session.source_document(), {"available": False})
            item = session.inspect_time(0)["objects"][1]
            self.assertIsNone(item["name"])
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
