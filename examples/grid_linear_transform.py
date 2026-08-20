from __future__ import annotations

import argparse
from pathlib import Path

from zanim import Canvas, Color, Easing, Line, Object2D, Scene, StrokeStyle, Style, Transform2D, Vec2


def build_scene(width: int, height: int, unit_size: float) -> Scene:
    scene = Scene(canvas=Canvas(width=width, height=height, unit_size=unit_size), fps=30)
    lines: list[Object2D] = []
    style = Style(fill=None, stroke=StrokeStyle(Color(90, 110, 145, 120), 0.018))
    axis_style = Style(fill=None, stroke=StrokeStyle(Color(220, 225, 235, 220), 0.028))
    for value in range(-6, 7):
        lines.append(Object2D(Line(Vec2(value, -4), Vec2(value, 4)), style=axis_style if value == 0 else style))
    for value in range(-4, 5):
        lines.append(Object2D(Line(Vec2(-6, value), Vec2(6, value)), style=axis_style if value == 0 else style))
    scene.add(*lines)

    target = Transform2D(xx=1.15, xy=0.7, yx=-0.15, yy=0.75)
    with scene.parallel():
        for line in lines:
            scene.play_transform(line, target, duration=4.0, easing=Easing.SMOOTHSTEP)
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description='Render a linear transformation of a coordinate grid')
    parser.add_argument('--output', type=Path, default=Path('media/linear_grid.mp4'))
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--width', type=int, default=960)
    parser.add_argument('--height', type=int, default=540)
    parser.add_argument('--unit-size', type=float, default=64.0)
    args = parser.parse_args()
    scene = build_scene(args.width, args.height, args.unit_size)
    print(scene.render_video(args.output, fps=args.fps, verify_random_access=True))


if __name__ == '__main__':
    main()
