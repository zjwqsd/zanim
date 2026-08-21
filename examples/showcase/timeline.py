"""Timeline composition: offsets, parallel clips, easing, functions and morphing."""
from __future__ import annotations

from math import pi, sin
from pathlib import Path

from zanim import (
    Canvas, Circle, Color, DOWN, Easing, Object2D, Row, Scene,
    Square, Style, TOP, Text, Vec2, affine2d,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/showcase/timeline.mp4"
WHITE = Color(238, 242, 250)
BLUE = Color(78, 145, 255)
PINK = Color(245, 92, 145)
GREEN = Color(84, 215, 155)


def outlined(color: Color) -> Style:
    return Style.paint(color.with_alpha(80), color, 0.045)


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(1280, 720, 95), fps=60)
    title = Text("One timeline, independent channels", font_size=32, opacity=0)
    left = Object2D(Circle(0.72), style=outlined(BLUE))
    middle = Object2D(Square(1.35), style=outlined(PINK))
    source = Object2D(Circle(0.75), style=outlined(GREEN))
    target = Object2D(Square(1.45), style=outlined(BLUE))

    header = scene.frame.top_region(height=1.2)
    title.place(anchor=TOP, at=header.top + 0.25 * DOWN)
    Row(gap=0.85, at=Vec2()).place(left, middle, source, target)
    left_origin = left.center

    title, left, middle, source, target = scene.add(title, left, middle, source, target)
    title.fade_in(duration=0.7)

    # One block schedules several clips from the same cursor. ``at`` adds a
    # relative offset without making the author manually manage timestamps.
    with scene.parallel():
        left.transform_function(
            lambda a: affine2d(
                to=(left_origin.x, left_origin.y + 0.55 * sin(4 * pi * a)),
                rotation=2 * pi * a,
            ),
            duration=3.0,
            easing=Easing.LINEAR,
        )
        middle.affine(
            to=middle.center, rotation=pi, scale=1.35, duration=1.1, at=0.35
        )
        middle.style(to=outlined(GREEN), duration=1.0, at=1.45)

        # Pure relation: source and target remain visible and unchanged while
        # a third transient interpolation is rendered between them.
        scene.interpolate(source, target, duration=2.2, at=0.5)

    scene.wait(0.35)
    with scene.parallel(duration=0.7):
        left.fade_out()
        middle.fade_out(at=0.1)
        title.fade_out(at=0.2)
        source.fade_out(at=0.2)
        target.fade_out(at=0.2)
    return scene


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene()
    print(scene.render_video(OUTPUT, verify_random_access=True))


if __name__ == "__main__":
    main()
