"""Lesson 10: offscreen Scene rendering, alpha masks and raster composition."""

from __future__ import annotations

from math import sin

from zanim import (
    BLUE,
    GREEN,
    MUTED,
    ORANGE,
    PI,
    TAU,
    TOP,
    WHITE,
    Canvas,
    Circle,
    Group,
    Rectangle,
    Scene,
    Square,
    Text,
    Vec2,
    affine2d,
)
from zanim.raster import AlphaMaskSource, RasterObject2D, SceneRasterSource

DURATION = 4.0


def content_scene() -> Scene:
    scene = Scene(canvas=Canvas(480, 320, 70), fps=60)
    square = Square(1.35, fill=BLUE.with_alpha(225), stroke=WHITE)
    circle = Circle(0.82, fill=ORANGE.with_alpha(225), stroke=WHITE)
    bar = Rectangle(3.8, 0.35, fill=GREEN.with_alpha(210))
    square.transform = affine2d(position=(-1.25, 0.45), rotation=-0.2)
    circle.transform = affine2d(position=(1.15, -0.35))
    bar.transform = affine2d(position=(0, -1.35), rotation=0.12)
    group = scene.add(Group([square, circle, bar]))
    group.transform_function(
        lambda a: affine2d(rotation=0.8 * PI * a, scale=1.0 + 0.08 * a),
        duration=DURATION,
    )
    return scene


def mask_scene() -> Scene:
    scene = Scene(canvas=Canvas(480, 320, 70), fps=60)
    aperture = Circle(1.25, fill=WHITE, transform=affine2d(position=(-1.75, 0), scale=0.8))
    aperture = scene.add(aperture)
    aperture.transform_function(
        lambda a: affine2d(
            position=(-1.75 + 3.5 * a, 0.35 * sin(TAU * a)),
            scale=0.8 + 0.55 * sin(PI * a),
        ),
        duration=DURATION,
    )
    return scene


scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)
title = Text("A Scene can become raster data for another Scene", font_size=34)
subtitle = Text(
    "content Scene + alpha-mask Scene → AlphaMaskSource → RasterObject2D",
    font_size=20,
    color=MUTED,
)
title.place(anchor=TOP, at=scene.frame.top + Vec2(0, -0.28))
subtitle.place(anchor=TOP, at=title.anchor(TOP) + Vec2(0, -0.55))

# Each SceneRasterSource evaluates its child Scene at the requested absolute
# source time. The final masked source is still just a random-access source.
content = content_scene()
mask = mask_scene()
content_view = RasterObject2D(
    SceneRasterSource(content),
    width=3.7,
    transform=affine2d(position=(-4.25, -0.55)),
)
mask_view = RasterObject2D(
    SceneRasterSource(mask),
    width=3.7,
    transform=affine2d(position=(0.0, -0.55)),
)
result = RasterObject2D(
    AlphaMaskSource(
        SceneRasterSource(content_scene()),
        SceneRasterSource(mask_scene()),
        feather=lambda t: 1.5 + 2.0 * (0.5 + 0.5 * sin(PI * t / DURATION)),
    ),
    width=3.7,
    transform=affine2d(position=(4.25, -0.55)),
)

labels = [
    Text("content", font_size=21, color=MUTED),
    Text("mask alpha", font_size=21, color=MUTED),
    Text("result", font_size=21, color=MUTED),
]
for x, label in zip((-4.25, 0.0, 4.25), labels):
    label.place(anchor=TOP, at=Vec2(x, 1.9))

scene.add(title, subtitle, *labels)
content_view, mask_view, result = scene.add(content_view, mask_view, result)
with scene.parallel(duration=DURATION):
    content_view.media()
    mask_view.media()
    result.media()
scene.wait(0.35)

scene.preview()
