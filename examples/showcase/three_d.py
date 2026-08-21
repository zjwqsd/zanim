"""3D meshes, smooth surfaces, SO(3), a shared camera and 2D overlays."""
from __future__ import annotations

from math import pi, sin, sqrt
from pathlib import Path

from zanim import (
    Box3D, Camera3D, Canvas, Color, Easing, SO3, Scene, Surface3D, Text,
    Transform2D, Transform3D, Vec3,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/showcase/three_d.mp4"
BLUE = Color(96, 166, 255)
GREEN = Color(82, 205, 150)
RED = Color(245, 92, 105)


def terrain(x: float, z: float) -> float:
    r = sqrt(x*x + z*z)
    return 0.38 * sin(2.3*r) * (1.0 / (1.0 + 0.18*r*r))


def build_scene() -> Scene:
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
        x_range=(-2.4, 2.4), y_range=(-2.4, 2.4), resolution=(49, 49),
        color=GREEN, transform=surface_base,
    )

    # A tiny world-frame tripod makes the common 3D coordinate system obvious.
    axes = (
        Box3D(Vec3(2.3, 0.025, 0.025), color=RED, transform=Transform3D.translation(0.9, -1.55, 0)),
        Box3D(Vec3(0.025, 2.3, 0.025), color=GREEN, transform=Transform3D.translation(-0.25, -0.4, 0)),
        Box3D(Vec3(0.025, 0.025, 2.3), color=BLUE, transform=Transform3D.translation(-0.25, -1.55, 1.15)),
    )

    title = Text("2D and 3D share one Scene", font_size=31, transform=Transform2D.translation(0, 3.25), z_index=10)
    left_label = Text("SO(3)", font_size=24, transform=Transform2D.translation(-3.2, -2.7), z_index=10)
    right_label = Text("Surface3D", font_size=24, transform=Transform2D.translation(3.0, -2.7), z_index=10)
    scene.add(*axes, cube, surface, title, left_label, right_label)

    with scene.parallel():
        scene.fade_in(title, duration=0.7)
        scene.fade_in(left_label, duration=0.8, at=0.15)
        scene.fade_in(right_label, duration=0.8, at=0.2)
        scene.play_transform_function(
            cube,
            lambda a: cube_base @ SO3.rotation_axis(Vec3(1, 1, 0.35), 2*pi*a).to_transform3d(),
            duration=5.0,
            easing=Easing.LINEAR,
        )
        scene.play_transform_function(
            surface,
            lambda a: Transform3D.translation(2.25, -0.35, 0)
                      @ Transform3D.rotation_y(-0.65*pi*a)
                      @ Transform3D.scaling(0.72),
            duration=5.0,
            easing=Easing.LINEAR,
        )
    scene.wait(0.35)
    return scene


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene()
    print(scene.render_video(OUTPUT, verify_random_access=True))


if __name__ == "__main__":
    main()
