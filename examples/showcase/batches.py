"""Lesson 08: dense primitive data with BatchObject2D and batch transitions."""

from __future__ import annotations

from math import cos, sin

from zanim import DOWN, PI, TAU, TOP, Canvas, Color, Scene, Text, Vec2
from zanim.batch import BatchObject2D, CircleSet, LineSet

N = 420


def circle_state(phase: float) -> CircleSet:
    centers = []
    radii = []
    fills = []
    for i in range(N):
        u = i / N
        angle = TAU * (u * 5.0 + phase)
        radius = 0.8 + 3.0 * u
        centers.append(Vec2(radius * cos(angle), radius * sin(angle)))
        radii.append(0.025 + 0.055 * (0.5 + 0.5 * sin(5 * TAU * u + phase * 2 * TAU)))
        fills.append(Color(round(70 + 170 * u), round(145 + 70 * (1 - u)), 255, 220))
    return CircleSet(tuple(centers), tuple(radii), tuple(fills))


def line_state(phase: float) -> LineSet:
    count = 180
    starts = []
    ends = []
    colors = []
    widths = []
    for i in range(count):
        u = i / count
        a = TAU * u
        b = a + phase * PI
        starts.append(Vec2(2.0 * cos(a), 2.0 * sin(a)))
        ends.append(Vec2(3.5 * cos(b), 3.5 * sin(b)))
        colors.append(Color(100, round(140 + 100 * u), 255, 100))
        widths.append(0.006)
    return LineSet(tuple(starts), tuple(ends), tuple(colors), tuple(widths))


scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)
title = Text("600 primitives, two batch objects", font_size=31, opacity=0)
title.place(anchor=TOP, at=scene.frame.top + 0.35 * DOWN)
dots = BatchObject2D(circle_state(0.0), z_index=2)
lines = BatchObject2D(line_state(0.0), z_index=0)
lines, dots, title = scene.add(lines, dots, title)
title.fade_in(duration=0.6)

with scene.parallel(duration=2):
    dots.batch(to=circle_state(0.33))
    lines.batch(to=line_state(0.55))
with scene.parallel(duration=2):
    dots.batch(to=circle_state(0.68))
    lines.batch(to=line_state(1.0))
scene.wait(0.4)

scene.preview()
