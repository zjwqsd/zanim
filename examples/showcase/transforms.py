"""Lesson 05: LOCAL, PARENT and WORLD transforms plus Camera2D."""

from __future__ import annotations

from zanim import (
    BLUE,
    DEGREES,
    GREEN,
    LOCAL,
    MUTED,
    PARENT,
    RED,
    TOP,
    WHITE,
    WORLD,
    YELLOW,
    Canvas,
    Color,
    Dot,
    Group,
    Line,
    Scene,
    Square,
    Text,
    Vec2,
    affine2d,
)
from zanim.geometry import Object2D


def axis(color: Color, end: Vec2) -> Object2D:
    return Line(Vec2(), end, stroke=color, stroke_width=0.035)


def make_panel(center_x: float) -> tuple[Group, Group]:
    # The parent frame is deliberately rotated in WORLD. The child frame is
    # rotated again inside it, so LOCAL/PARENT/WORLD translations visibly differ.
    parent_x = axis(RED, Vec2(1.5, 0))
    parent_y = axis(GREEN, Vec2(0, 1.15))
    origin = Dot(radius=0.07, color=WHITE)

    body = Square(0.72, fill=BLUE.with_alpha(190), stroke=WHITE)
    child_x = axis(RED, Vec2(0.78, 0))
    child_y = axis(GREEN, Vec2(0, 0.78))
    tool = Group(
        [body, child_x, child_y],
        transform=affine2d(position=(-0.55, -0.1), rotation=-33 * DEGREES),
    )
    panel = Group(
        [parent_x, parent_y, origin, tool],
        transform=affine2d(position=(center_x, -0.45), rotation=20 * DEGREES),
    )
    return panel, tool


scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)

title = Text("One vector, three coordinate frames", font_size=35)
subtitle = Text(
    "move(by=(1.5, 0), frame=...) changes which basis interprets the vector",
    font_size=21,
    color=MUTED,
)
title.place(anchor=TOP, at=scene.frame.top + Vec2(0, -0.28))
subtitle.place(anchor=TOP, at=title.anchor(TOP) + Vec2(0, -0.55))

local_panel, local_tool = make_panel(-4.1)
parent_panel, parent_tool = make_panel(0.0)
world_panel, world_tool = make_panel(4.1)
labels = [
    Text("LOCAL", font_size=24, color=YELLOW),
    Text("PARENT", font_size=24, color=YELLOW),
    Text("WORLD", font_size=24, color=YELLOW),
]
for x, label in zip((-4.1, 0.0, 4.1), labels):
    label.place(anchor=TOP, at=Vec2(x, 2.05))

title, subtitle, local_panel, parent_panel, world_panel, *_ = scene.add(
    title, subtitle, local_panel, parent_panel, world_panel, *labels
)
local_tool = local_panel.children[-1]
parent_tool = parent_panel.children[-1]
world_tool = world_panel.children[-1]
scene.wait(0.6)

with scene.parallel(duration=2.2):
    local_tool.move(by=(1.5, 0), frame=LOCAL)
    parent_tool.move(by=(1.5, 0), frame=PARENT)
    world_tool.move(by=(1.5, 0), frame=WORLD)

scene.wait(0.45)
# Camera2D is a view transform over the same deterministic world state.
scene.camera.affine(position=(0.65, -0.15), scale=1.12, duration=1.0)
scene.camera.affine(position=(0.0, 0.0), scale=1.0, duration=0.9)
scene.wait(0.35)

scene.preview()
