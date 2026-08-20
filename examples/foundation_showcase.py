from __future__ import annotations

from pathlib import Path

from zanim import (
    Arrow, Canvas, Circle, Color, Dot, DynamicNumber, Easing, Group2D, Math,
    NumberFormat, NumberLine, Object2D, RIGHT, ScalarValue, Scene, Square,
    StrokeStyle, Style, Text, Transform2D, UP, Vec2,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'media' / 'foundation_showcase.mp4'


def build_scene() -> Scene:
    scene = Scene(canvas=Canvas(width=1280, height=720, unit_size=90), fps=60)

    number_line = NumberLine((-4, 4), length=8.0, tick_step=1.0, z_index=-2)
    number_line.shift(0, -2.25)

    square = Object2D(
        Square(1.25),
        style=Style(fill=Color(83, 146, 255, 190), stroke=StrokeStyle(Color(180, 215, 255), .035)),
    )
    circle = Object2D(
        Circle(.68),
        style=Style(fill=Color(255, 151, 92, 175), stroke=StrokeStyle(Color(255, 210, 180), .035)),
    )
    dot = Dot(radius=.11, color=Color(255, 230, 120), z_index=5)
    shapes = Group2D([square, circle, dot]).arrange(RIGHT, buff=.65)
    shapes.shift(-1.0, .35)

    arrow = Arrow(Vec2(-3.6, -1.35), Vec2(2.8, -1.35), color=Color(125, 220, 190), z_index=1)

    title = Text('Unified Zanim Objects', font_size=35, z_index=10)
    title.to_edge(scene.canvas, UP, buff=.55)

    formula = Math(r'x(t) =', font_size=32, transform=Transform2D.translation(2.8, 1.7), z_index=10)
    value = ScalarValue(0)
    number = DynamicNumber(
        value,
        number_format=NumberFormat(width=6, decimals=2, sign='space'),
        font_size=30,
        transform=Transform2D.translation(4.35, 1.7),
        color=Color(255, 225, 140),
        z_index=10,
    )

    # Nested group: renderer still only sees heterogeneous leaves.
    root = Group2D([number_line, shapes, arrow], opacity=1.0)
    scene.add(root, title, formula, number, value)

    # 0..1.4: draw geometry / reveal vectors through their native mechanisms.
    with scene.parallel():
        scene.create(square, duration=1.4, easing=Easing.SMOOTHSTEP)
        scene.create(circle, duration=1.4, easing=Easing.SMOOTHSTEP)
        scene.fade_in(title, duration=1.0)
        scene.fade_in(formula, duration=1.0)
        scene.fade_in(number, duration=1.0)

    # 1.4..3.2: independent style/value channels overlap cleanly.
    with scene.parallel():
        scene.play_style(
            square,
            Style(fill=Color(116, 225, 170, 210), stroke=StrokeStyle(Color(210, 255, 235), .07)),
            duration=1.8,
        )
        scene.play_value(value, 12.5, duration=1.8, easing=Easing.LINEAR)
        scene.play_transform(
            shapes,
            Transform2D.translation(.8, .2).rotate(.18),
            duration=1.8,
        )

    # 3.2..4.7: camera is another transform-channel object.
    scene.play_transform(
        scene.camera,
        Transform2D.translation(-.35, -.1) @ Transform2D.scaling(1.18),
        duration=1.5,
    )

    # 4.7..5.8: parent opacity affects every heterogeneous child uniformly.
    scene.fade_out(root, duration=1.1)
    scene.wait(.35)
    return scene


def main() -> None:
    scene = build_scene()
    out = scene.render_video(OUT, fps=60, verify_random_access=True)
    print(out)
    print(f'duration={scene.timeline.cursor:.2f}s unified-objects=ok random-access=ok')


if __name__ == '__main__':
    main()
