import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from urllib.request import urlopen

from zanim import Canvas, Circle, Object2D, Scene, Transform2D
from zanim.preview import PreviewServer, PreviewSession, _CompressedFrameCache


class PreviewSessionTests(unittest.TestCase):
    def make_scene(self, *, fps=10, duration=2.0):
        scene = Scene(canvas=Canvas(80, 48, 12), fps=fps)
        obj = Object2D(Circle(1))
        scene.add(obj)
        scene.transform(obj, to=Transform2D.translation(2, 0), duration=duration)
        return scene, obj

    def test_prefetch_plan_is_forward_from_selection(self):
        scene, _ = self.make_scene(fps=10, duration=4)
        session = PreviewSession(
            scene, hot_cache_mb=0, prefetch_seconds=0.5, prefetch_workers=1
        )
        try:
            plan = session.prefetch_plan(12)
            self.assertTrue(plan)
            self.assertEqual(plan[0], 13)
            self.assertEqual(plan, tuple(sorted(plan)))
            self.assertTrue(all(frame > 12 for frame in plan))
        finally:
            session.close()

    def test_raw_frame_cache_avoids_duplicate_evaluate(self):
        scene, _ = self.make_scene()
        session = PreviewSession(scene, hot_cache_mb=0, prefetch_workers=1)
        calls = []
        original = Scene.evaluate

        def evaluate(scene_self, time):
            calls.append(time)
            return original(scene_self, time)

        try:
            with patch.object(Scene, "evaluate", evaluate):
                first = session.raw_frame(4)
                second = session.raw_frame(4)
            self.assertEqual(first, second)
            self.assertEqual(calls, [0.4])
            self.assertEqual(session.cache_state()["stats"]["renders"], 1)
            self.assertEqual(session.cache_state()["stats"]["hot_hits"], 1)
        finally:
            session.close()

    def test_inspector_reports_active_clip_and_current_state(self):
        scene, _ = self.make_scene()
        session = PreviewSession(scene, hot_cache_mb=0, prefetch_workers=1)
        try:
            info = session.inspect(5)
            obj = next(item for item in info["objects"] if item["id"] == 1)
            self.assertTrue(obj["alive"])
            self.assertEqual(obj["type"], "Object2D")
            self.assertEqual(obj["active_clips"][0]["type"], "TransformClip")
            self.assertAlmostEqual(obj["active_clips"][0]["progress"], 0.25)
            self.assertAlmostEqual(obj["state"]["render_transform"]["tx"], 0.3125)
        finally:
            session.close()


    def test_exact_time_is_not_quantized_to_nearest_frame(self):
        scene, _ = self.make_scene(fps=10, duration=2.0)
        session = PreviewSession(scene, hot_cache_mb=0, prefetch_workers=1)
        try:
            exact = session.inspect_time(0.735)
            obj = next(item for item in exact["objects"] if item["id"] == 1)
            expected_alpha = 0.735 / 2.0
            expected_eased = expected_alpha * expected_alpha * (3.0 - 2.0 * expected_alpha)
            self.assertAlmostEqual(exact["time"], 0.735)
            self.assertAlmostEqual(obj["state"]["render_transform"]["tx"], 2.0 * expected_eased)
            nearest = session.inspect(7)
            nearest_obj = next(item for item in nearest["objects"] if item["id"] == 1)
            self.assertNotAlmostEqual(
                obj["state"]["render_transform"]["tx"],
                nearest_obj["state"]["render_transform"]["tx"],
            )
        finally:
            session.close()

    def test_exact_range_video_reuses_cached_samples(self):
        scene, _ = self.make_scene(fps=10, duration=1.0)
        session = PreviewSession(scene, hot_cache_mb=0, prefetch_workers=1)
        try:
            for sample_time in (0.13, 0.23, 0.33, 0.43):
                session.raw_time(sample_time)
            before = session.cache_state()["stats"]["renders"]
            output = session.export_video_time(0.13, 0.53)
            after = session.cache_state()["stats"]["renders"]
            self.assertTrue(output.is_file())
            self.assertEqual(before, after)
            self.assertEqual(output, session.export_video_time(0.13, 0.53))
        finally:
            session.close()

    def test_cold_cache_prevents_reraster_after_hot_eviction(self):
        scene, _ = self.make_scene(fps=10, duration=1.0)
        session = PreviewSession(scene, hot_cache_mb=0, prefetch_workers=1)
        calls = []
        original = Scene.evaluate

        def evaluate(scene_self, time):
            calls.append(time)
            return original(scene_self, time)

        try:
            with patch.object(Scene, "evaluate", evaluate):
                first = session.raw_frame(0)
                session.raw_frame(1)
                restored = session.raw_frame(0)
            self.assertEqual(first, restored)
            self.assertEqual(calls, [0.0, 0.1])
            state = session.cache_state()
            self.assertEqual(state["stats"]["renders"], 2)
            self.assertEqual(state["stats"]["cold_hits"], 1)
            self.assertEqual(state["cached_ranges"], [[0, 1]])
            self.assertEqual(state["hot_entries"], 1)
            self.assertLess(state["cold_bytes"], state["cold_raw_equivalent"])
        finally:
            session.close()

    def test_full_second_pass_uses_cold_cache_without_new_raster(self):
        scene, _ = self.make_scene(fps=10, duration=1.0)
        session = PreviewSession(scene, hot_cache_mb=0, prefetch_workers=1)
        try:
            for frame in range(session.frame_count):
                session.raw_frame(frame)
            first_pass = session.cache_state()["stats"]["renders"]
            for frame in range(session.frame_count):
                session.raw_frame(frame)
            state = session.cache_state()
            self.assertEqual(first_pass, session.frame_count)
            self.assertEqual(state["stats"]["renders"], first_pass)
            self.assertGreaterEqual(state["stats"]["cold_hits"], session.frame_count - 1)
            self.assertEqual(state["cached_ranges"], [[0, session.frame_count - 1]])
        finally:
            session.close()

    def test_raw_http_endpoint_returns_cached_rgb0_without_conversion(self):
        scene, _ = self.make_scene(fps=10, duration=1.0)
        server = PreviewServer(
            scene, host="127.0.0.1", port=0, hot_cache_mb=0, prefetch_workers=1
        ).start(open_browser=False)
        try:
            t = 0.35
            expected = server.session.raw_time(t)
            with urlopen(server.url + f"api/frame/raw?t={t}") as response:
                actual = response.read()
                self.assertEqual(response.headers["Content-Type"], "application/octet-stream")
                self.assertEqual(response.headers["X-Zanim-Pixel-Format"], "rgb0")
                self.assertEqual(int(response.headers["Content-Length"]), len(expected))
            self.assertEqual(actual, expected)
            with urlopen(server.url) as response:
                html = response.read()
            self.assertIn(b'<canvas id="preview"', html)
            self.assertIn(b'/api/frame/raw', html)
        finally:
            server.close()

    def test_video_export_reuses_cached_raw_frames(self):
        scene, _ = self.make_scene(fps=5, duration=1.0)
        session = PreviewSession(scene, hot_cache_mb=0, prefetch_workers=1)
        try:
            for frame in range(scene.fps):
                session.raw_frame(frame)
            before = session.cache_state()["stats"]["renders"]
            output = session.export_video(0, scene.fps)
            after = session.cache_state()["stats"]["renders"]
            self.assertTrue(output.is_file())
            self.assertEqual(before, after)
            self.assertGreater(session.cache_state()["stats"]["hot_hits"] + session.cache_state()["stats"]["cold_hits"], 0)
            self.assertEqual(output, session.export_video(0, scene.fps))
        finally:
            session.close()

    def test_partial_cache_uses_baseline_video_path(self):
        scene, _ = self.make_scene(fps=5, duration=1.0)
        session = PreviewSession(scene, hot_cache_mb=0, prefetch_workers=1)
        calls = []

        def fake_render(scene_self, path, **kwargs):
            calls.append(kwargs)
            Path(path).write_bytes(b"video")
            return Path(path)

        try:
            session.raw_frame(0)
            with patch.object(Scene, "render_video", autospec=True, side_effect=fake_render):
                session.export_video_time(0.0, 1.0)
            self.assertEqual(len(calls), 1)
            self.assertNotIn("_frame_provider", calls[0])
        finally:
            session.close()

    def test_fully_cached_export_uses_frame_provider(self):
        scene, _ = self.make_scene(fps=5, duration=1.0)
        session = PreviewSession(scene, hot_cache_mb=0, prefetch_workers=1)
        calls = []

        def fake_render(scene_self, path, **kwargs):
            calls.append(kwargs)
            Path(path).write_bytes(b"video")
            return Path(path)

        try:
            for frame in range(session.frame_count):
                session.raw_frame(frame)
            with patch.object(Scene, "render_video", autospec=True, side_effect=fake_render):
                session.export_video_time(0.0, 1.0)
            self.assertEqual(len(calls), 1)
            self.assertIn("_frame_provider", calls[0])
        finally:
            session.close()

    def test_cold_cache_has_hard_disk_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frames.zcache"
            cache = _CompressedFrameCache(path, max_bytes=128)
            try:
                self.assertTrue(cache.put(0, bytes(1024)))
                self.assertFalse(cache.put(1, os.urandom(1024)))
                self.assertTrue(cache.is_full)
                self.assertLessEqual(cache.size_bytes, 128)
                self.assertLessEqual(path.stat().st_size, 128)
                self.assertTrue(cache.contains(0))
                self.assertFalse(cache.contains(1))
            finally:
                cache.close()


if __name__ == "__main__":
    unittest.main()
