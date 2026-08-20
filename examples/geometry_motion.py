from __future__ import annotations

import argparse
from pathlib import Path

from zanim import (
    Canvas, Circle, Color, Easing, Object2D, Rectangle, Scene, Style, Transform2D,
)


def build_scene(width: int, height: int, unit_size: float, duration: float) -> Scene:
    scene = Scene(canvas=Canvas(width=width, height=height, unit_size=unit_size), fps=30)
    rectangle = Object2D(
        Rectangle(2.2, 1.3),
        transform=Transform2D.translation(-2.6, 0.8),
        style=Style(fill=Color(80, 150, 255, 170)),
    )
    circle = Object2D(
        Circle(0.8),
        transform=Transform2D.translation(2.4, -0.6),
        style=Style(fill=Color(255, 150, 90, 170)),
    )
    scene.add(rectangle, circle)
    with scene.parallel():
        scene.play_transform(
            rectangle,
            Transform2D.translation(0.4, 1.2).rotate(0.9).scale(1.35, 0.7),
            duration=duration,
            easing=Easing.SMOOTHSTEP,
        )
        scene.play_transform(
            circle,
            Transform2D.translation(-0.8, -1.0).scale(1.8, 0.65),
            duration=duration,
            easing=Easing.SMOOTHSTEP,
        )
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description='Render a Scene transform example')
    parser.add_argument('--output', type=Path, default=Path('media/geometry_motion.mp4'))
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--duration', type=float, default=4.0)
    parser.add_argument('--width', type=int, default=960)
    parser.add_argument('--height', type=int, default=540)
    parser.add_argument('--unit-size', type=float, default=80.0)
    args = parser.parse_args()

    scene = build_scene(args.width, args.height, args.unit_size, args.duration)
    print(scene.render_video(args.output, fps=args.fps, verify_random_access=True))


if __name__ == '__main__':
    main()
