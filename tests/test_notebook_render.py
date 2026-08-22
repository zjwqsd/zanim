from __future__ import annotations

import unittest
from unittest.mock import patch

from zanim import Canvas, Circle, Scene
from zanim.notebook import NotebookImage, NotebookVideo


class NotebookRenderTests(unittest.TestCase):
    def test_render_without_path_is_rejected_outside_notebook(self):
        scene = Scene()
        with patch("zanim.notebook.is_notebook", return_value=False):
            with self.assertRaisesRegex(ValueError, "only available in a Jupyter notebook"):
                scene.render()

    def test_static_notebook_render_returns_inline_png(self):
        scene = Scene(canvas=Canvas(80, 48, 12))
        scene.add(Circle(1))
        with patch("zanim.notebook.is_notebook", return_value=True):
            result = scene.render()
        self.assertIsInstance(result, NotebookImage)
        self.assertTrue(result.data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(result._repr_png_(), result.data)

    def test_time_notebook_render_returns_inline_png(self):
        scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
        scene.add(Circle(1))
        scene.wait(1)
        with patch("zanim.notebook.is_notebook", return_value=True):
            result = scene.render(time=0.5)
        self.assertIsInstance(result, NotebookImage)

    def test_animated_notebook_render_returns_inline_mp4(self):
        scene = Scene(canvas=Canvas(80, 48, 12), fps=10)
        scene.add(Circle(1))
        scene.wait(0.2)
        with patch("zanim.notebook.is_notebook", return_value=True):
            result = scene.render()
        self.assertIsInstance(result, NotebookVideo)
        self.assertIn(b"ftyp", result.data[:64])
        html = result._repr_html_()
        self.assertIn("video/mp4;base64,", html)


if __name__ == "__main__":
    unittest.main()
