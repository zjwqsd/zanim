"""Lesson 13: linear algebra on a mathematically unbounded plane.

The grid and reference polygon receive the exact same complete linear map.
No grid extent is authored: Zig resolves only the visible part of the infinite
plane, including the singular rank-1 projection stage.
"""

from __future__ import annotations

from math import pi
from typing import Callable

from zanim import (
    BLUE,
    CYAN,
    GREEN,
    MUTED,
    RED,
    WHITE,
    YELLOW,
    Canvas,
    Color,
    Dot,
    InfiniteGrid,
    InfiniteLine,
    Polygon,
    Scene,
    Text,
    Transform2D,
)

LinearMap = Callable[[float], Transform2D]


def _apply_together(scene: Scene, objects, provider: LinearMap, *, duration: float) -> None:
    """Apply one complete alpha->matrix provider to all reference geometry."""
    with scene.parallel(duration=duration):
        for obj in objects:
            obj.transform_function(provider)


def _stage(
    scene: Scene,
    objects,
    name: str,
    matrix: str,
    provider: LinearMap,
    *,
    duration: float = 1.65,
    hold: float = 0.42,
) -> None:
    label = Text(name, font_size=24, color=WHITE, opacity=0, z_index=20)
    formula = Text(matrix, font_size=19, color=MUTED, opacity=0, z_index=20)
    label.move_to((0.0, -2.72))
    formula.move_to((0.0, -3.05))
    label, formula = scene.add(label, formula)

    with scene.parallel(duration=0.28):
        label.fade_in()
        formula.fade_in()
    _apply_together(scene, objects, provider, duration=duration)
    scene.wait(hold)
    _apply_together(scene, objects, lambda a: provider(1.0 - a), duration=0.95)
    with scene.parallel(duration=0.24):
        label.fade_out()
        formula.fade_out()
    scene.remove(label, formula)
    scene.wait(0.08)


scene = Scene(canvas=Canvas(1280, 720, 100), fps=60)

title = Text("Linear algebra on an infinite plane", font_size=32, color=WHITE, z_index=20)
subtitle = Text(
    "the infinite grid and the finite reference shape receive the same 2×2 matrix",
    font_size=19,
    color=MUTED,
    z_index=20,
)
title.move_to((0.0, 3.16))
subtitle.move_to((0.0, 2.76))

# The grid has no authored boundary. The two colored infinite lines make the
# transformed basis directions visible even when the lattice becomes dense.
grid = InfiniteGrid(
    0.5,
    color=Color(94, 108, 136, 115),
    stroke_width=0.014,
    z_index=-4,
)
x_axis = InfiniteLine((0, 0), (1, 0), color=RED.with_alpha(220), stroke_width=0.035, z_index=-2)
y_axis = InfiniteLine((0, 0), (0, 1), color=GREEN.with_alpha(220), stroke_width=0.035, z_index=-2)

# An asymmetric L shape is a better reference than a circle/square: rotation,
# shear, orientation and collapse are all immediately visible.
reference = Polygon(
    [
        (0.45, 0.35),
        (2.05, 0.35),
        (2.05, 0.85),
        (1.20, 0.85),
        (1.20, 1.75),
        (0.45, 1.75),
    ],
    fill=BLUE.with_alpha(145),
    stroke=CYAN,
    stroke_width=0.045,
    z_index=4,
)
origin = Dot((0, 0), radius=0.055, color=YELLOW, z_index=8)
reference_note = Text("same A", font_size=17, color=CYAN, z_index=20)
reference_note.move_to((1.28, 2.02))

# Only these four objects transform. The origin remains fixed because every
# map is linear rather than affine-with-translation.
grid, x_axis, y_axis, reference, origin, title, subtitle, reference_note = scene.add(
    grid, x_axis, y_axis, reference, origin, title, subtitle, reference_note
)
linear_objects = (grid, x_axis, y_axis, reference)
scene.wait(0.55)

_stage(
    scene,
    linear_objects,
    "Rotation",
    "R(θ),  θ: 0 → 55°   ·   det A = 1",
    lambda a: Transform2D.rotation(a * 55.0 * pi / 180.0),
)

_stage(
    scene,
    linear_objects,
    "Anisotropic scaling",
    "A = diag(1.8, 0.55)",
    lambda a: Transform2D.scaling(1.0 + 0.8 * a, 1.0 - 0.45 * a),
)

_stage(
    scene,
    linear_objects,
    "Shear",
    "A = [[1, 1.15], [0, 1]]   ·   area preserved",
    lambda a: Transform2D.shear(x=1.15 * a),
)

_stage(
    scene,
    linear_objects,
    "Singular projection",
    "A → [[1, 0.65], [0, 0]]   ·   rank 2 → rank 1",
    lambda a: Transform2D(
        xx=1.0,
        xy=0.65 * a,
        yx=0.0,
        yy=1.0 - a,
    ),
    duration=1.9,
    hold=0.62,
)

_stage(
    scene,
    linear_objects,
    "General invertible map",
    "A = [[1.15, 0.75], [-0.45, 1.05]]",
    lambda a: Transform2D(
        xx=1.0 + 0.15 * a,
        xy=0.75 * a,
        yx=-0.45 * a,
        yy=1.0 + 0.05 * a,
    ),
    duration=1.9,
)

scene.wait(0.45)
scene.preview()
