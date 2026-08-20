from __future__ import annotations

import argparse
from math import pi
from pathlib import Path

from zanim import Camera3D, Canvas, Color, Cube3D, Easing, Scene, Text, Transform3D, Vec2, Vec3


def build_scene(*, draft: bool = False) -> Scene:
    canvas = Canvas(960, 540, 75.0) if draft else Canvas(1920, 1080, 150.0)
    scene = Scene(canvas=canvas, fps=30 if draft else 60)
    scene.camera3d = Camera3D(position=Vec3(4.2, 3.0, 5.2), target=Vec3())

    cube = Cube3D(2.5, color=Color(78, 169, 255))
    title = Text("Zanim 3D · rotating cube", font_size=42, color=Color(238, 242, 250))
    title.move_to(Vec2(0.0, 3.05))
    scene.add(cube, title)

    scene.play_transform_function(
        cube,
        lambda a: Transform3D.rotation_y(2.0 * pi * a) @ Transform3D.rotation_x(0.72 * pi * a),
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
        suffix = "rotating_cube_draft.mp4" if args.draft else "rotating_cube.mp4"
        output = Path("media/three_d") / suffix
    scene.render_video(
        output, verify_random_access=True, preset="veryfast", crf=22,
        video_encoder="auto",
    )
    print(output.resolve())


if __name__ == "__main__":
    main()
