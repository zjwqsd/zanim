from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zanim import Canvas, Circle, Color, Group, Scene, Square, Style
from zanim.ir import scene_to_ir
from zanim.preview import PreviewServer
from zanim.source import get_preview_source, preview_source, reload_preview_source


def _write_reload_module(path: Path, *, duration: float) -> None:
    source = (
        "from zanim import Canvas, Circle, Scene, Style, Color, Transform2D\n"
        "from zanim.source import preview_source\n\n"
        "@preview_source\n"
        "def build_scene() -> Scene:\n"
        "    scene = Scene(canvas=Canvas(80, 48, 12), fps=10)\n"
        "    marker = Circle(1, style=Style(fill=Color(230, 90, 90)))\n"
        "    marker = scene.add(marker)\n"
        f"    marker.transform(to=Transform2D.translation(1, 0), duration={duration!r})\n"
        "    return scene\n"
    )
    path.write_text(source, encoding="utf-8")


@preview_source
def build_source_scene() -> Scene:
    scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
    marker = Circle(1, style=Style(fill=Color(230, 90, 90)))
    marker = scene.add(marker)
    marker.move(to=(1, 0), duration=1.0)
    return scene


class PreviewSourceTests(unittest.TestCase):
    def test_decorator_captures_object_name_without_source_locations(self):
        scene = build_source_scene()
        source = get_preview_source(scene)
        self.assertIsNotNone(source)
        assert source is not None
        marker = scene.items[0]
        registered = scene._require_registered(marker)
        self.assertEqual(source.primary_name(registered.object_id), "marker")
        self.assertFalse(hasattr(source, "text"))
        self.assertFalse(hasattr(source, "clip_source"))
        clip = scene._timeline.clips[0]
        self.assertEqual(scene._timeline._event_actions[id(clip)], "move")

    def test_scene_ir_carries_timeline_debug_metadata(self):
        scene = build_source_scene()
        ir = scene_to_ir(scene, include_debug=True)
        marker_id = scene._require_registered(scene.items[0]).object_id
        self.assertEqual(ir["debug"]["objects"][str(marker_id)]["names"], ["marker"])
        self.assertEqual(ir["debug"]["objects"][str(marker_id)]["type"], "Circle")
        events = ir["debug"]["timeline"]
        self.assertEqual(events[0]["type"], "point")
        self.assertEqual(events[0]["label"], "marker-add")
        self.assertEqual(events[1]["type"], "span")
        self.assertEqual(events[1]["label"], "marker-move")
        self.assertEqual(events[1]["start"], 0.0)
        self.assertEqual(events[1]["duration"], 1.0)

        lean = scene_to_ir(scene)
        self.assertNotIn("debug", lean)

    def test_reload_supports_builder_defined_as_main_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.py"
            _write_reload_module(path, duration=1.0)
            namespace = {"__name__": "__main__", "__file__": str(path), "__package__": ""}
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

    def test_web_preview_reload_preserves_time_revision_and_old_scene_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = "zanim_reload_http_fixture"
            path = root / f"{name}.py"
            _write_reload_module(path, duration=1.0)
            sys.path.insert(0, str(root))
            server = None
            try:
                module = importlib.import_module(name)
                server = PreviewServer(module.build_scene(), host="127.0.0.1", port=0).start(
                    open_browser=False
                )
                with urlopen(server.url + "api/ir") as response:
                    first = json.loads(response.read())
                self.assertEqual(first["meta"]["preview_revision"], 1)

                _write_reload_module(path, duration=2.0)
                with urlopen(Request(server.url + "api/reload?t=0.75", method="POST")) as response:
                    result = json.loads(response.read())
                self.assertEqual(result["revision"], 2)
                self.assertAlmostEqual(result["time"], 0.75)
                self.assertAlmostEqual(server.scene.duration, 2.0)
                with urlopen(server.url + "api/ir") as response:
                    second = json.loads(response.read())
                self.assertEqual(second["meta"]["preview_revision"], 2)
                self.assertAlmostEqual(second["duration"], 2.0)

                _write_reload_module(path, duration=0.25)
                with urlopen(Request(server.url + "api/reload?t=0.75", method="POST")) as response:
                    result = json.loads(response.read())
                self.assertAlmostEqual(result["time"], 0.25)
                self.assertAlmostEqual(server.scene.duration, 0.25)

                path.write_text("def broken(:\n", encoding="utf-8")
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(server.url + "api/reload?t=0.1", method="POST"))
                payload = json.loads(caught.exception.read())
                self.assertFalse(payload["ok"])
                self.assertIn("SyntaxError", payload["traceback"])
                self.assertAlmostEqual(server.scene.duration, 0.25)
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
                "from zanim import Canvas, Circle, Scene\n"
                "from zanim.source import preview_source\n\n"
                "@preview_source\n"
                "def build_scene():\n"
                "    scene = Scene(canvas=Canvas(80, 48, 12), fps=10)\n"
                "    marker = scene.add(Circle(1))\n"
                "    marker.opacity(to=0.5, duration=DURATION)\n"
                "    return scene\n",
                encoding="utf-8",
            )
            sys.path.insert(0, str(root))
            try:
                module = importlib.import_module("reload_pkg.demo")
                scene = module.build_scene()
                reloaded = reload_preview_source(scene)
                self.assertAlmostEqual(reloaded.duration, 1.25)
                source = get_preview_source(reloaded)
                self.assertIsNotNone(source)
                assert source is not None
                self.assertEqual(source.package_name, "reload_pkg")
                self.assertIs(sys.modules["reload_pkg.demo"], module)
            finally:
                for module_name in ("reload_pkg.demo", "reload_pkg.helper", "reload_pkg"):
                    sys.modules.pop(module_name, None)
                sys.path.remove(str(root))

    def test_reload_can_drop_optional_decorator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = "zanim_reload_decorator_fixture"
            path = root / f"{name}.py"
            _write_reload_module(path, duration=1.0)
            sys.path.insert(0, str(root))
            try:
                module = importlib.import_module(name)
                scene = module.build_scene()
                path.write_text(
                    path.read_text(encoding="utf-8").replace("@preview_source\n", ""),
                    encoding="utf-8",
                )
                reloaded = reload_preview_source(scene)
                info = get_preview_source(reloaded)
                self.assertIsNotNone(info)
                assert info is not None
                self.assertTrue(
                    all(
                        id(c) in reloaded._timeline._event_actions for c in reloaded._timeline.clips
                    )
                )
            finally:
                sys.modules.pop(name, None)
                sys.path.remove(str(root))

    def test_timeline_debug_preserves_object_hierarchy_and_effective_lifetimes(self):
        scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
        group = Group([Square(1), Circle(0.5)])
        group = scene.add(group)
        scene.wait(0.5)
        scene.remove(group)
        ir = scene_to_ir(scene, include_debug=True)

        records = {int(record["id"]): record for record in ir["objects"]}
        child_ids = [
            object_id for object_id, record in records.items() if record.get("parent") == 1
        ]
        self.assertEqual(child_ids, [2, 3])
        events = ir["debug"]["timeline"]
        for object_id in (1, 2, 3):
            removes = [
                event
                for event in events
                if event["action"] == "remove" and event["targets"] == [object_id]
            ]
            self.assertEqual(len(removes), 1)
            self.assertEqual(removes[0]["time"], 0.5)

    def test_replace_event_targets_both_objects(self):
        scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
        source = scene.add(Square(1))
        scene.wait(0.25)
        scene.replace(source, Circle(1), duration=0.5)
        events = scene_to_ir(scene, include_debug=True)["debug"]["timeline"]
        replace = next(event for event in events if event["action"] == "replace")
        self.assertEqual(replace["targets"], [1, 2])
        self.assertEqual(replace["start"], 0.25)
        self.assertEqual(replace["duration"], 0.5)

    def test_undecorated_scene_still_has_timeline_with_fallback_names(self):
        scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
        scene.add(Circle(1, style=Style(fill=Color(230, 90, 90))))
        ir = scene_to_ir(scene, include_debug=True)
        self.assertEqual(ir["debug"]["timeline"][0]["label"], "Circle#1-add")
        self.assertNotIn("source", ir["debug"])
        server = PreviewServer(scene, host="127.0.0.1", port=0).start(open_browser=False)
        try:
            with self.assertRaises(HTTPError) as caught:
                urlopen(server.url + "api/source")
            self.assertEqual(caught.exception.code, 404)
        finally:
            server.close()


if __name__ == "__main__":
    unittest.main()
