"""Lesson 04: timeline composition, offsets, easing and interpolation."""

from __future__ import annotations

from math import sin

from zanim import (
    BLUE,
    DOWN,
    GREEN,
    PI,
    PINK,
    TAU,
    TOP,
    Canvas,
    Circle,
    Color,
    Easing,
    Row,
    Scene,
    Square,
    Style,
    Text,
    Vec2,
    affine2d,
)


def outlined(color: Color) -> Style:
    return Style.paint(color.with_alpha(80), color, 0.045)


scene = Scene(canvas=Canvas(1280, 720, 95), fps=60)
title = Text("One timeline, independent channels", font_size=32, opacity=0)
left = Circle(0.72, style=outlined(BLUE))
middle = Square(1.35, style=outlined(PINK))
source = Circle(0.75, style=outlined(GREEN))
target = Square(1.45, style=outlined(BLUE))

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
            position=(left_origin.x, left_origin.y + 0.55 * sin(4 * PI * a)),
            rotation=TAU * a,
        ),
        duration=3.0,
        easing=Easing.LINEAR,
    )
    middle.affine(position=middle.center, rotation=PI, scale=1.35, duration=1.1, at=0.35)
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

scene.preview()
