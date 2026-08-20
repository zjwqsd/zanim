#!/usr/bin/env bash
set -euo pipefail
zig build test
uv run python -m unittest discover -s tests
zig build -Doptimize=ReleaseFast >/dev/null
uv run python - <<'PY'
import tempfile
from pathlib import Path
from zanim import Canvas, Circle, Color, Object2D, Scene, Style

with tempfile.TemporaryDirectory(prefix='zanim-check-') as tmp:
    scene = Scene(canvas=Canvas(width=320, height=180, unit_size=60))
    scene.add(Object2D(Circle(0.8), style=Style(fill=Color(100, 180, 255), stroke=None)))
    scene.render_frame(Path(tmp) / 'smoke.png', 0.0)
PY
