#!/usr/bin/env bash
set -euo pipefail
zig build test
uv run python -m unittest discover -s tests
zig build -Doptimize=ReleaseFast >/dev/null
uv run python - <<'PY'
import tempfile
from pathlib import Path
from PIL import Image as PILImage
from zanim import Canvas, Circle, Color, Image, Object2D, Scene, Style, Transform2D

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
PY
