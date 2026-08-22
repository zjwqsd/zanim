"""Planar open-chain forward kinematics from the ordinary Zanim scene graph."""
from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path

from zanim import (
    BOTTOM, CENTER, Canvas, Color, Dot, Group2D, Line, Object2D, ORIGIN, RIGHT, SE2,
    Scene, Text, TOP, Vec2, preview_source,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/showcase/kinematics.mp4"

BLUE = Color(83, 146, 255)
GREEN = Color(91, 220, 166)
ORANGE = Color(255, 156, 86)
WHITE = Color(235, 241, 250)
MUTED = Color(150, 165, 190)


def link(length: float, color: Color) -> Object2D:
    return Object2D(Line(ORIGIN, Vec2(length, 0)), stroke=color, stroke_width=0.07)


@preview_source
def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(1280, 720, 92), fps=60)

    # Declare geometry in each joint's own local frame.
    l1, l2, l3 = 2.2, 1.7, 1.15
    link1 = link(l1, BLUE)
    link2 = link(l2, GREEN)
    link3 = link(l3, ORANGE)

    j1_mark = Dot(ORIGIN, radius=0.11, color=WHITE, z_index=4)
    j2_mark = Dot(ORIGIN, radius=0.11, color=WHITE, z_index=4)
    slider_mark = Dot(ORIGIN, radius=0.11, color=ORANGE, z_index=4)
    ee_mark = Dot(Vec2(l3, 0), radius=0.13, color=Color(255, 224, 105), z_index=5)

    # Every Group2D transform is local -> parent. These home transforms are
    # exactly the fixed offsets in an open kinematic chain.
    joint3 = Group2D([slider_mark, link3, ee_mark], position=(l2, 0))
    joint2 = Group2D([j2_mark, link2, joint3], position=(l1, 0))
    joint1 = Group2D([j1_mark, link1, joint2])

    title = Text("Open-chain FK = ordinary frame composition", font_size=32)
    formula = Text(
        "T₀ₑ = T₀₁(q₁) · T₁₂(q₂) · T₂₃(q₃)",
        font_size=25,
        color=MUTED,
    )
    title.place(anchor=TOP, at=scene.frame.top + Vec2(0, -0.35))
    formula.place(anchor=TOP, at=title.anchor(BOTTOM) + Vec2(0, -0.16))

    # Top-level placement is world placement. Child offsets above remain parent-relative.
    joint1.place(anchor=CENTER, at=Vec2(-0.6, -0.55))

    title, formula, joint1 = scene.add(title, formula, joint1)
    joint2 = scene.on(joint2)
    joint3 = scene.on(joint3)
    scene.wait(0.6)

    home1 = SE2.from_affine(joint1.transform_value)
    home2 = SE2.from_affine(joint2.transform_value)
    home3 = SE2.from_affine(joint3.transform_value)

    # Two revolute joints and one prismatic joint animate independently. Each
    # provider returns one COMPLETE local->parent pose; hierarchy composition is FK.
    with scene.parallel(duration=6):
        joint1.transform_function(
            lambda a: home1 @ SE2(theta=0.75 * sin(2 * pi * a))
        )
        joint2.transform_function(
            lambda a: home2 @ SE2(theta=-0.9 * sin(2 * pi * a + 0.8))
        )
        joint3.transform_function(
            lambda a: home3
            @ SE2(translation=0.65 * (0.5 - 0.5 * cos(2 * pi * a)) * RIGHT)
        )

    scene.wait(0.5)
    return scene


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene()
    print(scene.render_video(OUTPUT, verify_random_access=True))


if __name__ == "__main__":
    main()
