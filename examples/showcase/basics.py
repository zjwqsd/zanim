"""Core 2D authoring: objects, groups, layout, style, transforms and camera."""
from __future__ import annotations

from pathlib import Path

from zanim import (
    Arrow, Canvas, Circle, Color, Dot, Easing, Group2D, Math, NumberLine,
    Object2D, RIGHT, Scene, Square, StrokeStyle, Style, Text, Transform2D,
    UP, Vec2,
)

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "media/showcase/basics.mp4"

BLUE = Color(83, 146, 255)
ORANGE = Color(255, 151, 92)
GREEN = Color(91, 220, 166)
WHITE = Color(238, 242, 250)


def shape_style(color: Color, alpha: int = 185) -> Style:
    return Style(
        fill=Color(color.r, color.g, color.b, alpha),
        stroke=StrokeStyle(Color(220, 232, 255), 0.035),
    )


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(1280, 720, 90), fps=60)

    title = Text("Objects compose like values", font_size=34)
    title.to_edge(scene.canvas, UP, buff=0.5)
    subtitle = Math(r'"Scene" = "objects" + "timeline"', font_size=28, color=Color(170, 185, 215))
    subtitle.move_to(Vec2(0, 2.55))

    square = Object2D(Square(1.25), style=shape_style(BLUE))
    circle = Object2D(Circle(0.68), style=shape_style(ORANGE))
    dot = Dot(radius=0.11, color=Color(255, 227, 112), z_index=5)
    shapes = Group2D([square, circle, dot]).arrange(RIGHT, buff=0.7)
    shapes.shift(-0.7, 0.35)

    number_line = NumberLine((-4, 4), length=8.0, tick_step=1.0, z_index=-2)
    number_line.shift(0, -2.2)
    arrow = Arrow(Vec2(-3.4, -1.35), Vec2(3.0, -1.35), color=GREEN, z_index=1)
    stage = Group2D([number_line, shapes, arrow])

    scene.add(stage, title, subtitle)
    with scene.parallel():
        scene.fade_in(title, duration=0.8)
        scene.fade_in(subtitle, duration=0.9, at=0.15)
        scene.create(square, duration=1.2)
        scene.create(circle, duration=1.2, at=0.15)
        scene.fade_in(dot, duration=0.6, at=0.7)

    with scene.parallel():
        scene.play_transform(
            shapes,
            Transform2D.translation(0.8, 0.25).rotate(0.18),
            duration=1.6,
        )
        scene.play_style(
            square,
            Style(fill=Color(GREEN.r, GREEN.g, GREEN.b, 205),
                  stroke=StrokeStyle(Color(220, 255, 240), 0.06)),
            duration=1.6,
        )
        scene.play_transform(
            arrow,
            Transform2D.translation(0.15, 0.1).scale(1.08),
            duration=1.6,
        )

    scene.play_transform(
        scene.camera,
        Transform2D.translation(-0.3, -0.08) @ Transform2D.scaling(1.15),
        duration=1.3,
    )
    scene.fade_out(stage, duration=0.9)
    scene.wait(0.3)
    return scene


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    scene = build_scene()
    print(scene.render_video(OUTPUT, verify_random_access=True))


if __name__ == "__main__":
    main()
