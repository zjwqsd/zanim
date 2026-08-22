"""Lesson 01: core 2D authoring — declare, layout, add, animate, inspect."""

from __future__ import annotations

from zanim import (
    BLUE,
    BOTTOM,
    DOWN,
    GREEN,
    ORANGE,
    TOP,
    UP,
    WORLD,
    Arrow,
    Canvas,
    Circle,
    Color,
    Dot,
    Group,
    Math,
    NumberLine,
    Row,
    Scene,
    Square,
    Text,
    Vec2,
)

scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)

# Declare: visual state only. Position is not hidden in constructors.
title = Text("Objects compose like values", font_size=34, opacity=0)
subtitle = Math(
    r'"Scene" = "objects" + "timeline"',
    font_size=28,
    color=Color(170, 185, 215),
    opacity=0,
)
square = Square(1.25, fill=BLUE.with_alpha(185), stroke=Color(220, 232, 255), trim=0)
circle = Circle(0.68, fill=ORANGE.with_alpha(185), stroke=Color(220, 232, 255), trim=0)
dot = Dot(radius=0.11, color=Color(255, 227, 112), opacity=0, z_index=5)
number_line = NumberLine((-4, 4), length=8.0, tick_step=1.0, z_index=-2)
arrow = Arrow(Vec2(-3.2, 0), Vec2(3.2, 0), color=GREEN, z_index=1)
shapes = Group([square, circle, dot])
stage = Group([number_line, shapes, arrow])

# Layout: one-time authored placement before anything enters the timeline.
header = scene.frame.top_region(height=1.35)
content = scene.frame.inset(0.6).below(header, gap=0.2)
title.place(anchor=TOP, at=header.top + 0.25 * DOWN)
subtitle.place(anchor=TOP, at=title.anchor(BOTTOM) + 0.14 * DOWN)
Row(gap=0.7, at=content.center + 0.85 * UP).place(*shapes.children)
number_line.place(anchor=BOTTOM, at=content.bottom + 1.2 * UP)
arrow.place(anchor=BOTTOM, at=content.bottom + 2.05 * UP)

# Animate: add() crosses the lifetime boundary and returns bound handles.
stage, title, subtitle = scene.add(stage, title, subtitle)
_, shapes, arrow = stage.children
square, circle, dot = shapes.children

with scene.parallel():
    title.fade_in(duration=0.8)
    subtitle.fade_in(duration=0.9, at=0.15)
    square.create(duration=1.2)
    circle.create(duration=1.2, at=0.15)
    dot.fade_in(duration=0.6, at=0.7)

# A parallel block can supply one shared default duration. Explicit per-clip
# duration= still overrides it; frame semantics remain explicit.
with scene.parallel(duration=1.6):
    shapes.move(by=(0.8, 0.25), frame=WORLD)
    square.paint(
        fill=GREEN.with_alpha(205),
        stroke=Color(220, 255, 240),
        stroke_width=0.06,
    )
    arrow.move(by=(0.15, 0.1), frame=WORLD)

# Rotation and scale still require an explicit frame or world-space pivot.
shapes.rotate(by=0.18, about=shapes.center, duration=0.8)
shapes.scale(by=1.08, about=shapes.center, duration=0.6)

scene.camera.affine(position=(-0.3, -0.08), scale=1.15, duration=1.3)
stage.fade_out(duration=0.9)
scene.wait(0.3)

scene.preview()
