#!/usr/bin/env bash
set -euo pipefail
zig build test
zig build -Doptimize=ReleaseFast >/dev/null
uv run python -m unittest discover -s tests
uv run python - <<'PY'
import tempfile
from pathlib import Path
from PIL import Image as PILImage
from zanim import Canvas, Circle, Color, Cube3D, Image, Object2D, Scene, Style, Transform2D, Transform3D
from zanim.render.frame import render_snapshot_rgba

with tempfile.TemporaryDirectory(prefix='zanim-check-') as tmp:
    tmp = Path(tmp)
    image_path = tmp / 'pixel.png'
    PILImage.new('RGBA', (8, 6), (240, 70, 80, 210)).save(image_path)
    scene = Scene(canvas=Canvas(width=320, height=180, unit_size=60))
    scene.add(
        Object2D(Circle(0.8), style=Style(fill=Color(100, 180, 255), stroke=None), z_index=0),
        Image(image_path, width=1.5, transform=Transform2D.rotation(0.2), z_index=1),
        Object2D(Circle(0.18), style=Style(fill=Color(255, 240, 100), stroke=None), z_index=2),
    )
    scene.render_frame(tmp / 'smoke.png', 0.0)

    scene3d = Scene(canvas=Canvas(width=160, height=90, unit_size=30))
    opaque = Cube3D(0.65, transform=Transform3D.translation(-0.65, 0.0, 0.0))
    translucent = Cube3D(
        0.65, color=Color(180, 210, 255),
        transform=Transform3D.translation(0.65, 0.0, 0.0),
    )
    translucent.opacity = 0.35
    scene3d.add(opaque, translucent)
    smoke3d = tmp / 'smoke3d.png'
    scene3d.render_frame(smoke3d, 0.0)
    image3d = PILImage.open(smoke3d).convert('RGB')
    assert any(pixel != (14, 17, 24) for pixel in image3d.get_flattened_data())

    rgba = bytearray(scene3d.width * scene3d.height * 4)
    render_snapshot_rgba(rgba, scene3d.evaluate(0.0), scene3d.canvas)
    alpha = rgba[3::4]
    assert any(0 < value < 255 for value in alpha)
    assert any(value == 255 for value in alpha)
PY
