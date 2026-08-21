"""Timeline composition: offsets, parallel clips, easing, functions and morphing."""
from __future__ import annotations

from math import pi, sin
from pathlib import Path

from zanim import (
    Canvas, Circle, Color, Easing, Object2D, ObjectInterpolation, Scene, Square,
    StrokeStyle, Style, Text, Transform2D, Vec2,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/showcase/timeline.mp4"
WHITE = Color(238, 242, 250)
BLUE = Color(78, 145, 255)
PINK = Color(245, 92, 145)
GREEN = Color(84, 215, 155)


def outlined(color: Color) -> Style:
    return Style(fill=Color(color.r, color.g, color.b, 80), stroke=StrokeStyle(color, 0.045))


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(1280, 720, 95), fps=60)
    title = Text("One timeline, independent channels", font_size=32, transform=Transform2D.translation(0, 2.7))

    left = Object2D(Circle(0.72), style=outlined(BLUE), transform=Transform2D.translation(-3.2, 0))
    middle = Object2D(Square(1.35), style=outlined(PINK))
    source = Object2D(Circle(0.75), style=outlined(GREEN), transform=Transform2D.translation(3.2, 0))
    target = Object2D(Square(1.45), style=outlined(BLUE), transform=Transform2D.translation(3.2, 0))
    relation = ObjectInterpolation.from_objects(source, target)
    source.opacity = 0.0
    target.opacity = 0.0

    scene.add(title, left, middle, source, target)
    scene.fade_in(title, duration=0.7)

    # One block schedules several clips from the same cursor. ``at`` adds a
    # relative offset without making the author manually manage timestamps.
    with scene.parallel():
        scene.play_transform_function(
            left,
            lambda a: Transform2D.translation(-3.2, 0.55 * sin(4 * pi * a)).rotate(2 * pi * a),
            duration=3.0,
            easing=Easing.LINEAR,
        )
        scene.play_transform(
            middle,
            Transform2D.rotation(pi).scale(1.35),
            duration=1.1,
            easing=Easing.SMOOTHSTEP,
            at=0.35,
        )
        scene.play_style(middle, outlined(GREEN), duration=1.0, at=1.45)

        scene.timeline.add_interpolation(relation, duration=2.2, at=0.5)

    scene.wait(0.35)
    with scene.parallel():
        scene.fade_out(left, duration=0.7)
        scene.fade_out(middle, duration=0.7, at=0.1)
        scene.fade_out(title, duration=0.7, at=0.2)
    return scene


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene()
    print(scene.render_video(OUTPUT, verify_random_access=True))


if __name__ == "__main__":
    main()
