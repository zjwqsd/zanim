"""Lesson 06: SVG import, immutable VectorDocument reuse and reveal animation."""

from __future__ import annotations

from pathlib import Path

from zanim import DOWN, MUTED, TOP, Canvas, Group, Scene, Text, affine2d, load_svg
from zanim.vector import VectorObject2D

EXAMPLES = Path(__file__).resolve().parents[1]
SVG = EXAMPLES / "assets/fourier_heart.svg"


scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)

title = Text("SVG becomes ordinary Zanim vector data", font_size=35)
subtitle = Text(
    "load_svg() → VectorDocument → reusable VectorObject2D",
    font_size=22,
    color=MUTED,
)
title.place(anchor=TOP, at=scene.frame.top + 0.28 * DOWN)
subtitle.place(anchor=TOP, at=title.anchor(TOP) + 0.55 * DOWN)

# VectorDocument is immutable resource data. Multiple scene objects can share
# the exact same document while owning independent transforms/reveal/opacity.
heart_document = load_svg(SVG)
left = VectorObject2D(
    heart_document,
    reveal=0,
    transform=affine2d(position=(-2.6, -0.45), scale=0.72),
)
right = VectorObject2D(
    heart_document,
    reveal=0,
    opacity=0.72,
    transform=affine2d(position=(2.6, -0.45), rotation=-0.22, scale=0.72),
)
hearts = Group([left, right])

scene.add(title, subtitle, hearts)
left, right = map(scene.on, (left, right))
scene.wait(0.45)

with scene.parallel():
    left.create(duration=1.8)
    right.create(duration=1.8, at=0.35)

with scene.parallel(duration=1.25):
    left.affine(position=(-2.25, -0.2), rotation=0.18, scale=0.82)
    right.affine(position=(2.25, -0.2), rotation=-0.38, scale=0.82)
    right.opacity(to=1.0)

scene.wait(0.65)

scene.preview()
