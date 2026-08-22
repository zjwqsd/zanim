"""Lesson 11: 3D meshes/surfaces, SO(3), Camera3D and 2D overlays."""

from __future__ import annotations

from math import sin, sqrt

from zanim import (
    BLUE,
    BOTTOM,
    DOWN,
    GREEN,
    PI,
    RED,
    SO3,
    TAU,
    TOP,
    Box3D,
    Camera3D,
    Canvas,
    Easing,
    Scene,
    Surface3D,
    Text,
    Transform3D,
    Vec2,
    Vec3,
)


def terrain(x: float, z: float) -> float:
    r = sqrt(x * x + z * z)
    return 0.38 * sin(2.3 * r) * (1.0 / (1.0 + 0.18 * r * r))


scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)
scene.camera3d = Camera3D(
    position=Vec3(7.0, 4.6, 8.0),
    target=Vec3(0, 0.15, 0),
    fov_y_degrees=38,
    layer_z_index=0,
)

cube_base = Transform3D.translation(-2.35, 0.35, 0)
cube = Box3D(Vec3(1.55, 1.55, 1.55), color=BLUE, transform=cube_base)

surface_base = Transform3D.translation(2.25, -0.35, 0) @ Transform3D.scaling(0.72)
surface = Surface3D(
    terrain,
    x_range=(-2.4, 2.4),
    y_range=(-2.4, 2.4),
    resolution=(49, 49),
    color=GREEN,
    transform=surface_base,
)

# A tiny world-frame tripod makes the common 3D coordinate system obvious.
axes = (
    Box3D(Vec3(2.3, 0.025, 0.025), color=RED, transform=Transform3D.translation(0.9, -1.55, 0)),
    Box3D(Vec3(0.025, 2.3, 0.025), color=GREEN, transform=Transform3D.translation(-0.25, -0.4, 0)),
    Box3D(
        Vec3(0.025, 0.025, 2.3), color=BLUE, transform=Transform3D.translation(-0.25, -1.55, 1.15)
    ),
)

title = Text("2D and 3D share one Scene", font_size=31, opacity=0, z_index=10)
left_label = Text("SO(3)", font_size=24, opacity=0, z_index=10)
right_label = Text("Surface3D", font_size=24, opacity=0, z_index=10)
title.place(anchor=TOP, at=scene.frame.top + 0.35 * DOWN)
left_label.place(anchor=BOTTOM, at=scene.frame.bottom + Vec2(-3.2, 0.55))
right_label.place(anchor=BOTTOM, at=scene.frame.bottom + Vec2(3.0, 0.55))
scene.add(*axes)
cube, surface, title, left_label, right_label = scene.add(
    cube, surface, title, left_label, right_label
)

with scene.parallel(duration=5):
    title.fade_in(duration=0.7)
    left_label.fade_in(duration=0.8, at=0.15)
    right_label.fade_in(duration=0.8, at=0.2)
    cube.transform_function(
        lambda a: cube_base @ SO3.rotation_axis(Vec3(1, 1, 0.35), TAU * a).to_transform3d(),
        easing=Easing.LINEAR,
    )
    surface.transform_function(
        lambda a: (
            Transform3D.translation(2.25, -0.35, 0)
            @ Transform3D.rotation_y(-0.65 * PI * a)
            @ Transform3D.scaling(0.72)
        ),
        easing=Easing.LINEAR,
    )
scene.wait(0.35)

scene.preview()
