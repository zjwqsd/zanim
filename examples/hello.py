import tempfile
from pathlib import Path

from zanim import Canvas, Circle, Color, Object2D, Scene, Style


scene = Scene(canvas=Canvas(width=640, height=360, unit_size=80))
scene.add(Object2D(Circle(1.0), style=Style(fill=Color(100, 180, 255), stroke=None)))
with tempfile.TemporaryDirectory(prefix="zanim-hello-") as td:
    scene.render_frame(Path(td) / "hello.png", 0.0)
print("hello render: ok")
