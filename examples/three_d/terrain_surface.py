from __future__ import annotations

import argparse
from math import cos, pi, sin
from pathlib import Path

from zanim import Camera3D, Canvas, Color, Easing, Math, Scene, Surface3D, Text, Transform3D, Vec2, Vec3


def height(x: float, y: float) -> float:
    return 0.75 * sin(x) * cos(y) + 0.18 * sin(2.0 * x + y)


def build_scene(*, draft: bool = False) -> Scene:
    canvas = Canvas(960, 540, 75.0) if draft else Canvas(1920, 1080, 150.0)
    scene = Scene(canvas=canvas, fps=30 if draft else 60)
    scene.camera3d = Camera3D(
        position=Vec3(6.2, 4.6, 6.6), target=Vec3(0.0, 0.0, 0.0), fov_y_degrees=42.0,
    )

    surface = Surface3D(
        height, x_range=(-pi, pi), y_range=(-pi, pi), resolution=(81, 81),
        color=Color(70, 202, 151),
    )
    title = Text("Bivariate function terrain", font_size=40, color=Color(238, 242, 250))
    title.move_to(Vec2(0.0, 3.05))
    formula = Math(r"z = 0.75 sin(x) cos(y) + 0.18 sin(2x + y)", font_size=28)
    formula.move_to(Vec2(0.0, 2.55))
    scene.add(surface, title, formula)

    scene.play_transform_function(
        surface,
        lambda a: Transform3D.rotation_y(0.65 * pi * a),
        duration=8.0,
        easing=Easing.LINEAR,
    )
    return scene


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    scene = build_scene(draft=args.draft)
    if args.output:
        output = Path(args.output)
    else:
        suffix = "terrain_surface_draft.mp4" if args.draft else "terrain_surface.mp4"
        output = Path("media/three_d") / suffix
    scene.render_video(
        output, verify_random_access=True, preset="veryfast", crf=22,
        video_encoder="auto",
    )
    print(output.resolve())


if __name__ == "__main__":
    main()
